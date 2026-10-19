import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { FACE_SWAP_MODEL as model } from '../static/face-swap/model.mjs';
import worker, { scoreGame } from '../backend/src/existing-api.mjs';

const bank = JSON.parse(fs.readFileSync('static/face-swap/puzzles.json')).puzzles;
const schedule = JSON.parse(fs.readFileSync('schedule.json'));
const puzzle = bank[0], [a, b] = puzzle.players;
const misses = Object.values(schedule.players).map(p => p.id).filter(id => !puzzle.players.includes(id)).slice(0, 5);
let checks = 0;
function test(name, run) { run(); checks++; console.log('PASS', name); }
const plain = value => JSON.parse(JSON.stringify(value));

test('either identity can be found first; a partial answer is not a win and uses no miss', () => {
  for (const order of [[a, b], [b, a]]) {
    const partial = model.progress(puzzle, order.slice(0, 1));
    assert.equal(partial.over, false); assert.equal(partial.wrong, 0); assert.equal(partial.left, 5);
    assert.deepEqual(model.result(puzzle, order), { won: true, tries: 2, points: 10 });
  }
  assert.throws(() => model.result(puzzle, [a]), /finished/);
});
test('four misses still allow both correct names; five misses reveal the pair and score zero', () => {
  for (const guesses of [[...misses.slice(0, 4), a, b], [b, ...misses.slice(0, 4), a]]) {
    assert.deepEqual(model.result(puzzle, guesses), { won: true, tries: 6, points: 2 });
  }
  assert.deepEqual(model.result(puzzle, misses), { won: false, tries: 5, points: 0 });
  assert.deepEqual(model.result(puzzle, [a, ...misses]), { won: false, tries: 6, points: 0 });
  assert.equal(model.progress(puzzle, [a, ...misses]).found.length, 1);
});
test('duplicates, malformed guesses, and answers after completion are rejected', () => {
  for (const guesses of [[a, a], [misses[0], misses[0]], [String(a)], [null], [NaN], [a, b, misses[0]], [...misses, a]]) {
    assert.throws(() => model.progress(puzzle, guesses));
  }
  for (const players of [[a, a], [a], [a, 'oops'], []]) assert.throws(() => model.progress({ players }, []));
});
test('every bank pairing has identical browser and server scoring in either order at every hint level', () => {
  const data = { ...schedule, faceswap_puzzles: bank };
  for (const p of bank) for (const order of [p.players, p.players.slice().reverse()]) for (let wrong = 0; wrong <= 4; wrong++) {
    const other = Object.values(schedule.players).map(x => x.id).filter(id => !p.players.includes(id)).slice(0, wrong);
    const guesses = [order[0], ...other, order[1]];
    assert.deepEqual(scoreGame('faceswap', { id: p.id }, guesses, data), { won: true, tries: wrong + 2, points: 10 - wrong * 2 });
  }
  assert.throws(() => scoreGame('faceswap', { id: 'missing' }, [a, b], data), /missing/);
  assert.throws(() => scoreGame('faceswap', { id: puzzle.id }, [a], data), /finished/);
});

function runtime(storage = new Map()) {
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', hidden: false,
      complete: false, naturalWidth: 0, dataset: {}, attributes: {}, classList: { toggle() {} },
      setAttribute(k, v) { this.attributes[k] = v; } });
    return elements.get(id);
  };
  const players = Object.values(schedule.players).map(p => ({ ...p }));
  const state = { target: null, guesses: [], over: false, day: '2026-10-19', opts: {} };
  const context = vm.createContext({ G: {}, S: { faceswap: state }, game: 'faceswap', mode: 'daily',
    BYID: new Map(players.map(p => [p.id, p])), PLAYERS: players,
    FACE_SWAP_MODEL: model, DAILY: { faceswap: { '2026-10-19': { id: bank[1].id } } },
    $, esc: String, posName: p => p.pos === 'G' ? 'Goalie' : p.pos === 'D' ? 'Defenceman' : 'Forward',
    countryName: p => p, teamName: p => p, logo: p => `logo-${p}`, FALLBACK: '',
    dayKey: () => '2026-10-19', hash: () => 0, toast() {}, updateLabels() {},
    shuffled: rows => rows.slice().reverse(),
    store: { get: key => storage.has(key) ? plain(storage.get(key)) : null,
      set: (key, value) => storage.set(key, plain(value)) },
  });
  vm.runInContext(fs.readFileSync('static/face-swap/game.js', 'utf8').replace('/*__FACE_SWAP_PUZZLES__*/[]', JSON.stringify(bank)), context);
  const g = context.G.faceswap;
  function start(p = puzzle) { state.guesses = []; state.over = false; state.opts = {}; state.target = g.prepareTarget(p, state.opts); g.reset(state.target); g.render(state.target, state); }
  function guess(id) { const result = g.guess(state.target, id, true); if (result !== null) { state.guesses.push(id); state.over = g.isDone(state.target, state.guesses); g.render(state.target, state); } return result; }
  return { context, storage, state, $, g, start, guess, load() { $('fsImage').onload(); } };
}

test('the photo must load before an attempt; a failed image can be retried without losing a miss', () => {
  const r = runtime(); r.start(); assert.equal(r.guess(a), null); assert.equal(r.state.guesses.length, 0);
  r.$('fsImage').onerror(); assert.equal(r.g.failed, true); assert.equal(r.$('fsRetry').hidden, false);
  r.$('fsRetry').onclick(); assert.equal(r.state.guesses.length, 0);
  r.load(); assert.equal(r.g.ready, true); assert.equal(r.$('fsPhotoMessage').hidden, true);
  r.guess(b); assert.equal(r.state.over, false); assert.equal(r.$('fsProgress').textContent, '1 / 2 identified');
  assert.equal(r.$('fsMisses').attributes['aria-label'], '0 of 5 misses used');
});
test('identity cards keep names hidden; only misses advance position, age, country, and team clues', () => {
  const r = runtime(); r.start(); r.load();
  for (const id of [a, b]) assert(!r.$('fsIdentities').innerHTML.includes(schedule.players[id].name));
  const labels = ['Position', 'Age', 'Country', 'Team'];
  for (let i = 0; i < 4; i++) {
    r.guess(misses[i]); const html = r.$('fsIdentities').innerHTML;
    labels.forEach((label, index) => assert.equal(html.includes(`<small>${label}</small>`), index <= i));
  }
  r.guess(b); assert(r.$('fsIdentities').innerHTML.includes(schedule.players[b].name));
  assert(!r.$('fsIdentities').innerHTML.includes(schedule.players[a].name));
  const before = r.state.guesses.length; assert.equal(r.guess(b), null); assert.equal(r.state.guesses.length, before);
  r.guess(a); assert.equal(r.state.over, true); assert.equal(r.$('fsGuessing').hidden, true);
  assert(r.$('fsIdentities').innerHTML.includes(schedule.players[a].name));
  assert.equal(r.g.score(r.state.target, r.state.guesses), 2);
});
test('a loss reveals both original players, including a previously unidentified player', () => {
  const r = runtime(); r.start(); r.load(); r.guess(a); misses.forEach(id => r.guess(id));
  assert.equal(r.state.over, true); const html = r.$('fsIdentities').innerHTML;
  assert(html.includes(schedule.players[a].name)); assert(html.includes(schedule.players[b].name));
  assert(html.includes('Revealed')); assert.equal(r.g.score(r.state.target, r.state.guesses), 0);
});
test('daily assignments are stable, saved clues survive roster refreshes, and sharing contains no answers', () => {
  const r = runtime(); assert.equal(r.g.daily('2026-10-19').id, bank[1].id); r.start(); r.load();
  const opts = plain(r.state.opts), team = r.state.target.people[0].team;
  r.context.BYID.get(a).team = 'CHANGED';
  const restored = r.g.prepareTarget(puzzle, opts); assert.equal(restored.people[0].team, team);
  assert.equal(vm.runInContext("fsAge('1997-10-20', '2026-10-19')", r.context), 28);
  assert.equal(vm.runInContext("fsAge('1997-10-20', '2026-10-20')", r.context), 29);
  const share = r.g.shareText(puzzle, { guesses: [b, a] }, 1, '\nhttps://sweater.win/share/#faceswap');
  assert(share.includes('2/2 players')); for (const id of [a, b]) assert(!share.includes(schedule.players[id].name));
});
test('Unlimited visits every portrait before repeating and resumes the same rotation after reload', () => {
  const r = runtime(), first = r.g.random().id;
  const reload = runtime(r.storage), ids = [first];
  for (let i = 1; i < bank.length; i++) ids.push(reload.g.random().id);
  assert.equal(new Set(ids).size, bank.length);
  assert.notEqual(reload.g.random().id, ids.at(-1));
});
test('Face Swap replaces the retired interface and is a normal playable hub mode', () => {
  assert.equal(runtime().g.kind, 'score', 'Daily history, statistics, and analytics must record points');
  const source = fs.readFileSync('build_sweater.py', 'utf8');
  assert(!source.includes('id="view-blur"')); assert(!source.includes('G.blur ='));
  assert(source.includes('["faceswap", "👥"')); assert(!/MAINTENANCE_GAMES = new Set\([^\n]*faceswap/.test(source));
  assert(source.includes('id === "blur") { id = "faceswap"'));
});
// Verify the real result endpoint selects the published pair, recomputes points,
// rejects unfinished runs, and keeps the first result when a client retries.
const uid = crypto.randomUUID(), secret = 'a'.repeat(64), rows = new Map();
const secretHash = Buffer.from(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(secret))).toString('hex');
const env = { SCHEDULE_URL: 'https://puzzles.example.test/schedule.json', DB: { prepare(sql) { return { bind(...args) { return {
  async first() { return sql.includes('secret_hash') ? (args[0] === uid ? { secret_hash: secretHash } : null) : rows.get(args.slice(0, 3).join(':')); },
  async run() {
    const [who, game, day, won, tries, points] = args, key = [who, game, day].join(':');
    if (rows.has(key)) return { meta: { changes: 0 } };
    rows.set(key, { won, tries, points }); return { meta: { changes: 1 } };
  }
}; } }; } } };
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async url => {
    assert.equal(url, env.SCHEDULE_URL);
    return new Response(JSON.stringify({ faceswap_puzzles: bank, faceswap_days: { [today]: { id: puzzle.id } } }));
  };
  const request = guesses => worker.fetch(new Request('https://api.example.test/api/result', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid, secret, game: 'faceswap', day: today, guesses, points: 99999, won: true }) }), env);
  assert.equal((await request([a])).status, 400); assert.equal(rows.size, 0);
  assert.equal((await request([a, a])).status, 400); assert.equal(rows.size, 0);
  let response = await request([b, misses[0], a]); assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true, won: true, tries: 3, points: 8, alreadySaved: false });
  response = await request([a, b]);
  assert.deepEqual(await response.json(), { ok: true, won: true, tries: 3, points: 8, alreadySaved: true });
  assert.equal(rows.size, 1); checks++;
  console.log('PASS HTTP daily scoring uses the published pair, ignores forged points, and preserves the original result on retries');
} finally { globalThis.fetch = originalFetch; }
console.log(`${checks} Face Swap checks passed across ${bank.length} pairings.`);
