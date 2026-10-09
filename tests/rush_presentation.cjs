// Presentation regressions: blade projection without layout reads,
// round/replay state, and a completed animation at desktop/mobile sizes.
// Run from the repository root: node tests/rush_presentation.cjs
const assert = require('node:assert/strict');
const {Element, setFrameRate, counters} = require('./helpers/rush_runtime.cjs');

// Independently compose the rendered CSS transform, including SVG letterboxing.
// Puck contact must survive handedness, body rotation, stick pitch and resizing.
let projections = 0;
for (const width of [360, 720, 898]) for (const hand of [-1, 1]) for (const rot of [-24, 0, 24]) for (const pitch of [0, 35, 58]) {
  const height = width * 405 / 720 - 1;
  const a = {x: .5, y: .5, hand, rot, stickPitch: pitch, stickAngle: hand * 22, stickX: -4, stickY: hand * 3, el: new Element()};
  edgeRushRenderAgent(a, width, height);
  const m = a.stickEl.style.transform.match(/-?[\d.]+/g).map(Number);
  const local = {x: (64 - 39) * 48 / 78, y: (22.5 - 15) * 48 / 78};
  const lx = 19 + m[4] + local.x * m[0] + local.y * m[2];
  const ly = 2 + m[5] + local.x * m[1] + local.y * m[3];
  const angle = rot * Math.PI / 180, scale = width / 720;
  const expected = {x: a.x + scale * (lx * Math.cos(angle) - ly * Math.sin(angle)) / width,
    y: a.y + scale * (lx * Math.sin(angle) + ly * Math.cos(angle)) / height};
  const blade = edgeRushStick(a);
  assert(Math.hypot((blade.x - expected.x) * width, (blade.y - expected.y) * height) < 1e-6);
  projections++;
}

const target = edgeRushRandom(seeded(hash('rush-presentation')));
assert(target);
const round = target.rounds[0], pick = round.a;
S.edgerush = {target, guesses: [String(pick)], over: false};
const g = G.edgerush;
g.pending = true; g.lastCorrect = true;
g.render(target, S.edgerush);
assert.equal($('erRound').textContent, '1 / 5', 'HUD must keep the round being animated');
assert.equal($('erScore').textContent, '0', 'Verdict appears after the play');
assert(!$('erChoices').innerHTML.includes('rush-line-rating'), 'Do not reveal the answer before the shot');

(async () => {
  for (const width of [360, 720, 900]) {
    setFrameRate({360: 15, 720: 60, 900: 30}[width]);
    $('erStage').clientWidth = width; $('erStage').clientHeight = width * 405 / 720;
    g.pending = true; g.review = null; g.lastCorrect = true;
    await edgeRushAnimate(round, pick, true);
    assert.equal(g.pending, false);
    assert(g.review && $('erStage').classes.has('review'), 'The final scene stays available for review');
    assert.equal($('erRound').textContent, '1 / 5');
    assert.equal($('erScore').textContent, '1');
    assert.equal($('erReview').hidden, false);
    assert($('erChoices').innerHTML.includes('rush-line-rating'));
  }
  const guessesBefore = [...S.edgerush.guesses];
  const verdictBefore = $('erCalloutMain').textContent;
  const actorId = edgeRushLine(round.lines[pick].ids).roles[0];
  const poseBefore = $('erActors').querySelector(`[data-rush-id="${actorId}"]`).style.transform;
  setFrameRate(144);
  g.pending = true; g.replaying = true; g.render(target, S.edgerush);
  assert.equal($('erScore').textContent, '1', 'Replay cannot rewind the score');
  await edgeRushAnimate(round, pick, true);
  assert.deepEqual(S.edgerush.guesses, guessesBefore, 'Replay must not record another guess');
  assert.equal($('erCalloutMain').textContent, verdictBefore, 'Replay retains the outcome');
  const before = poseBefore.match(/-?[\d.]+/g).map(Number);
  const after = $('erActors').querySelector(`[data-rush-id="${actorId}"]`).style.transform.match(/-?[\d.]+/g).map(Number);
  assert(before.every((v, i) => Math.abs(v - after[i]) < .01), 'Replay retains the settled play at the same frame rate');
  $('erStage').clientWidth = 420; $('erStage').clientHeight = 420 * 405 / 720;
  g.repaint();
  const transform = $('erActors').querySelector(`[data-rush-id="${edgeRushLine(round.lines[pick].ids).roles[0]}"]`).style.transform;
  assert(transform.includes(`scale(${420 / 720})`), 'Settled actors resize with the rink');
  $('erNext').events.click();
  assert.equal(g.review, null);
  assert.equal($('erRound').textContent, '2 / 5');
  assert.equal($('erReview').hidden, true);
  assert($('erStage').classes.has('idle'));
  assert.equal(counters().observed, counters().disconnected, 'Scene observers are released after each playback');
  g.pending = true; g.review = {r: round, picked: pick, correct: true};
  edgeRushCancelAnimation();
  assert.equal(g.pending, false); assert.equal(g.review, null, 'Leaving Rush clears the pending review');
  g.pending = true;
  const canceled = edgeRushAnimate(round, pick, true);
  queueMicrotask(() => edgeRushCancelAnimation());
  await canceled;
  assert.equal(g.pending, false); assert.equal(g.review, null, 'A canceled playback cannot reopen the old result');
  console.log({projections, completedAnimations: 4, frames: counters().frames, replayRecordedGuesses: S.edgerush.guesses.length, observersReleased: counters().disconnected});
})().catch(error => { console.error(error); process.exitCode = 1; });
