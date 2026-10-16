# Who Scored? clip library

Seventy-nine distinct scorers supply the daily goal library. Each round uses one camera angle,
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
in `schedule.json`, with a no-repeat window based on the library size. Adding players
expands the pool without rewriting past or locked daily assignments.
Who Scored offers one goal per day, shared by everyone, with a new goal at
midnight Eastern. Refreshes restore today's progress or completed result.
There are no Unlimited or archive rounds. Replays and slow motion of today's
clip remain unlimited, and its original becomes available after the answer.
NHL.com source links appear only after the answer is revealed. The completed result
replaces the player-profile button with the game's date, both teams and final score,
linked to its NHL.com box score. Overtime and shootout results are labelled.

Hints appear in rounded bubbles beneath the name field: position group (Forward
or Defenseman) after two misses, then birth country after four. Specific forward
positions stay hidden. Hints persist on refresh and disappear when the round ends.

Every source needs its original `game_id` and `date`. `games.json` stores the verified
final result for each game, keyed by that ID: `id`, `date`, `away` and `home` (each
with `abbrev`, `name`, `score`), and `finish` (`REG`, `OT`, or `SO`). Verify these
against `https://api-web.nhle.com/v1/gamecenter/{game_id}/landing` after adding or
replacing a highlight. Use `gameDate`, the final team scores, and
`periodDescriptor.periodType` from a completed (`OFF` or `FINAL`) game. The builder
joins this committed data to each clip and rejects missing or mismatched results;
the browser does not need to fetch game details.
