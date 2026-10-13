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

## Pending expansion: six batches of 40

The new expansion targets **240 additional unique scorers**, for 279 total.
`progress/expansion-candidates.json` contains 268 distinct official scorer
candidates with spare events. These are discovery records, not playable clips.
`progress/expansion-batches.json` fixes six ordered groups of 40. The first batch
has 40 corroborated source originals and three reviewed exports; **none of this
expansion is active or published in the game yet**.

Use the isolated SAM2 environment and store raw footage, API caches, models and
working frames outside the checkout:

```sh
python tools/who_scored/discover.py
python tools/who_scored/collect.py --batch 1 --storyboards
# Optional: inspect a different event for one scorer.
python tools/who_scored/collect.py --ids goal-45 --source-choice 1 --storyboards
```

Source collection corroborates the exact scorer and highlight ID against a second
official endpoint, records the game jersey number and checks the downloaded
source checksum. Storyboards are keyed to the selected video ID. Do not save
public-player policy keys or expiring rendition URLs in provenance.

A clip requires three recorded checks: official attribution plus visual jersey
identity; comparison of **every** original/masked frame; and complete encoded
video decoding with matching timing, plus visual first/middle/final inspection.
Keep occluding teammates and foreground objects visible. Repair coverage gaps
and recheck after any edit. Automatic opaque-pixel assertions prove rendering,
not that the correct player or all body parts were selected.

Reviewed edits and immutable review hashes live under `progress/batch-01/`.
Their exported media remain staged at
`/workspace/who-scored-expansion/batch-01/exports` until the entire batch passes.
The batch gate rejects fewer than 40 reviews, duplicate scorers, missing frames,
and media/edit checksums that changed after review:

```sh
python tools/who_scored/batch.py --batch 1 --exports /workspace/who-scored-expansion/batch-01/exports
# Once all 40 reviews pass, stage the batch locally.
python tools/who_scored/batch.py --batch 1 --exports /workspace/who-scored-expansion/batch-01/exports --stage
```

Then run the game, Daily schedule and full-decode media checks above, build the
site, publish the batch to GitHub, and verify its manifest and media on the live
Pages deployment. Staging locally does not count as a published batch. Proceed
with batches 2–6 in order. Daily assignments for past/today/tomorrow stay locked.
