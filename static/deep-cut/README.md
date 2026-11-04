# Deep Cut

Seven timed, open-answer NHL prompts per daily shift. Each recognized player has
a fixed score of 10, 15, 30, 60, 85 or 100. Passes and timeouts score zero. A
three-second preview precedes a 35-second answer window; rejected names cost
three seconds. The absolute deadline persists across reloads and navigation.
Practice is unlimited and unranked. Daily results use Sweater's existing stats,
XP, archives, sharing, and server-validated leaderboard replay.

The game fills the viewport with an original rink scene and overlays large
prompts and controls. A jumbotron clock lights seven-segment digits down to
tenths, with a red warning for the final five seconds. Correct answers trigger
six animation levels: small sprays, longer skating bursts, rare-tier spotlights,
and a gold-star celebration for cult legends. Optional audio follows the tier;
reduced motion removes moving particles, camera impacts, and light sweeps.

Backgrounds progress by total score: neighbourhood rink below 150, community
arena at 150, big leagues at 300, rafters at 450, and legends at 600. The next
threshold is visible and crossing it announces the new arena. Rarity scoring
and the immutable published puzzle bank do not change with these visual effects.

The seven shift markers are miniature pucks. Completed pucks take the answer's
rarity colour; the current prompt has a mint outline, and missed prompts stay
muted. Their labels include the round, points and rarity for screen readers.

Click or tap exposed scenery for a small local flourish, or drag for a trail:
snowflakes at the neighbourhood rink, ice chips at the community arena,
confetti in the big leagues, silver glints in the rafters and gold sparkles
in legends. These effects ignore game panels and controls, preserve native
touch scrolling, respect reduced motion and never affect answers or the clock.
Particles expire within 1.2 seconds and are capped at 120. Leaving the game,
resizing or hiding the tab clears them; a new scene removes old-scene particles.

The neighbourhood has snow-rooted evergreen trunks and complete building
facades. The community arena has empty bleachers, three rinkside spectators,
and lights suspended from the roof. Clean 1440×900 background exports and a
labelled overview live in `backgrounds/`; the production build copies these
PNG files for direct viewing and download. `dcDraw(time,{backgroundOnly:true})`
renders the same scenery without the skater or interaction effects for exports.

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

Common given-name variants (for example, Mike/Michael and Matt/Matthew) are
recognized with the full surname and optional birth year. Exact canonical names
take priority over aliases, and ambiguous identities still require more detail.
Aliases map to the original NHL player ID; they do not add team appearances or
change any published answer's rarity score. Michael Cammalleri's Calgary record
already exists in v1, and "Mike Cammalleri" resolves to that same record.

The persistent **Answer corrections** checkbox is on by default. It enables
unique surnames, common first-name variants, conservative spelling corrections,
and useful partial names. Long names can tolerate two edits; short names get
at most one. Surname prefixes require six characters, and first+surname
fragments require at least eight overall with four in the surname. Exact names
and literal prefixes take priority over spelling corrections; the closest
spelling candidates are considered before eligibility. Ambiguous matches need
more detail. The result identifies the recognized full name and correction type.
Turning the option off requires an exact full name; accents, punctuation and
case remain normalized, and known full-name variants such as Mike/Michael stay
valid. Changing this preference does not reset the deadline.

The locally served VT323 font is by Peter Hull and licensed under the SIL Open
Font License; see `FONT-LICENSE.txt`.

Run `node tests/deep_cut.mjs` and `python -B tests/deep_cut_data.py`.

For a self-contained playable preview without fetching NHL data, run
`python -B tools/deep_cut/preview.py --out work/deep-cut.html` and open that file
in a browser. Preview saves use separate storage keys. The production mode is
available at `#deepcut` after Sweater's usual build and deployment.
