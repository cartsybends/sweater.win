# Reviewed Who Scored? expansion

The manifest has 79 unique players: the original 9, 30 earlier additions and the
first expansion batch of 40. Media are
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

## Reproducing tracked edits

Install SAM2 and its dependencies, and obtain the SAM2.1 Hiera tiny checkpoint.
Use `gather_expansion.py` to collect the selected sources. Restore each edit's
`original` to the local downloaded source path before processing; work directories
are keyed to the source, extraction window, crop and source checksum.

```sh
python tools/who_scored/pipeline.py prepare EDIT.json
python tools/who_scored/pipeline.py track EDIT.json --checkpoint MODEL.pt --threads 2
python tools/who_scored/pipeline.py render EDIT.json --output static/who-scored
```

Reviewed prompts select only the credited scorer.
`tracking_image_size` optionally selects 1024 instead of the default 512 when
small hands or helmet edges need more detail; CPU tracking takes longer. Changing
the resolution invalidates the tracking signature and requires retracking.
Explicit per-frame polygons, ellipses and lines fix occlusion gaps. `allow_empty` is permitted only after a
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

Who Scored is daily-only: one shared scheduled goal each day, unlocking at
midnight Eastern. Today's progress and finished result survive refreshes.
Unlimited and archive entry paths cannot unlock another goal; replay, slow
motion and the original reveal remain available for today's clip.
Expanding the Daily pool replaces only unlocked future assignments and preserves
past, today and tomorrow. The builder retains every clip's scorer in the embedded
player data, including players available only from the schedule archive.

The setup screen derives the footage year range from the active clips' official
game dates and explains that players may have changed teams. Use game dates for
migrated videos; their publication date can be years later than the actual goal.

## Correcting existing highlights

`progress/corrections-01/` records the 41 reported early endings and silhouette
problems. Each corrected version retains the same scorer and clip ID. Four use a
replacement official goal (Robertson, Zibanejad, Crouse and Coleman). The other
cuts retain the scoring action and its finish/aftermath, including camera pans
after the scorer exits. A visible puck crossing the line is not required.

Review every original/masked frame, the full scene and the compressed export.
Readable jersey numbers and continuous movement must confirm the scorer; official
attribution alone does not identify which person to mask. Pay particular attention
to foreground faces, helmets, gloves, teammate overlaps and the last frame. Keep
`allow_empty` limited to verified exits or complete occlusions. Record the reviewed
scoring finish in `scoring_play_end_frame`; export caps cannot remove it.

The correction gate checks the complete reported set, all visual review records,
source/edit/media hashes, matching decoded video timing, and preserved scorer IDs:

```sh
python tools/who_scored/corrections.py --review tools/who_scored/progress/corrections-01 --exports /workspace/who-scored-corrections/exports
# Stage only the completed, reviewed set.
python tools/who_scored/corrections.py --review tools/who_scored/progress/corrections-01 --exports /workspace/who-scored-corrections/exports --stage
python tests/who_scored_batches.py
```

Keep previous media versions and review records intact. After staging, run the
game/schedule/media checks, browser playback through the end of both streams,
publish to GitHub and verify the live assets. Staging is not publication.

## Expansion: six batches of 40

The new expansion targets **240 additional unique scorers**, for 279 total.
`progress/expansion-candidates.json` contains 268 distinct official scorer
candidates with spare events. These are discovery records, not playable clips.
`progress/expansion-batches.json` fixes six ordered groups of 40. The first batch
has 40 corroborated source originals and completed reviews. Its 40 video pairs
and posters are included in the playable manifest. The batch registry records
GitHub and live-deployment verification separately from local staging.
Batches 2–6 contain the remaining 200 planned additions.

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
and recheck after any edit. Review the complete scene as well as the scorer crop so a raised hand outside
the initial matte cannot be overlooked. Automatic opaque-pixel assertions prove rendering,
not that the correct player or all body parts were selected.

Reviewed edits and immutable review hashes live under `progress/batch-01/`.
Raw footage and working exports stay outside the checkout. Only the reviewed
video pairs and posters are copied into `static/who-scored/` after the entire
batch passes.
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
