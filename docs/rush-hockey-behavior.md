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
- When contained on entry, the carrier stretches the pair toward an outside lane and considers an open outlet before a moderate shooting chance. A pass can develop the attack even when it does not immediately give the receiver a better shot. Open close-range chances still trigger a shot.
- Proposed support destinations use projected blade positions, never the currently painted DOM anchor. Pass decisions include only receivers who have completed entry and regripped, so rejected passes do not consume the rush's pass budget.
- Tactical reads, movement, checks and shot phases share a capped simulation clock. Slow frames cannot trigger shot timeouts before the entry develops or skip the shooting windup.
- Safe entry outlets are judged as plays that move defensive coverage, rather than only by the receiver's immediate shot quality. A contained carrier allows that first play to develop before taking an average shooting lane; a genuine open close-range chance remains available.
- Wrist, snap and slap shots first align the body and puck with a forehand shooting box facing the actual net target. Off-wing alignment follows shooting handedness and takes extra setup time. Weight transfer, a staggered skating base, top-hand pull, lower-shaft flex and follow-through distinguish wrist sweeps, compact snaps and raised slap backswing.
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

- Greg Revak, [Shooting Body Shape](https://hockeysarsenal.substack.com/p/shooting-body-shape) and [Playing on the Off Wing](https://hockeysarsenal.substack.com/p/the-benefits-of-playing-on-the-off): shoulders over the puck, downforce, and forehand access from the opposite wing.
- Dwayne Blais / Ice Hockey Systems, [Improve Your Snap Shot](https://icehockeysystems.com/skill-development-videos/perfect-snap-shot) and [Wrist Shot / Snap Shot](https://www.icehockeysystems.com/hockey-drills/ice-shooting-wrist-shotsnap-shot): shooting box, top-hand extension and pull, lower-hand pressure and weight transfer.

The uploaded video supplied observed motion frames. Web sources supplied accessible coaching text; embedded web videos were not treated as watched footage.

Run `node tests/rush_behavior.cjs` from the repository root for possession, readiness, mirrored spacing, proposed-route DOM independence and shooting transitions. Run `node tests/rush_scenarios.cjs` for 480 varied attacks at 30/60/144 fps and open/blocked backdoor feeds. Run `node tests/rush_flow.cjs` for 600 complete breakouts and entries from four daily generated units, using real player positions, shooting hands and game-assigned roles at mobile/desktop widths and 15/30/60/120/144 fps, including painted blade anchors, receiver eligibility, passing frequency and second-pass opportunities.

Run `node tests/rush_shots.cjs` for 144 full setup/load/contact/follow sequences across both hands and wings, slap/wrist/snap shots, incoming angles and frame rates. Each frame verifies fixed arm/leg lengths and gloves attached to the shaft, with stationary slapshot contact and continuous phase transitions.

## Presentation and rendering

- Blade positions use the same affine projection as the rendered stick, including handedness, body rotation, stick pitch and the stage aspect ratio. The animation no longer reads skater bounds after painting or paints each skater twice per frame. Physics keeps the existing heading behavior so cosmetic turning cannot change the available passing lanes.
- Playback advances physics at 60Hz with bounded catch-up and pauses when the page is hidden. Tactical variation starts from a scene-specific clock, so replay keeps the same play across different display rates. Ordinary skating paints once per display frame.
- Ice passes retain nearly constant speed through the lane with a restrained soft catch. Ice lighting, contact shadows and jersey surfaces supply depth without obscuring the puck or changing body geometry.
- A pass has a fixed lead point. The receiver glides through the feed with two hands ready, rather than starting the next carrier route during flight. The other two attackers establish their next depth/high triangle around that future receiving position. Defenders read the receiving lane; the goalie starts a restrained anticipation read after a short reaction delay. Skaters turn their heads toward the current or expected puck without changing their blade geometry.
- Shot outcomes are separate from the strongest-unit answer. An open shooting lane, good position, finishing profile, a quick lateral feed and the goalie's recovery improve conversion; lower-rated units can score and the strongest unit can be saved. Outcomes are reproducible on replay. Swept equipment contacts use three-dimensional joint positions and the puck's rising trajectory, so a projected pad or upper body cannot become a flat wall across every shot.
- The net roof has a taller, consistent projection. A rebound resting on it retains an elevated shadow and the final **ON TOP OF NET / NO GOAL** verdict; a goal drops into the cage and lights the goal lamp.
- The goalie mask follows the [Bauer Profile 960 shell and cat-eye cage](https://uk.bauer.com/products/bauer-profile-960-senior-non-certified-goalie-mask-s24). [NHL Auctions documents a Bauer Pro 960 used by Jack Campbell](https://auctions.nhl.com/iSynApp/auctionDisplay.action?auctionId=4826877&sid=1100803). Crown, cheeks and chin form one continuous shell; the curved cage, vents and mounts turn together in the head frame over the collar. This is native projected SVG geometry based on those product photographs.
- The idle scene previews a unit on hover or keyboard focus. The round counter stays on the active play; ratings and the verdict appear when the play finishes. The result remains available until Next rush, and Replay rush repeats the scene without recording a guess. Scene observers are released after playback; resizing repaints the settled scene in rink coordinates.

Run `node tests/rush_presentation.cjs` for independent rendered-blade projection checks, complete mobile/desktop animation playback, delayed verdicts, persistent result review, replay scoring and settled poses at 15/30/60/144Hz, resizing and cancellation cleanup.

Run `node tests/rush_outcomes.cjs` for straight lead-pass lanes and anticipated receiving routes, height-aware pad/upper-body contacts at 15/30/60/144Hz, open-versus-covered shooting opportunities, 60 full animated rush outcomes, mask assembly turns and an elevated net-roof rebound through the final no-goal verdict. Scoring frequency in this regression set describes the stylized game, not an NHL conversion-rate estimate.
