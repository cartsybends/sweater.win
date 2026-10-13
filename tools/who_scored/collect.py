"""Collect and corroborate source videos for a pending expansion.

Originals and API caches remain outside the checkout. This never activates clips,
asserts that masks passed review, or saves expiring delivery URLs/policy keys.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import fcntl
import html
import json
from pathlib import Path
import re
import subprocess
import unicodedata
import urllib.request

from discover import REPO, atomic_json


def get(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Sweater clip source verification)', **(headers or {})}), timeout=45)


def json_get(url, headers=None):
    with get(url, headers) as response:
        return json.load(response)


def api(path, work):
    cached = work / 'api' / (path.replace('/', '_') + '.json')
    if cached.exists():
        return json.loads(cached.read_text())
    result = json_get('https://api-web.nhle.com/v1/' + path)
    atomic_json(cached, result)
    return result


def public_player(source):
    with get(source) as response:
        page = response.read().decode()
    match = re.search(r'data-plugin="bc-video-player-events"\s+data-options=\'([^\']+)\'', page)
    if not match:
        raise ValueError('Public NHL player configuration not found')
    options = json.loads(html.unescape(match[1]))
    account = options['brightcoveAccount']
    config = json_get(f'https://players.brightcove.net/{account}/{options["brightcovePlayer"]}_default/config.json')
    return account, config['video_cloud']['policy_key']


def normalized(text):
    return ''.join(character for character in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(character))


def corroborate(row, selected, work):
    landing = api(f'gamecenter/{selected["game_id"]}/landing', work)
    matches = [goal for period in landing.get('summary', {}).get('scoring', []) for goal in period['goals']
               if goal.get('playerId') == row['pid'] and str(goal.get('highlightClip')) == selected['source_video_id']]
    if len(matches) != 1:
        raise ValueError('Goal attribution and highlight ID must match a second official endpoint uniquely')
    goal = matches[0]
    name = goal['firstName']['default'] + ' ' + goal['lastName']['default']
    if normalized(name) != normalized(row['player']):
        raise ValueError('Official player name disagrees with source queue')
    box = api(f'gamecenter/{selected["game_id"]}/boxscore', work)
    players = [player for team in box.get('playerByGameStats', {}).values() for group in team.values()
               if isinstance(group, list) for player in group if player.get('playerId') == row['pid']]
    if len(players) != 1 or not isinstance(players[0].get('sweaterNumber'), int):
        raise ValueError('The scorer needs a unique official game jersey number')
    return {'official_event_id': goal['eventId'], 'jersey': players[0]['sweaterNumber'],
            'official_goal_scorer': name, 'source_attribution_verified': True}


def collect_one(row, credentials, args, previous):
    if args.source_choice is None and previous:
        selected = next((candidate for candidate in row['candidates']
                         if candidate['source_video_id'] == previous['source_video_id']), None)
        if selected is None:
            raise ValueError('Previously curated source is absent from the queue')
    else:
        selected = row['candidates'][args.source_choice or 0]
    attribution = corroborate(row, selected, args.work)
    account, policy = credentials
    metadata = json_get(f'https://edge.api.brightcove.com/playback/v1/accounts/{account}/videos/{selected["source_video_id"]}',
                        {'Accept': 'application/json;pk=' + policy})
    text = normalized(' '.join(metadata.get(field) or '' for field in ['name', 'description', 'long_description']))
    if normalized(row['player'].split()[-1]) not in text:
        raise ValueError('Media metadata does not corroborate the official scorer')
    renditions = [source for source in metadata.get('sources', []) if source.get('container') == 'MP4'
                  and source.get('src', '').startswith('https://') and not source.get('key_systems')]
    eligible = [source for source in renditions if source.get('height', 0) <= 720] or renditions
    if not eligible:
        raise ValueError('No supported public unencrypted MP4 rendition')
    chosen = max(eligible, key=lambda source: (source.get('height', 0), source.get('avg_bitrate', 0)))
    path = args.work / 'originals' / f'{row["id"]}-{selected["source_video_id"]}.mp4'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix('.partial')
        try:
            with get(chosen['src']) as response, temporary.open('wb') as output:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 100 * 1024 * 1024:
                        raise ValueError('Source exceeds the per-video download budget')
                    output.write(chunk)
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if previous and previous.get('source_video_id') == selected['source_video_id'] and previous.get('source_sha256') != checksum:
        raise ValueError('Original source changed; preserving the prior provenance without relabeling it')
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    stream = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    result = {'id': row['id'], 'pid': row['pid'], 'player': row['player'], **selected, **attribution,
              'original': str(path), 'source_sha256': checksum,
              'media_title': metadata.get('name'), 'duration': float(info['format']['duration']),
              'dimensions': [stream['width'], stream['height']],
              'status': 'original_ready_needs_edit_and_three_reviews', 'playable': False}
    if args.storyboards:
        folder = args.work / 'storyboards' / row['id'] / selected['source_video_id']
        folder.mkdir(parents=True, exist_ok=True)
        if not list(folder.glob('*.jpg')):
            subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(path), '-vf',
                            'fps=1,scale=320:180,tile=5x5', '-q:v', '3', '-y', str(folder / '%03d.jpg')], check=True)
        result['storyboards'] = str(folder)
    return result


def main(args):
    queue = json.loads(args.queue.read_text())
    rows = queue['candidates'][:args.limit]
    if args.batch:
        batches = json.loads((REPO / 'tools/who_scored/progress/expansion-batches.json').read_text())
        selected_batch = next((batch for batch in batches['batches'] if batch['batch'] == args.batch), None)
        if selected_batch is None:
            raise ValueError('Unknown batch')
        by_id = {row['id']: row for row in queue['candidates']}
        rows = [by_id[ident] for ident in selected_batch['ids']]
    if args.ids:
        rows = [row for row in queue['candidates'] if row['id'] in args.ids]
        if set(args.ids) != {row['id'] for row in rows}:
            raise ValueError('Unknown source IDs')
    if not rows or (args.source_choice is not None and any(args.source_choice >= len(row['candidates']) for row in rows)):
        raise ValueError('Each selected player must have the requested source choice')
    output = args.work / 'originals-manifest.json'
    prior = json.loads(output.read_text()) if output.exists() else {'originals': [], 'failures': []}
    completed = {row['id']: row for row in prior['originals']}
    # Only merge records changed by this run. Reapplying the entire prior snapshot
    # would overwrite another collector's newer source selection despite the lock.
    updates = {}
    failures = {}
    credentials = public_player(rows[0]['candidates'][0]['source'])
    def persist():
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = json.loads(output.read_text()) if output.exists() else {'originals': [], 'failures': []}
            merged = {row['id']: row for row in current['originals']}
            merged.update(updates)
            issues = {row['id']: row for row in current['failures']}
            issues.update(failures)
            for ident in updates:
                issues.pop(ident, None)
            atomic_json(output, {'originals': sorted(merged.values(), key=lambda row: int(row['id'].split('-')[1])),
                                'failures': sorted(issues.values(), key=lambda row: row['id']),
                                'playable_additions': 0, 'status': 'pending_mask_and_visual_review'})
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(collect_one, row, credentials, args, completed.get(row['id'])): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                completed[row['id']] = result
                updates[row['id']] = result
                failures.pop(row['id'], None)
                print(row['id'], 'official attribution + jersey + media verified;', len(completed), 'originals ready', flush=True)
            except Exception as error:
                failures[row['id']] = {'id': row['id'], 'error_type': type(error).__name__}
                print(row['id'], 'needs source investigation:', type(error).__name__, flush=True)
            persist()
    if failures or any(row['id'] not in completed for row in rows):
        raise SystemExit('Source collection incomplete; missing sources must not be counted as playable additions')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, default=REPO / 'tools/who_scored/progress/expansion-candidates.json')
    parser.add_argument('--work', type=Path, default=Path('/workspace/who-scored-expansion'))
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--batch', type=int, choices=range(1, 7))
    parser.add_argument('--source-choice', type=int, help='Zero-based alternate source index; default preserves curated sources')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--storyboards', action='store_true')
    options = parser.parse_args()
    if options.limit < 1 or (options.source_choice is not None and options.source_choice < 0) or (options.ids and options.batch):
        parser.error('Use a positive limit, a nonnegative source choice, and either IDs or a batch')
    main(options)
