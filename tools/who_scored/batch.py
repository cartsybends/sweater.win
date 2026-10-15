"""Check or stage a complete reviewed batch of 40. Never marks a deployment live.

python tools/who_scored/batch.py --batch 1 --exports /workspace/who-scored-expansion/batch-01/exports
Add --stage only after every clip has three completed review records.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from discover import REPO, atomic_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_media(path, frames):
    streams = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)]))['streams']
    if len(streams) != 1:
        raise ValueError('Only a silent video stream is allowed')
    stream = streams[0]
    if (stream['codec_name'], stream['pix_fmt'], stream['width'], stream['height'],
            stream['r_frame_rate'], int(stream['nb_frames'])) != ('h264', 'yuv420p', 960, 540, '24/1', frames):
        raise ValueError('Export format or frame count disagrees with the review')
    raw = path.read_bytes()
    if raw.index(b'moov') > raw.index(b'mdat'):
        raise ValueError('Video must have fast-start headers')
    subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(path), '-f', 'null', '-'], check=True)
    return stream['duration']


def inspect_poster(path):
    from PIL import Image
    with Image.open(path) as poster:
        if poster.size != (960, 540) or poster.format != 'JPEG':
            raise ValueError('Poster must be a 960x540 JPEG')
        poster.verify()


def verify_batch(batch, records, queue, existing, exports, audit, edits):
    ids = batch['ids']
    if len(ids) != 40 or len(set(ids)) != 40:
        raise ValueError('A release requires exactly 40 distinct clips')
    if len(records) != 40 or {record['id'] for record in records} != set(ids):
        raise ValueError(f'Batch has {len(records)}/40 reviews; incomplete batches cannot be staged')
    if set(batch['approved_clips']) != set(ids):
        raise ValueError('Every batch member needs explicit review approval')
    old_ids = {clip['id'] for clip in existing}
    old_pids = {clip['pid'] for clip in existing}
    pids = [record['pid'] for record in records]
    if len(set(pids)) != 40 or old_ids & set(ids) or old_pids & set(pids):
        raise ValueError('Every addition must be a distinct new scorer and clip ID')
    return verify_records(records, queue, exports, audit, edits)


def verify_standalone(release, records, queue, existing, exports, audit, edits, batches):
    """An explicitly requested single addition never counts as a partial batch."""
    ids = release['ids']
    if len(ids) != 1 or len(records) != 1 or {r['id'] for r in records} != set(ids):
        raise ValueError('A standalone release requires exactly one reviewed clip')
    if set(release['approved_clips']) != set(ids):
        raise ValueError('The standalone clip needs explicit review approval')
    if set(ids) & {ident for row in batches for ident in row['ids']}:
        raise ValueError('A standalone release cannot consume part of a planned batch')
    if any(c['id'] in ids or c['pid'] == records[0]['pid'] for c in existing):
        raise ValueError('The standalone addition must be a distinct new scorer and clip ID')
    return verify_records(records, queue, exports, audit, edits)


def verify_records(records, queue, exports, audit, edits):
    """Apply identical source, visual-review and immutable-media checks."""
    by_id = {row['id']: row for row in queue['candidates']}
    sources = {source['id']: source for source in audit['sources']}
    if len(sources) != len(audit['sources']) or set(sources) != {r['id'] for r in records}:
        raise ValueError('Official source audit must cover every release member exactly once')
    for record in records:
        ident = record['id']
        source = sources[ident]
        if by_id[ident]['pid'] != record['pid'] or source['pid'] != record['pid']:
            raise ValueError('Scorer identity disagrees with the source queue')
        if source['source'] not in {candidate['source'] for candidate in by_id[ident]['candidates']}:
            raise ValueError('The audited highlight is not an official queued source')
        edit_path = edits / f'{ident}-edit.json'
        if digest(edit_path) != record['edit_sha256']:
            raise ValueError('Edit changed after review')
        edit = json.loads(edit_path.read_text())
        version = edit.get('version', 'v1')
        if not re.fullmatch(r'v[1-9][0-9]*', version):
            raise ValueError('Invalid media version')
        frames = edit.get('export_frames', round(edit['duration'] * 24))
        if (edit['id'], edit['pid'], frames, edit['source_sha256']) != (
                ident, record['pid'], record['frames'], source['source_sha256']):
            raise ValueError('Source checksum or extraction window disagrees with review')
        if record['source_sha256'] != source['source_sha256']:
            raise ValueError('Reviewed source checksum disagrees with the audit')
        reviews = record['reviews']
        identity, coverage, encoded = (reviews[key] for key in ['official_identity', 'silhouette_coverage', 'encoded_video'])
        if not all(review.get('passed') is True for review in [identity, coverage, encoded]):
            raise ValueError('All three reviews must pass')
        if (identity['jersey'], identity['event_id']) != (source['jersey'], source['official_event_id']):
            raise ValueError('Official identity review disagrees with the source audit')
        if coverage['visually_reviewed_frames'] != list(range(frames)) or not coverage.get('note', '').strip():
            raise ValueError('Visual coverage review must include every frame and its findings')
        if encoded.get('all_frames_decoded') is not True or encoded.get('matching_pair') is not True:
            raise ValueError('Encoded videos need complete decoding and matching-pair checks')
        if not {0, frames // 2, frames - 1} <= set(encoded.get('visually_sampled_frames', [])):
            raise ValueError('Encoded first, middle and final frames need visual review')
        if not record.get('motion', '').strip():
            raise ValueError('A clip needs a reviewed shooting description')
        for kind in ['masked', 'reveal', 'poster']:
            filename = record['assets'][kind]
            expected = f'{ident}-{version}.jpg' if kind == 'poster' else f'{ident}-{"original" if kind == "reveal" else kind}-{version}.mp4'
            if filename != expected or digest(exports / filename) != record['asset_sha256'][kind]:
                raise ValueError('Export changed after review or has an invalid opaque filename')
        durations = [inspect_media(exports / record['assets'][kind], frames) for kind in ['masked', 'reveal']]
        if durations[0] != durations[1]:
            raise ValueError('Encoded video pair has different timing')
        inspect_poster(exports / record['assets']['poster'])
    return sources


def main(args):
    progress = REPO / 'tools/who_scored/progress'
    registry = json.loads((progress / 'expansion-batches.json').read_text())
    batch = next(row for row in registry['batches'] if row['batch'] == args.batch)
    folder = progress / f'batch-{args.batch:02d}'
    records = json.loads((folder / 'review.json').read_text())['reviewed_clips']
    queue = json.loads((progress / 'expansion-candidates.json').read_text())
    media = REPO / 'static/who-scored'
    existing = json.loads((media / 'clips.json').read_text())
    sources = verify_batch(batch, records, queue, existing, args.exports,
                           json.loads((progress / f'batch-{args.batch:02d}-source-audit.json').read_text()), folder)
    print(f'Batch {args.batch}: 40 new scorers, three review passes and immutable media verified.')
    if not args.stage:
        return
    standalone_ids = {ident for release in registry.get('standalone_releases', [])
                      for ident in release['ids']}
    active_standalones = standalone_ids & {clip['id'] for clip in existing}
    if len(existing) != registry['starting_library_size'] + (args.batch - 1) * 40 + len(active_standalones):
        raise ValueError('Stage batches in order after preceding batches are complete')
    provenance = json.loads((media / 'sources.json').read_text())
    provenance_by_id = {source['id']: source for source in provenance}
    for record in records:
        source = sources[record['id']]
        for filename in record['assets'].values():
            target = media / filename
            if target.exists():
                if digest(target) != digest(args.exports / filename):
                    raise ValueError('Existing media would be overwritten')
            else:
                shutil.copyfile(args.exports / filename, target)
        existing.append({'id': record['id'], 'pid': record['pid'], **record['assets'],
                         'motion': record['motion'], 'source': source['source']})
        reviewed_source = {**source, 'exported_sha256': record['asset_sha256'],
                           'review_record': f'tools/who_scored/progress/batch-{args.batch:02d}/review.json'}
        if source['id'] in provenance_by_id and provenance_by_id[source['id']] != reviewed_source:
            raise ValueError('Previously staged provenance changed')
        provenance_by_id[source['id']] = reviewed_source
    atomic_json(media / 'sources.json', list(provenance_by_id.values()))
    atomic_json(media / 'clips.json', existing)
    batch['status'] = 'staged_awaiting_github_and_live_verification'
    registry['verified_playable_additions'] = len(existing) - registry['starting_library_size']
    atomic_json(progress / 'expansion-batches.json', registry)
    print('Staged locally. Run game/schedule/media checks, publish to GitHub and verify the live deployment.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=int, choices=range(1, 7), required=True)
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--stage', action='store_true')
    main(parser.parse_args())
