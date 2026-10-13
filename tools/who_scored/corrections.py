"""Verify an entire reviewed correction set; optionally stage immutable media.

Unlike an expansion batch, corrections retain every clip ID and scorer PID.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from batch import digest, inspect_media, inspect_poster
from discover import REPO, atomic_json
from pipeline import frame_count


def verify_corrections(folder, exports, current, inspect=True):
    baseline = json.loads((folder / 'clips-before.json').read_text())
    issues = json.loads((folder / 'issues.json').read_text())['clips']
    records = json.loads((folder / 'review.json').read_text())['reviewed_clips']
    old = {clip['id']: clip for clip in baseline}
    reported = {issue['id']: issue for issue in issues}
    reviewed = {record['id']: record for record in records}
    if not issues or len(reported) != len(issues) or len(reviewed) != len(records) or set(reviewed) != set(reported):
        raise ValueError('Every reported clip needs exactly one completed correction review')
    if len(old) != len(baseline) or len({clip['pid'] for clip in baseline}) != len(baseline):
        raise ValueError('Baseline must contain distinct clip IDs and scorers')
    proposed = {ident: dict(clip) for ident, clip in old.items()}
    for ident, record in reviewed.items():
        if ident not in old or record['pid'] != old[ident]['pid'] or record['pid'] != reported[ident]['pid']:
            raise ValueError('A correction must retain the reported scorer and clip ID')
        if reported[ident]['previous_assets'] != {kind: old[ident][kind] for kind in ['masked', 'reveal', 'poster']}:
            raise ValueError('Reported assets disagree with the baseline')
        edit_path = folder / f'{ident}-edit.json'
        if digest(edit_path) != record['edit_sha256']:
            raise ValueError('Edit changed after review')
        edit = json.loads(edit_path.read_text())
        frames = frame_count(edit)
        source = record['source']
        if (edit['id'], edit['pid'], frames, edit['source_sha256']) != (ident, record['pid'], record['frames'], source['source_sha256']):
            raise ValueError('Review disagrees with the scorer, source or extraction window')
        if source['id'] != ident or source['pid'] != record['pid'] or source['player'] != edit['player']:
            raise ValueError('Official source identity disagrees with the edit')
        reviews = record['reviews']
        identity, coverage, scoring, encoded = (reviews[key] for key in ['official_identity', 'silhouette_coverage', 'scoring_highlight', 'encoded_video'])
        if not all(review.get('passed') is True for review in [identity, coverage, scoring, encoded]):
            raise ValueError('Identity, coverage, scoring highlight and encoded checks must pass')
        if identity['jersey'] != source['jersey'] or not identity.get('note', '').strip():
            raise ValueError('Visual identity review must agree with the official jersey')
        if coverage['visually_reviewed_frames'] != list(range(frames)) or not coverage.get('note', '').strip():
            raise ValueError('Coverage review must inspect every frame and record its findings')
        finish = edit.get('scoring_play_end_frame')
        if type(finish) is not int or not 0 <= finish < frames or scoring['finish_frame'] != finish or not scoring.get('note', '').strip():
            raise ValueError('The complete scoring finish needs an explicit matching review')
        if encoded.get('all_frames_decoded') is not True or encoded.get('matching_pair') is not True:
            raise ValueError('Both encoded streams need full decoding and matching timing')
        if not {0, frames // 2, frames - 1} <= set(encoded.get('visually_sampled_frames', [])):
            raise ValueError('Encoded first, middle and final frames need visual review')
        version = edit.get('version', 'v1')
        if not re.fullmatch(r'v[1-9][0-9]*', version):
            raise ValueError('Invalid media version')
        for kind in ['masked', 'reveal', 'poster']:
            filename = record['assets'][kind]
            expected = f'{ident}-{version}.jpg' if kind == 'poster' else f'{ident}-{"original" if kind == "reveal" else kind}-{version}.mp4'
            if filename != expected or filename == old[ident][kind] or digest(exports / filename) != record['asset_sha256'][kind]:
                raise ValueError('Corrected media must be new immutable assets matching the review')
        if inspect:
            durations = [inspect_media(exports / record['assets'][kind], frames) for kind in ['masked', 'reveal']]
            if durations[0] != durations[1]:
                raise ValueError('Video pair timing differs')
            inspect_poster(exports / record['assets']['poster'])
        proposed[ident].update(record['assets'])
        proposed[ident]['source'] = source['source']
        proposed[ident]['motion'] = record['motion']
    result = [proposed[clip['id']] for clip in baseline]
    if current not in [baseline, result]:
        raise ValueError('Playable library changed outside the reported corrections')
    return result, records


def main(args):
    args.review = args.review.resolve()
    args.exports = args.exports.resolve()
    media = REPO / 'static/who-scored'
    current = json.loads((media / 'clips.json').read_text())
    proposed, records = verify_corrections(args.review, args.exports, current)
    print(f'{len(records)} corrections: complete visual reviews, scoring finishes and immutable matching media verified.')
    if not args.stage:
        return
    # Check all destination hashes before any copy; never overwrite a prior version.
    for record in records:
        for kind, filename in record['assets'].items():
            target = media / filename
            if target.exists() and digest(target) != record['asset_sha256'][kind]:
                raise ValueError('Previously staged media would be overwritten')
    sources = json.loads((media / 'sources.json').read_text())
    by_id = {record['id']: record for record in records}
    for record in records:
        for filename in record['assets'].values():
            if not (media / filename).exists():
                shutil.copyfile(args.exports / filename, media / filename)
    for index, source in enumerate(sources):
        if source['id'] in by_id:
            record = by_id[source['id']]
            sources[index] = {**record['source'], 'exported_sha256': record['asset_sha256'],
                              'review_record': str((args.review / 'review.json').relative_to(REPO))}
    atomic_json(media / 'sources.json', sources)
    atomic_json(media / 'clips.json', proposed)
    print('Staged locally; publication and live verification are still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--stage', action='store_true')
    main(parser.parse_args())
