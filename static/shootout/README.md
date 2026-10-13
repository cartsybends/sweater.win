# Shootout artwork and motion

`scene.svg`, `styles.css`, and `animation.js` are embedded into the generated page by `build_sweater.py`. The scene is self-contained, including the stick image, and its initial attributes are the ready pose. Run `node tests/shootout.cjs` after changing the artwork or motion.

The stick has a plain, unbranded dark finish derived from the supplied photograph. The embedded WebP's SHA-256 is `60f627d29b80aec4d12bfc010d5d41967643535e22adfbf4577b3b6f732cc4c4`. `shStickPhoto` maps the finish into the original 1000 × 1000 coordinate system; `shStickTrace` retains the reference silhouette. Preserve the shaft, shoulder transition, paddle, curved heel, broad blade, and rounded toe together.

`SH_STICK` describes the source grip, scale, and convex bounds. `shootStick()` produces one affine projection for the complete stick. Dropping pitches its plane forward so the blade stays above the ice; a high blocker save lifts the stick with the hand. Do not animate or resize the blade separately from the shaft and paddle.

Each sleeve is one closed, tapered silhouette draped over a single cubic curve. Its yoke, stripe, and fabric folds are clipped to that same silhouette. Shoulder roots stay inside the torso, and padded palms, thumbs, and cuffs connect the sleeves to the equipment. The arm solver preserves upper-arm and forearm lengths in three dimensions; elbow depth allows natural forearm foreshortening as the blocker rises. Keep the blocker near upright rather than twisting its board sideways, and check intermediate frames for pinching and self-intersection.

Playback runs at 1.6× the simulation clock, giving the puck a 300 ms flight to the goal plane. Keeper movement, impact, net response, recovery, and completion all use the same clock, so faster shots cannot outrun their save animation.

The save motion was reviewed against these official NHL clips, frame by frame, and adapted to the site's frontal illustrated view:

- [Hellebuyck's blocker save](https://www.nhl.com/video/chi-wpg-hellebuyck-with-a-great-save-against-ryan-greene-6384316112112)
- [Bobrovsky's blocker save](https://www.nhl.com/video/sergei-bobrovsky-with-a-spectacular-goalie-save-vs-dallas-stars-6348790340112)
- [Shesterkin's glove save](https://www.nhl.com/video/nyr-fla-shesterkin-with-a-great-save-against-a-j-greer-6387179663112)

[IIHF high-blocker guidance](https://www.iihf.com/en/coaching/19494/high-blocker) also informed hand presentation and wrist rotation. The successful save uses a small lateral weight shift; a wrong read moves farther away so scored pucks clear the pads. After a save, the hands recover smoothly while the glove retains a caught puck.

The tests cover 30,100 shot frames, five targets, all keeper pairs, net/post/ice contacts, readable puck scaling, four playback frame rates, stored results, interruption, keyboard targets, and reduced motion. They also check 5,005 rig poses for arm reversal, cuff attachment, stick rigidity, grounded pads, and sleeve outline intersections.
