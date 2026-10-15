"""Stage an explicitly requested single scorer with the normal review checks."""
import argparse
import json
from pathlib import Path
import shutil

from batch import digest, verify_standalone
from discover import REPO, atomic_json


def main(args):
    progress = REPO / 'tools/who_scored/progress'
    registry = json.loads((progress / 'expansion-batches.json').read_text())
    release = next(r for r in registry['standalone_releases'] if r['name'] == args.release)
    folder = progress / args.release
    records = json.loads((folder / 'review.json').read_text())['reviewed_clips']
    media = REPO / 'static/who-scored'
    clips = json.loads((media / 'clips.json').read_text())
    sources = verify_standalone(release, records,
        json.loads((progress / 'expansion-candidates.json').read_text()), clips,
        args.exports, json.loads((folder / 'source-audit.json').read_text()),
        folder, registry['batches'])
    print('Single scorer: official attribution, every-frame visual review and immutable media verified.')
    if not args.stage:
        return
    if len(clips) + 1 != release['target_library_size']:
        raise ValueError('The standalone release must reach its requested library size')
    provenance = json.loads((media / 'sources.json').read_text())
    for record in records:
        for filename in record['assets'].values():
            target = media / filename
            if target.exists() and digest(target) != digest(args.exports / filename):
                raise ValueError('Existing media would be overwritten')
        for filename in record['assets'].values():
            shutil.copyfile(args.exports / filename, media / filename)
        source = sources[record['id']]
        clips.append({'id': record['id'], 'pid': record['pid'], **record['assets'],
                      'motion': record['motion'], 'source': source['source']})
        provenance.append({**source, 'exported_sha256': record['asset_sha256'],
                           'review_record': str((folder / 'review.json').relative_to(REPO))})
    atomic_json(media / 'clips.json', clips)
    atomic_json(media / 'sources.json', provenance)
    release['status'] = 'staged_awaiting_github_and_live_verification'
    registry['verified_playable_additions'] = len(clips) - registry['starting_library_size']
    atomic_json(progress / 'expansion-batches.json', registry)
    print(f'Staged locally: {len(clips)} scorers. GitHub and live verification still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', choices=['bonus-160'], default='bonus-160')
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--stage', action='store_true')
    main(parser.parse_args())
