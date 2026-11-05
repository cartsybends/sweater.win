# Deep Cut prompt releases

The active bank has **308 different questions in 17 families**: 119 original
questions plus the 189-question expansion. Scoring editions are stored for
replays and do not count as additional questions. `active_prompt_ids` identifies
the current question editions; `practice_runs` identifies the 365 current sets.
Every set has seven different families, and the rotation covers every question.

## Evidence and eligibility

`prompt_facts.json` is an explicit NHL snapshot verified on November 4, 2026,
containing 8,810 players and 53,423 regular-season player-seasons. Each response
has its official NHL source URL and SHA-256 audit hash. Season GP sum to the
official career GP for every player. Fetch summaries in bounded decades: the
stats service silently limits responses and their reported totals to 10,000.
The collector rejects capped responses and incomplete career coverage.

`build_expansion.py` creates `static/deep-cut/expansion.json`. Its declarative
criteria make each answer set auditable. Team eras use the season's starting
year. Shared-club questions require recorded appearances for the same team in
the same season, exclude the anchor player, and explicitly do not claim that
they appeared in the same game. Traded-season stat totals are combined.
Birthplace, height, handedness, draft and name questions use official NHL bios.
All questions require a recorded NHL regular-season appearance.

Team-name questions keep predecessors separate. Franchise-count questions
combine name changes and relocations. The original Jets (`WIN`) belong with
Phoenix/Arizona, not the Thrashers/current Jets (`WPG`); the NHL team metadata's
incorrect `WIN` franchise ID is corrected explicitly. Utah is a separate NHL
franchise. Pre-1979 debutants are excluded from the modern undrafted question.

## Publication

Collect a new fact snapshot only for an explicit content release using the
read-only `Verify Deep Cut scoring data` workflow, with `collect_prompt_facts`
enabled. Download its `deep-cut-prompt-facts` artifact and review its completeness
before installing it. The daily site build does not refetch these frozen facts.

Run `python -B tools/deep_cut/build_expansion.py` to reproduce this release.
The script refuses to overwrite a different published bank. Future content
changes require a new version and identities; do not edit a published answer
set. `scoring.py` appends current-roster editions for team-era questions and for
eligible current teammates of an active named player in shared-club questions,
using the same 10/15-point policy as other single-club prompts. New practice sets use
all categories immediately. The day planner preserves today's shared daily and
all past dates, and rotates expanded sets into future days. Every previously
published player, question, scoring edition and run remains available unchanged.

Verify with `python -B tests/deep_cut_expansion.py`, the existing Deep Cut data,
scoring and TOI tests, and `node tests/deep_cut.mjs`. The expansion tests check
complete career coverage, actual membership boundaries, relocations, rotation
coverage, current-club scoring and the stats service's response-cap failure.
