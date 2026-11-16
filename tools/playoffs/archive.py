"""Keep daily, as-recorded league forecasts; never reconstruct old probabilities."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ZONE = 'America/New_York'
FIELDS = ('version', 'model', 'start', 'season', 'season_games', 'simulations',
          'completed_games', 'total_games', 'updated_at', 'checked_at',
          'source_sha256', 'teams', 'advanced', 'validation', 'latest_game')


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Archive timestamps must include a time zone')
    return parsed


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':'), sort_keys=True) + '\n').encode()


def snapshot(feed, commit=None):
    from model import validate_forecast
    validate_forecast(feed)
    checked, updated = timestamp(feed['checked_at']), timestamp(feed['updated_at'])
    if updated > checked:
        raise ValueError('Forecast cannot be newer than its data check')
    day = checked.astimezone(ZoneInfo(ZONE)).date().isoformat()
    saved = {key: deepcopy(feed[key]) for key in FIELDS if key in feed}
    # Daily browsing needs team records, all five stages and team breakdowns.
    # Live games/news and the growing intraday trend series stay in the live feed.
    saved['history'] = []
    saved['games'] = []
    saved['archive'] = {'version': 1, 'date': day, 'time_zone': ZONE,
                        'kind': 'recorded', **({'source_commit': commit} if commit else {})}
    return saved


def capture(feed, folder=None, commit=None):
    folder = Path(folder) if folder is not None else ROOT / 'playoffs_archive'
    saved = snapshot(feed, commit)
    day = saved['archive']['date']
    index_path = folder / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {
        'version': 1, 'time_zone': ZONE, 'days': []}
    if index.get('version') != 1 or index.get('time_zone') != ZONE:
        raise ValueError('Unsupported archive index')
    entries = {row['date']: row for row in index['days']}
    previous = entries.get(day)
    if previous and timestamp(previous['checked_at']) >= timestamp(saved['checked_at']):
        return False
    content = encode(saved)
    entry = {key: saved[key] for key in ('season', 'updated_at', 'checked_at')}
    entry.update(date=day, sha256=hashlib.sha256(content).hexdigest())
    entries[day] = entry
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (day + '.json')
    temp = path.with_suffix('.tmp')
    temp.write_bytes(content)
    temp.replace(path)
    index['days'] = [entries[key] for key in sorted(entries)]
    temp_index = index_path.with_suffix('.tmp')
    temp_index.write_bytes(encode(index))
    temp_index.replace(index_path)
    return True


def backfill(ref='origin/main', folder=None):
    """Read only snapshots committed on the published main branch."""
    commits = subprocess.check_output([
        'git', 'log', '--first-parent', '--format=%H', ref, '--', 'playoffs_cache.json'
    ], cwd=ROOT, text=True).splitlines()
    count = 0
    for commit in commits:
        raw = subprocess.check_output(['git', 'show', commit + ':playoffs_cache.json'], cwd=ROOT)
        # capture keeps only the latest data check per NHL calendar day, even if
        # a later code merge included an older feed. No current stats are mixed in.
        count += capture(json.loads(raw), folder, commit)
    return count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backfill-ref', help='Recover actual forecasts from main-branch Git history')
    args = parser.parse_args()
    if args.backfill_ref:
        print('Daily snapshots recovered:', backfill(args.backfill_ref))
    else:
        print('Daily snapshot updated:', capture(json.loads((ROOT / 'playoffs_cache.json').read_text())))
