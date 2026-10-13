"""Discover additional distinct scorers from official NHL goal events.

This produces a source queue, never a playable clip manifest. Existing players,
IDs and selected source events are preserved. Delivery URLs are not recorded.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
from pathlib import Path
import re
import time
import tempfile
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[2]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def fetch_score(day, cache):
    path = cache / (day.isoformat() + '.json')
    if path.exists():
        return json.loads(path.read_text())
    url = 'https://api-web.nhle.com/v1/score/' + day.isoformat()
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Sweater clip source verification)'})
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            if not isinstance(result.get('games'), list):
                raise ValueError('Official score response has no games list')
            atomic_json(path, result)
            return result
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def goal_sources(document, eligible, excluded):
    for game in document['games']:
        if game.get('gameType') != 2 or game.get('gameState') not in ('OFF', 'FINAL'):
            continue
        for goal in game.get('goals', []):
            pid = goal.get('playerId')
            video = goal.get('highlightClip')
            if pid not in eligible or pid in excluded or not video:
                continue
            player = goal.get('firstName', {}).get('default', '') + ' ' + goal.get('lastName', {}).get('default', '')
            if not player.strip():
                continue
            sharing = goal.get('highlightClipSharingUrl')
            if not sharing or not re.match(r'^https://(?:www\.)?nhl\.com/', sharing):
                continue
            yield pid, {
                'game_id': game['id'], 'date': game['gameDate'],
                'period': goal['period'], 'time_in_period': goal['timeInPeriod'],
                'player': player.strip(), 'official_goal_scorer': player.strip(),
                'team': goal['teamAbbrev'], 'source': sharing,
                'source_video_id': str(video),
                'discrete_video_id': str(goal['discreteClip']) if goal.get('discreteClip') else None,
                'goal_modifier': goal.get('goalModifier'),
            }


def discover(args):
    existing = json.loads((REPO / 'static/who-scored/clips.json').read_text())
    excluded = {clip['pid'] for clip in existing}
    eligible = {int(pid) for pid in json.loads((REPO / 'schedule.json').read_text())['players']}
    output = args.output.resolve()
    saved = json.loads(output.read_text()) if output.exists() else {}
    records = {row['pid']: row for row in saved.get('candidates', [])}
    by_pid = {clip['pid']: clip for clip in existing}
    for pid in excluded & records.keys():
        row = records[pid]
        if by_pid[pid]['id'] != row['id'] or by_pid[pid]['source'] not in {source['source'] for source in row['candidates']}:
            raise ValueError('Published scorer disagrees with the expansion queue')
    used_ids = {clip['id'] for clip in existing} | {row['id'] for row in records.values()}
    next_id = max(int(ident.split('-')[1]) for ident in used_ids) + 1
    days = []
    current = args.start
    while current <= args.end:
        days.append(current)
        current += timedelta(days=args.stride)
    checked = set(saved.get('checked_dates', []))
    errors = list(saved.get('discovery_errors', []))

    def persist():
        value = {
            'target_additional_players': args.additional,
            'current_playable_players': len(excluded),
            'target_total_players': saved.get('target_total_players', len(excluded) + args.additional),
            'batch_size': saved.get('batch_size', 40),
            'planned_batches': (args.additional + 39) // 40,
            'candidate_count': len(records), 'playable_additions': len(excluded & records.keys()),
            'status': 'source_discovery_only',
            'required_reviews': ['official_scorer_and_jersey', 'every_frame_mask_coverage', 'encoded_video_and_reveal_review'],
            'checked_dates': sorted(checked), 'discovery_errors': errors,
            'candidates': sorted(records.values(), key=lambda row: int(row['id'].split('-')[1])),
        }
        atomic_json(output, value)

    for offset in range(0, len(days), args.workers):
        batch = [day for day in days[offset:offset + args.workers] if day.isoformat() not in checked]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {day: executor.submit(fetch_score, day, args.cache) for day in batch}
            for day, future in futures.items():
                try:
                    document = future.result()
                except Exception as error:
                    errors.append({'date': day.isoformat(), 'error_type': type(error).__name__})
                    print(day, 'source request failed:', type(error).__name__, flush=True)
                    continue
                checked.add(day.isoformat())
                for pid, source in goal_sources(document, eligible, excluded):
                    if pid not in records:
                        ident = f'goal-{next_id:02d}'
                        next_id += 1
                        records[pid] = {'id': ident, 'pid': pid, 'player': source['player'], 'status': 'needs_source_and_mask_review', 'candidates': []}
                    row = records[pid]
                    if source['source_video_id'] not in {item['source_video_id'] for item in row['candidates']}:
                        row['candidates'].append(source)
                persist()
                print(day, len(document['games']), 'games;', len(records), 'distinct additional scorer candidates', flush=True)
        if len(records) >= args.additional + args.spares:
            break
    persist()
    if len(records) < args.additional:
        raise SystemExit(f'Only {len(records)} source candidates; expand the date range before claiming {args.additional} additions')
    print(f'Source queue saved: {len(records)} distinct candidates. No playable media or library entries were added.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--additional', type=int, default=240)
    parser.add_argument('--spares', type=int, default=28)
    parser.add_argument('--start', type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument('--end', type=date.fromisoformat, default=date(2025, 4, 17))
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--cache', type=Path, default=Path('/workspace/who-scored-expansion/score-cache'))
    parser.add_argument('--output', type=Path, default=REPO / 'tools/who_scored/progress/expansion-candidates.json')
    options = parser.parse_args()
    if options.additional < 1 or options.spares < 0 or options.stride < 1 or options.start > options.end:
        parser.error('Use a positive target/stride, nonnegative spare count and valid date range')
    discover(options)
