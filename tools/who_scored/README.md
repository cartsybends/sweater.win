# Reviewed Who Scored? expansion

The manifest has 39 unique players: the existing 9 plus 30 new scorers. Media are
960x540, 24fps, silent H.264 with fast-start headers. Each masked video shares
its frame count and camera angle with its reveal. Existing goal01..09 IDs and
corrected v2 media stay intact.

`expansion-sources.json` records the selected official highlights and checksums.
`progress/final-source-audit.json` cross-checks all 30 highlight IDs against official
NHL goal attribution. `progress/expansion-review.json` records visual coverage and
identity checks for every addition. Four completed exports were recovered from an
interrupted run; their original masks are unavailable, and their provenance states
which source rendition was used for verification. All their exported pairs were
visually reviewed again.

## Reproducing the 26 new tracked edits

Install SAM2 and its dependencies, and obtain the SAM2.1 Hiera tiny checkpoint.
Use `gather_expansion.py` to collect the selected sources. Restore each edit's
`original` to the local downloaded source path before processing; work directories
are keyed to the source, extraction window, crop and source checksum.

```sh
python tools/who_scored/pipeline.py prepare EDIT.json
python tools/who_scored/pipeline.py track EDIT.json --checkpoint MODEL.pt --threads 2
python tools/who_scored/pipeline.py render EDIT.json --output static/who-scored
```

Reviewed prompts select only the credited scorer. Explicit per-frame polygons,
ellipses and lines fix occlusion gaps. `allow_empty` is permitted only after a
verified exit from the camera. `export_frames` shortens a reviewed source sequence
without reusing any frames beyond the cap. Goal 35's corrections are also supported
by `patch_goal35.py`. Always compare every original/masked frame after retracking.

## Validation and publication

```sh
node tests/who_scored.cjs
python tests/who_scored_schedule.py
python tools/who_scored/validate.py --decode
python build_sweater.py --quiet --out site/index.html --site-url https://sweater.win/
```

Unlimited completes a 39-player shuffle bag without repeats. Expanding the Daily
pool replaces only unlocked future assignments and preserves past, today and
tomorrow. The builder retains every clip's scorer in the embedded player data,
including players available only from the schedule archive.
