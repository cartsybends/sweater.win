// Presentation regressions: blade projection without layout reads,
// round/replay state, and a completed animation at desktop/mobile sizes.
// Run from the repository root: node tests/rush_presentation.cjs
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('build_sweater.py', 'utf8');
const edges = Object.values(JSON.parse(fs.readFileSync('edge_cache.json')).players);
const careers = JSON.parse(fs.readFileSync('career_cache.json'));
const players = JSON.parse(fs.readFileSync('tests/fixtures/rush_players.json'));
global.EDGE_BYID = new Map(edges.map(p => [Number(p.id), p]));
global.BYID = new Map(players.map(p => [p.id, {...p, car: careers[p.id]?.car || []}]));
global.EDGE_POOL = edges.filter(p => BYID.has(Number(p.id))).map(p => ({...BYID.get(Number(p.id)), edge: p}));
global.EDGE_RUSH_ROLES = ['Carrier', 'Support', 'Finisher'];
global.esc = s => String(s);
global.FALLBACK = '';
global.teamName = s => s;
global.G = {}; global.S = {}; global.game = 'edgerush';
global.document = {hidden: false, querySelectorAll: () => []};
global.matchMedia = () => ({matches: false});
global.edgeSpeedLabel = () => 'MPH';
global.edgeSpeedValue = v => v;
global.edgeFormatSpeed = v => `${v.toFixed(2)} mph`;

class Element {
  constructor() {
    this.attrs = {}; this.nodes = new Map(); this.events = {}; this.isConnected = true;
    this.style = {setProperty(k, v) { this[k] = v; }};
    this.classes = new Set(); this.hidden = false; this.clientWidth = 720; this.clientHeight = 405;
    this.classList = {
      add: (...keys) => keys.forEach(k => this.classes.add(k)),
      remove: (...keys) => keys.forEach(k => this.classes.delete(k)),
      toggle: (k, value) => value ? this.classes.add(k) : this.classes.delete(k),
    };
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  querySelector(k) { if (!this.nodes.has(k)) this.nodes.set(k, new Element()); return this.nodes.get(k); }
  querySelectorAll() { return []; }
  addEventListener(k, fn) { this.events[k] = fn; }
  focus() { document.activeElement = this; }
  getBoundingClientRect() { throw Error('Animation should not read painted skater bounds'); }
  animate() {}
  set innerHTML(v) { this.html = v; this.nodes = new Map(); }
  get innerHTML() { return this.html || ''; }
}
const elements = new Map();
global.$ = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
for (const [start, end] of [
  ['function hash(str)', '// ---- dates:'],
  ['function seeded(seed)', 'function hlExtend'],
  ['function shuffled(arr', '// ---- Draft Day:'],
  ['const edgeValue =', 'function edgePairRandom'],
  ['function edgeRushRoleScores', 'function edgeRushZone'],
  ['function edgeRushChoiceMarkup', 'const EDGE_BUILD_CATS='],
]) vm.runInThisContext(source.slice(source.indexOf(start), source.indexOf(end)));
global.edgeRushEligible = () => EDGE_POOL.filter(p => p.pos !== 'G' && p.edge.speed && p.edge.shot && p.edge.total >= 20);

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

let frameClock = 10000, frameInterval = 1000 / 60;
let frames = 0;
global.performance = {now: () => frameClock};
let scheduled = false, frameQueue = [];
global.requestAnimationFrame = fn => {
  frameQueue.push(fn);
  if (!scheduled) {
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      const callbacks = frameQueue.splice(0);
      frameClock += frameInterval;
      assert(++frames < 16000, 'Animation must finish');
      callbacks.forEach(fn => fn(frameClock));
    });
  }
};
edgeRushWait = async () => true;
// DOM-independent contact locations come from the goalie's rendered geometry.
const renderGoalie = edgeRushRenderGoalie;
edgeRushRenderGoalie = (state, el, w, h) => { el.goalie = state; renderGoalie(state, el, w, h); };
edgeRushGoaliePoint = (el, type) => {
  const p = el.goalie.geometry.find(p => p.kind === (type === 'left' ? 'leftpad' : type === 'right' ? 'rightpad' : type))?.a;
  return p ? {x: p.x / 720, y: p.y / 405} : {x: el.goalie.x, y: el.goalie.y};
};
let observed = 0, disconnected = 0;
global.ResizeObserver = class {observe() { observed++; } disconnect() { disconnected++; }};

(async () => {
  for (const width of [360, 720, 900]) {
    frameInterval = 1000 / ({360: 15, 720: 60, 900: 30}[width]);
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
  frameInterval = 1000 / 144;
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
  assert.equal(observed, disconnected, 'Scene observers are released after each playback');
  g.pending = true; g.review = {r: round, picked: pick, correct: true};
  edgeRushCancelAnimation();
  assert.equal(g.pending, false); assert.equal(g.review, null, 'Leaving Rush clears the pending review');
  g.pending = true;
  const canceled = edgeRushAnimate(round, pick, true);
  queueMicrotask(() => edgeRushCancelAnimation());
  await canceled;
  assert.equal(g.pending, false); assert.equal(g.review, null, 'A canceled playback cannot reopen the old result');
  console.log({projections, completedAnimations: 4, frames, replayRecordedGuesses: S.edgerush.guesses.length, observersReleased: disconnected});
})().catch(error => { console.error(error); process.exitCode = 1; });
