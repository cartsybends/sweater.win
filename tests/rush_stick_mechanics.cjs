// Rigid blade proportions, distinct shot mechanics and ice-contact timing.
// Run from the repository root: node tests/rush_stick_mechanics.cjs
const assert = require('node:assert/strict');
const {Element} = require('./helpers/rush_runtime.cjs');
const matrix = node => node.attrs.transform.slice(7, -1).split(/\s+/).map(Number);
const point = (m, x, y) => ({x: m[0]*x+m[2]*y+m[4], y: m[1]*x+m[3]*y+m[5]});
const distance = (a, b) => Math.hypot(a.x-b.x, a.y-b.y);
const near = (a, b, message) => assert(Math.abs(a-b) < 1e-7, message);
let bladePoses = 0, shotSamples = 0;
function checkBlade(a, defender = false, now = 0) {
  a.el = new Element(); delete a.stickEl; delete a.skaterRig;
  edgeRushRenderSkater(a, defender, now);
  const root = !defender && a.state === 'shooting' ? a.skaterRig['shot-stick'] : a.stickEl;
  const blade = matrix(root.querySelector('.rush-stick-blade-rig'));
  const shaft = matrix(root.querySelector('.rush-stick-shaft-rig'));
  // Equal scale and perpendicular axes: a blade can rotate, but cannot shear
  // or inherit an elongated silhouette from the shaft's height projection.
  near(Math.hypot(blade[0],blade[1]), 48/78, 'Every blade has the same length scale');
  near(Math.hypot(blade[2],blade[3]), 48/78, 'Every blade has the same thickness scale');
  near(blade[0]*blade[2]+blade[1]*blade[3], 0, 'A blade remains rigid');
  assert(distance(point(blade,55,21), point(shaft,55,21)) < 1e-7, 'The heel stays attached to the shaft');
  if (a.state === 'shooting') {
    assert.deepEqual(blade, matrix(a.stickEl.querySelector('.rush-stick-blade-rig')), 'Changing paint layers cannot change the blade');
  }
  if (defender) {
    const tip = point(blade,64,22.5), read = edgeRushDefenderStick(a,now);
    assert(Math.hypot((read.x-a.x)*720-tip.x+39,(read.y-a.y)*405-tip.y+33) < 1e-7, 'A stick check reads the rendered blade');
  }
  bladePoses++;
}
for (const hand of [-1,1]) for (const angle of [-58,-24,0,24,58]) for (const pitch of [0,35,64,96]) {
  checkBlade({x:.5,y:.5,hand,stickAngle:angle,stickPitch:pitch});
}
for (const angle of [Math.PI-.6,Math.PI,Math.PI+.6]) for (const now of [1000,1150,1300]) {
  checkBlade({x:.6,y:.5,stickAim:angle,pokeAt:1000,mode:'gap'},true,now);
}

for (const hand of [-1,1]) for (const wing of [-1,1]) for (const type of ['snap','wrist','slap']) {
  const a = {x:.62,y:.5+wing*.20,rot:wing*12,hand,state:'shooting',releaseType:type,
    shotTargetRot:wing*12,stickAngle:hand*8,stickX:-2,stickY:hand*2,wristRoll:.25,gripX:34};
  edgeRushBeginWindup(a);
  const first = edgeRushBladeGrip(a), planted = a.shotPuckIce && {...a.shotPuckIce};
  const peak = type === 'slap' ? .60 : type === 'snap' ? .64 : .36;
  edgeRushShootingPose(a,peak);
  const loaded = edgeRushBladeGrip(a), wideGrip = a.gripX;
  assert(a.wristRoll > .65, 'The wrists close to load the shot');
  assert(a.shotWeight < 0, 'The player loads before transferring weight');
  if (type === 'snap') {
    assert(loaded.x < first.x-8 && distance(loaded,{x:0,y:0}) < distance(first,{x:0,y:0})-7,
      'A snap shot pulls the puck toward the body before the quick release');
    assert(a.gripX < 34, 'The lower hand slides inward during the pull');
    assert.equal(a.stickPitch,0); assert.equal(a.shotLift,0, 'The pulled puck stays on the ice');
  } else if (type === 'wrist') {
    assert(loaded.x < first.x-10, 'A wrist shot loads the puck behind the release point');
    assert.equal(a.stickPitch,0); assert.equal(a.shotLift,0, 'The cupped puck stays on the ice');
  } else {
    assert(a.stickPitch >= 90 && a.shotLift >= 17, 'The slapshot has a high backswing');
    assert(a.gripX >= 39, 'The lower hand widens to load a slapshot');
    assert.equal(a.shotFlex,0, 'The stick does not flex in midair');
    assert.deepEqual(a.shotPuckIce,planted, 'The puck stays planted through the backswing');
  }
  let last = null, maxFlex = 0;
  // Dense sampling also catches a pose jump at the downswing/contact boundary.
  for (let i = 0; i <= 500; i++) {
    const t=i/500; edgeRushShootingPose(a,t);
    const blade=edgeRushBladeGrip(a), top=edgeRushSkaterGrip(a,10,5+4*16/49);
    if (last) {
      assert(distance(blade,last.blade)<2.5, 'Blade movement is continuous through contact');
      assert(distance(top,last.top)<1, 'The hands cannot jump between shot phases');
    }
    if (type === 'slap' && a.shotFlex>.01) {
      assert.equal(a.stickPitch,0, 'Slapshot flex starts after the blade reaches the ice');
      const p=edgeRushStick(a);
      assert(Math.hypot((p.x-planted.x)*720,(p.y-planted.y)*405)<3.1, 'Compression occurs just behind the planted puck');
    }
    maxFlex=Math.max(maxFlex,a.shotFlex);last={blade,top};shotSamples++;
    if (i%10===0) checkBlade(a);
  }
  assert(maxFlex>.70, 'Every shot visibly loads the lower shaft');
  const release=edgeRushBladeGrip(a), top=edgeRushSkaterGrip(a,10,5+4*16/49);
  assert(release.x>loaded.x+8, 'A snap or wrist shot sweeps forward into release');
  assert(a.wristRoll<-.65 && a.shotWeight>.99, 'Release rolls the wrists and transfers the weight');
  if (planted) assert(edgeRushDistance(edgeRushStick(a),planted)<1e-8, 'A slapshot releases from the planted puck');
  edgeRushShootingPose(a,0,true);
  assert(distance(top,edgeRushSkaterGrip(a,10,5+4*16/49))<1e-7, 'Release joins follow-through without a hand jump');
  assert(distance(release,edgeRushBladeGrip(a))<1e-7, 'The blade is continuous at release');
  if (type === 'snap') assert(a.gripX>wideGrip, 'The lower hand drives outward after the pull');
  edgeRushShootingPose(a,type==='slap'?.30:type==='snap'?.18:.24,true);checkBlade(a);
  assert(a.stickPitch>(type==='slap'?60:type==='snap'?20:30), 'The released blade rises into follow-through');
}
console.log({bladePoses,shotSamples,shootingHands:2,wings:2});
