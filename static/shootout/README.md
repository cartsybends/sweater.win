# Shootout artwork and motion

`scene.svg`, `styles.css`, and `animation.js` are embedded into the generated page by `build_sweater.py`. The scene is self-contained, including the stick image, and its initial attributes are the ready pose. Run `node tests/shootout.cjs` after changing the artwork or motion.

The stick uses the user's supplied `Warrior-Ritual-M3-RTL-Pro-Goalie-Stick-1125817775.png` photograph, unchanged. Its SHA-256 is `48d325a840b917bb07a15c93b1f16cfb90b7c1ccabc77949de96e4d5e1c5c2cb`. `shStickPhoto` retains the original 1000 × 1000 image; `shStickTrace` clips it to a silhouette traced at the source image resolution. Preserve the shaft, shoulder transition, paddle graphics, curved heel, broad blade, and rounded toe together. The photograph must not be replaced with invented equipment graphics.

`SH_STICK` describes the source grip, scale, and convex bounds. `shootStick()` produces one affine projection for the complete stick. Dropping pitches its plane forward so the blade stays above the ice; a high blocker save lifts the stick with the hand. Do not animate or resize the blade separately from the shaft and paddle.

Each sleeve is one closed, tapered silhouette draped over a single cubic curve. Its stripe and fabric folds are clipped to that same silhouette. There are no independent upper-arm, forearm, or elbow-cap objects. Keep the hand attached to the equipment's actual cuff, preserve the elbow's bend branch through both the save and recovery, and check intermediate frames for pinching and self-intersection.

The save motion was reviewed against these official NHL clips, frame by frame, and adapted to the site's frontal illustrated view:

- [Hellebuyck's blocker save](https://www.nhl.com/video/chi-wpg-hellebuyck-with-a-great-save-against-ryan-greene-6384316112112)
- [Bobrovsky's blocker save](https://www.nhl.com/video/sergei-bobrovsky-with-a-spectacular-goalie-save-vs-dallas-stars-6348790340112)
- [Shesterkin's glove save](https://www.nhl.com/video/nyr-fla-shesterkin-with-a-great-save-against-a-j-greer-6387179663112)

[IIHF high-blocker guidance](https://www.iihf.com/en/coaching/19494/high-blocker) also informed hand presentation and wrist rotation. The successful save uses a small lateral weight shift; a wrong read moves farther away so scored pucks clear the pads. After a save, the hands recover smoothly while the glove retains a caught puck.

The tests cover 30,100 shot frames, five targets, all keeper pairs, net/post/ice contacts, readable puck scaling, four playback frame rates, stored results, interruption, keyboard targets, and reduced motion. They also check 5,005 rig poses for arm reversal, cuff attachment, stick rigidity, grounded pads, and sleeve outline intersections.
