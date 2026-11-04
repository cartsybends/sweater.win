# Deep Cut

Seven timed, open-answer NHL prompts per daily shift. Each recognized player has
a fixed score of 10, 15, 30, 60, 85 or 100. Passes and timeouts score zero. A
three-second preview precedes a 35-second answer window; rejected names cost
three seconds. The absolute deadline persists across reloads and navigation.
Practice is unlimited and unranked. Daily results use Sweater's existing stats,
XP, archives, sharing, and server-validated leaderboard replay.

`data.json` is a frozen v1 content release: 8,280 players, 119 prompts across
seven families, and 365 seven-round sets. Its source is the verified NHL-backed
community catalog through 2025–26. Each prompt stores its complete eligible set
and fixed point values. `tools/deep_cut/build_data.py` records the source hash
and refuses to overwrite a changed published bank. Release future changes under
new versioned prompt/run IDs while retaining previous records and assignments.
Do not regenerate v1 during the daily build.

Rarity is an editorial estimate using career games, awards, Hall of Fame
membership, era, and appearances for the particular team. Iconic players have
explicit familiarity anchors. Up to two qualifying role players are selected as
100-point cult legends. Scores are not observed player-pick percentages. This
method, the historical cutoff, and the 300-point daily-win threshold are stated
in the game.

`model.mjs` owns name normalization, alias/unique-surname matching, conservative
one-edit typo matching, action validation and scoring. `game.js` integrates the
model with Sweater and draws original procedural pixel scenery and a skater on
Canvas. Game sound is optional and off by default. Reduced motion disables
continuous movement. No reference game's source or artwork is reused.

The locally served VT323 font is by Peter Hull and licensed under the SIL Open
Font License; see `FONT-LICENSE.txt`.

Run `node tests/deep_cut.mjs` and `python -B tests/deep_cut_data.py`.

For a self-contained playable preview without fetching NHL data, run
`python -B tools/deep_cut/preview.py --out work/deep-cut.html` and open that file
in a browser. Preview saves use separate storage keys. The production mode is
available at `#deepcut` after Sweater's usual build and deployment.
