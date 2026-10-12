# Who Scored? clip library

Thirty-nine distinct scorers are available in this mode. Each round uses one camera angle,
a solid black matte on the scorer, a matching original reveal, a masked poster,
and no audio. Score graphics and on-ice player-name tickers are removed where present.
`sources.json` records the original NHL.com highlight, source-file checksum and edit timing.

The site owner reports that an NHL contact approved editing and hosting these clips.
That reported permission is the basis for this supplied library; it has not been independently verified.

To add a scorer:

1. Identify the scorer in the original shooting action, using their jersey number
   and the official goal attribution. Track that same player backwards through
   the lead-up; the initial puck carrier may be the passer. Prepare and inspect a
   masked clip, matching reveal and masked JPEG poster. Compare the original and
   silhouette frame by frame, including overlaps, the first frame and the finish. Remove
   score graphics, name labels and commentary. Export H.264 MP4, 960×540, 24 fps,
   `yuv420p`, with a fast-start header. Keep one camera angle and a short goal sequence.
2. Add a unique opaque `id`, NHL player `pid`, filenames, move description and official
   `source` URL to `clips.json`. Add its edit provenance to `sources.json`.
   Keep existing IDs so saved rounds and archived dailies continue to work. Use new
   filenames when replacing a clip so browsers load the corrected edit immediately.
3. Run `node tests/who_scored.cjs`, `python tests/who_scored_schedule.py`, and
   `python tools/who_scored/validate.py --decode`. Build the site and check both videos
   before publishing.

The builder validates and copies every referenced asset. Daily assignments are persisted
in `schedule.json`, with a no-repeat window based on the library size. Unlimited uses a
browser-local shuffle bag and saves its current goal, guesses and remaining rotation.
Adding players expands the pool without rewriting past or locked daily assignments.
NHL.com source links appear only after the answer is revealed.
