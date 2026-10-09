// Lead passes, height-aware saves, earned scoring, mask turns and net-roof verdicts.
// Run from repository root: node tests/rush_outcomes.cjs
const assert = require('node:assert/strict');
const {Element, setFrameRate, counters} = require('./helpers/rush_runtime.cjs');
const ids = edgeRushLine(edgeRushRandom(seeded(hash('rush-outcomes'))).rounds[0].lines[0].ids).roles;

// A feed uses the receiver's future position, with a straight lane until the catch.
const agents = ids.map((id, i) => edgeRushAgent(id, EDGE_RUSH_ROLES[i], [.67, .73, .61][i], [.30, .69, .53][i]));
const [carrier, receiver] = agents;
receiver.vx = .065; receiver.vy = -.025;
const puck = {mode: 'carry', owner: carrier, x: carrier.x, y: carrier.y};
assert(edgeRushPass(puck, receiver, .28));
assert(puck.receiveX > receiver.x && puck.receiveY < receiver.y);
const to = {x: puck.toX, y: puck.toY}, plan = {start: 10000, passes: 1};
edgeRushPlanAttack(puck, agents, [], {x: 628 / 720, y: .5}, plan, 11000);
assert.equal(receiver.intent, 'receive', 'The receiver stays committed to the incoming puck');
assert(agents.filter(a => a !== receiver).every(a => a.routeOwner === receiver.id));
assert(agents.filter(a => a !== receiver).some(a => a.intent === 'high-outlet'));
let passFrames = 0;
for (let i = 0; i < 18; i++) {
  const dt = 1 / 60; edgeRushHandle(receiver, false, dt); edgeRushSteer(receiver, dt);
  edgeRushUpdatePuck(puck, dt);
  if (puck.mode === 'pass' && puck.elapsed / puck.duration <= .80) {
    const t = puck.elapsed / puck.duration;
    assert(Math.hypot((puck.x - rushLerp(puck.fromX, to.x, t)) * 720, (puck.y - rushLerp(puck.fromY, to.y, t)) * 405) < .001);
  }
  passFrames++;
  if (puck.mode === 'carry') break;
}
assert.equal(puck.owner, receiver); assert.equal(receiver.receiving, null);
assert(edgeRushDistance(puck, edgeRushStick(receiver)) < 1e-8);

// At the same projected location, ice shots hit low pads and raised shots clear them.
const pad = {kind: 'leftpad', a: {x: 627, y: 195}, b: {x: 627, y: 210}, r: 5,
  iceA: {x: 627, y: 195, z: 3}, iceB: {x: 627, y: 210, z: 3}};
for (const fps of [15, 30, 60, 144]) {
  for (const [height, hitsPad] of [[.06, true], [.90, false]]) {
    const p = {x: 600 / 720, y: .5};
    edgeRushShot(p, 670 / 720, .5, .18, {height}); p.goalieGeometry = [pad];
    let done = false;
    for (let i = 0; i < fps; i++) { done = edgeRushUpdatePuck(p, 1 / fps); if (done) break; }
    assert(done); assert.equal(!!p.goalieHit, hitsPad, `Pad height at ${fps}Hz`);
  }
}
const highChest = {...pad, kind: 'chest', iceA: {...pad.iceA, z: 58}, iceB: {...pad.iceB, z: 58}};
assert.equal(edgeRushGoalieContact(600, 202.5, 670, 202.5, [highChest], 1, 1), null, 'Projected upper-body art cannot block an ice lane');

// Better positioning and an open lane earn more goals across the same seed set.
const shooter = edgeRushAgent(ids[0], 'Finisher', .79, .5);
shooter.releaseType = 'snap'; shooter.receiveAt = 10000;
const goalie = {x: 628 / 720, y: .5, vy: 0};
const profile = edgeRushShotProfile(shooter, {rating: 70}, shooter, true);
const blocked = [{x: .83, y: edgeRushStick(shooter).y}];
let openGoals = 0, blockedGoals = 0;
for (let seed = 0; seed < 500; seed++) {
  const open = edgeRushShotOutcome(shooter, [], goalie, profile, seed, 12000);
  const covered = edgeRushShotOutcome(shooter, blocked, goalie, profile, seed, 12000);
  assert(open.chance > covered.chance + .20);
  openGoals += ['goal', 'postin'].includes(open.outcome);
  blockedGoals += ['goal', 'postin'].includes(covered.outcome);
}
assert(openGoals > blockedGoals * 2);

// The continuous shell and attached cage both turn with the head over the collar.
const maskPaths = ['shell', 'opening', 'cage', 'vents', 'mounts'];
const poses = [-55, 0, 55].map(yaw => {
  const el = new Element(), g = {x: 628 / 720, y: .5, headYaw: yaw, upperYaw: 0};
  edgeRushRenderGoalie(g, el, 720, 405);
  assert(g.geometry.every(p => Number.isFinite(p.iceA.z) && Number.isFinite(p.iceB.z)));
  const mask = el.querySelector('.rush-g-mask');
  assert.equal(mask.attrs.transform, '');
  return Object.fromEntries(maskPaths.map(p => [p, mask.querySelector('.rush-mask-' + p).attrs.d]));
});
assert(poses.every(p => p.shell.endsWith('Z')));
for (const part of maskPaths) assert(new Set(poses.map(p => p[part])).size === 3, `${part} turns with the head`);

// A descending rebound rests on the elevated roof, never inside the goal.
const roofPuck = {mode: 'saveflight', airborne: true, x: .95, y: .5, z: 1.30, vz: -.8, vx: .008, vy: 0};
for (let i = 0; i < 120 && roofPuck.mode !== 'netrest'; i++) edgeRushUpdatePuck(roofPuck, 1 / 60);
assert.equal(roofPuck.mode, 'netrest'); assert.equal(roofPuck.z, 1);
const roofEl = new Element(); edgeRushRenderPuck(roofPuck, roofEl, 720, 405);
assert(roofEl.classes.has('on-roof'));
const projected = roofEl.style.transform.match(/-?[\d.]+/g).map(Number);
assert(roofPuck.y * 405 - projected[2] >= 17, 'Roof elevation remains visually distinct from the ice');

(async () => {
  setFrameRate(30);
  const results = [], totals = {goal: 0, save: 0, post: 0, crossbar: 0, postin: 0};
  for (let day = 0; day < 6; day++) {
    const target = edgeRushRandom(seeded(hash(`rush-outcomes-${day}`)));
    for (let roundIndex = 0; roundIndex < 5; roundIndex++) {
      const round = target.rounds[roundIndex];
      for (const picked of [round.a, (round.a + 1) % round.lines.length]) {
        S.edgerush = {target, guesses: Array(roundIndex).fill('0').concat(String(picked)), over: false};
        G.edgerush.pending = true; G.edgerush.render(target, S.edgerush);
        await edgeRushAnimate(round, picked, picked === round.a);
        const result = G.edgerush.review.result;
        assert.equal($('erCalloutMain').textContent === 'GOAL', ['goal', 'postin'].includes(result.outcome));
        assert.equal($('erStage').classes.has('goal'), ['goal', 'postin'].includes(result.outcome), 'Only a puck that entered the cage lights the goal lamp');
        results.push({...result, correct: picked === round.a}); totals[result.outcome]++;
      }
    }
  }
  const goals = results.filter(r => ['goal', 'postin'].includes(r.outcome));
  assert(goals.length >= 6, 'Full animated rushes must retain attainable scoring');
  assert(goals.length < results.length * .8, 'Good saves remain part of the game');
  assert(goals.some(r => !r.correct), 'A lower-rated unit can earn a goal from a good play');
  assert(results.some(r => r.correct && !['goal', 'postin'].includes(r.outcome)), 'Best-profile verdict does not guarantee a goal');

  // Drive a roof rebound through the complete scene and verify the final verdict.
  const originalOutcome = edgeRushShotOutcome, originalProfile = edgeRushShotProfile, originalDeflect = edgeRushSaveDeflect;
  edgeRushShotOutcome = () => ({outcome: 'save', chance: .4, quality: .7});
  edgeRushShotProfile = (...args) => ({...originalProfile(...args), save: 'blocker', variant: 'blocker-high', height: .85});
  edgeRushSaveDeflect = p => Object.assign(p, {mode: 'saveflight', airborne: true, x: .95, y: .5, z: 1.3, vz: -.8, vx: .008, vy: 0, roofBounces: 0});
  const target = edgeRushRandom(seeded(hash('rush-roof-verdict'))), round = target.rounds[0];
  S.edgerush = {target, guesses: [String(round.a)], over: false}; G.edgerush.pending = true;
  G.edgerush.render(target, S.edgerush); await edgeRushAnimate(round, round.a, true);
  assert.equal($('erCalloutMain').textContent, 'ON TOP OF NET');
  assert($('erCalloutSub').textContent.startsWith('NO GOAL'));
  assert.equal($('erPhase').textContent, 'ON TOP OF NET · NO GOAL');
  assert(!$('erStage').classes.has('goal')); assert(G.edgerush.review.result.roof);
  edgeRushShotOutcome = originalOutcome; edgeRushShotProfile = originalProfile; edgeRushSaveDeflect = originalDeflect;
  assert.equal(counters().observed, counters().disconnected);
  console.log({passFrames, openGoals, blockedGoals, animatedRushes: results.length, totals, roofVerdict: 'NO GOAL', frames: counters().frames});
})().catch(error => {console.error(error); process.exitCode = 1;});
