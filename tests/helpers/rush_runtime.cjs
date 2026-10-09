const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.env.RUSH_SOURCE || 'build_sweater.py', 'utf8');
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
      assert(++frames < 250000, 'Animation must finish');
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


module.exports = {source, Element, setFrameRate: fps => {frameInterval = 1000 / fps;}, counters: () => ({frames, observed, disconnected})};
