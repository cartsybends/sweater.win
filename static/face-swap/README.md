# Face Swap

Replaces the retired Blur mode with a two-player visual guessing game. The 200
portraits follow the ten approved examples and are bundled locally, along with
60 original NHL headshots.
No portrait generation or remote image request is needed during a round.

Guess either source player first. Correct names lock in without using a miss.
Five wrong guesses end a round. The first four misses reveal position, age on
the puzzle date, country, and team, in that order, for each unidentified player.
Finding both players scores 10 points minus 2 per miss. An unfinished pair scores
zero. Duplicate guesses do not use a miss.

Daily puzzles use stable IDs in `schedule.json`. Unlimited uses a saved shuffled
rotation that visits all 200 portraits before repeating. Daily, archive, and
Unlimited progress use separate Face Swap records; old Blur results are retained
as historical results and are not converted into Face Swap wins.

`model.mjs` is shared between the frontend and the leaderboard. `game.js`,
`styles.css`, and `view.html` are embedded by the Python builder. The builder
validates the hashes in `puzzles.json` and copies every portrait and source
headshot into the published `face-swap/` directory. `sources.json` records the
official NHL reference URLs.

To expand the bank, add a new image and pair with a unique ID, include both local
headshots, and record their SHA-256 hashes. Preserve puzzle IDs and pairings so
saved rounds and published daily answers remain valid. To improve a portrait,
publish a new filename such as `face-198-v2.webp` and move the previous filename
and hash into that puzzle's `previous_images` list. Both revisions are validated
and copied to the site, so an already-open client can still load its old photo.
Never overwrite a published image file or change a pair's source player IDs.

Portraits must preserve recognizable facial anatomy from both players. Assign
specific features to each source instead of asking for a vague average: for
example, one player's eyes/brows/nose and the other's cheeks/mouth/jaw. Hair and
facial hair can reinforce those identities, but cannot be the sole contribution
from one player. Review each face alongside both originals at the size used in
the game. Reject a smooth, attractive portrait if one identity has disappeared.
Keep coherent, natural anatomy, a neutral jersey and consistent headshot framing.

Checks: `node tests/face_swap.mjs` and `python -B tests/face_swap_data.py`.
