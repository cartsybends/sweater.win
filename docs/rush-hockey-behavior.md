# Rush behavior references

This is a bounded, stylized 3v2 simulation, rather than a full hockey match. EDGE speed, shot and location data affect execution and preferences; the derived awareness/handling ratings are game parameters, not measured NHL hockey-IQ data.

## Footage reviewed

User upload: **Hockey School – 3 MAN RUSH (3v2) – The Hockey Net – PHC**, 8:58.

Reviewed the entire visual breakdown at two-second intervals, then the entry and finish at quarter-second intervals. The initial live sequence (roughly 6–14 seconds) and later annotated replay show staggered entry, the depth player occupying a defender, a third attacker remaining available above the puck, and a pass into a shooting position. The stationary frames through much of the clip are coaching annotations of that same play; they are not separate rushes.

## Decisions implemented

- Puck carriers always use two hands. Only off-puck attackers sprinting before the offensive zone may release the bottom hand. Regripping starts before the blue line and completes before a pass can be sent.
- Support destinations are chosen together. One attacker provides depth off the strong-side defender's heels; the other stays above the puck in a different lane. Deep attacks rotate an attacker back up instead of sending everyone to the crease.
- A carrier can delay outside a closing defender while the depth route develops. The delay is bounded, and body/stick avoidance stays active.
- Passing compares the second defender's coverage: a defender following the depth player exposes the higher layer; a defender staying high can expose the depth player. Open-lane and pressure checks still apply, including the backdoor option.
- Shooting shares one grip anchor and mirrors shooting-side motion without mirroring the apparent height of the top hand. The hand extends during loading and pulls back through release. Slapshot elevation comes from backswing pitch, with a compact lateral sweep. A large slapshot windup requires room; measured shot speed alone does not select it.

## Coaching sources

- Greg Revak, [Modern 3v2: Fundamentals and Puck Carrier Reads](https://hockeysarsenal.substack.com/p/modern-3v2-fundamentals): depth and width, remain a shooting threat, react to D1/D2 rather than charging into the pair.
- Greg Revak, [Middle Lane Driver and Third Player Reads](https://hockeysarsenal.substack.com/p/modern-3v2-rush-attack-middle-lane): work off the defender's heels, reroute, stop at the net, show a receiving target.
- Greg Revak, [Middle Delay](https://hockeysarsenal.substack.com/p/zone-entry-middle-delay) and [Offensive Overlap](https://hockeysarsenal.substack.com/p/rush-offense-creating-via-the-overlap): different speed and depth layers make defenders commit.
- Ice Hockey Systems, [Kick Out with Middle Lane Drive](https://icehockeysystems.com/coaching-clip/3-on-2-zone-entry-kick-out-middle-lane-drive): outside receiver waits for the drive, then exploits space inside the dots.
- The Coaches Site, [3 on 2 Attack Rush](https://members.thecoachessite.com/article/3-on-2-attack-rush-an-offensive-pressure-tactic?suggested=5): F3 in a soft spot above the puck, sticks on the ice, width and depth.
- Darryl Belfry / Ice Hockey Systems, [Small Space to Big Space](https://www.icehockeysystems.com/hockey-drills/3-v-2-small-space-big-space): move possession out of congested areas; defenders block lanes with sticks down.
- Greg Revak, [Rush Leverage](https://hockeysarsenal.substack.com/p/understanding-rush-leverage): protect inside ice and choose leverage deliberately.
- Greg Revak, [Top and Bottom Hands](https://hockeysarsenal.substack.com/p/shooting-top-and-bottom-hands), [Puckhandling Hands](https://hockeysarsenal.substack.com/p/puckhandling-technique-top-and-bottom-hands), [Soft Catch](https://hockeysarsenal.substack.com/p/shooting-off-the-soft-catch): top-hand control, sliding lower hand, loading and releasing smoothly.

The uploaded video supplied observed motion frames. Web sources supplied accessible coaching text; embedded web videos were not treated as watched footage.

Run `node tests/rush_behavior.cjs` from the repository root for possession, readiness, mirrored spacing and transition checks. Run `node tests/rush_scenarios.cjs` for 480 varied attacks at 30/60/144 fps and open/blocked backdoor feeds.
