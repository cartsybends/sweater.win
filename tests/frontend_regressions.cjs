// Run from the repository root: node tests/frontend_regressions.cjs
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('build_sweater.py', 'utf8');
function part(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  assert(a >= 0 && b > a, `Missing source boundary: ${start}`);
  return source.slice(a, b);
}
let checks = 0;
async function test(name, fn) { await fn(); checks++; console.log('PASS', name); }
function runtime(extra = {}) {
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {hidden: false, style: {}, dataset: {},
      classList: {toggle() {}, add() {}, remove() {}}, querySelector() {return this;}, appendChild() {}});
    return elements.get(id);
  };
  const ctx = vm.createContext({console, Date, Intl, Math, JSON, Number, String, Array, Map, Set, $, ...extra});
  return {ctx, $, run: code => vm.runInContext(code, ctx)};
}

(async () => {
  await test('birthday ages follow the Eastern game calendar in every browser time zone', () => {
    const originalTZ = process.env.TZ;
    try {
      for (const tz of ['UTC', 'America/Vancouver', 'Asia/Tokyo']) {
        process.env.TZ = tz;
        let now;
        class FixedDate extends Date {constructor(...args) {super(...(args.length ? args : [now]));}}
        const r = runtime({Date: FixedDate});
        r.run(part('const ageOf = bd =>', 'const store ='));
        r.run(part('const ET_FMT =', 'const keyUTC ='));
        for (const [time, birthday, expected] of [
          ['2026-11-18T20:00:00Z', '1988-11-19', 37],
          ['2026-11-19T04:59:59Z', '1988-11-19', 37],
          ['2026-11-19T05:00:00Z', '1988-11-19', 38],
          ['2027-01-01T04:59:59Z', '2000-01-01', 26],
          ['2027-01-01T05:00:00Z', '2000-01-01', 27],
          ['2024-02-28T20:00:00Z', '2000-02-29', 23],
          ['2024-02-29T20:00:00Z', '2000-02-29', 24],
          ['2025-03-01T20:00:00Z', '2000-02-29', 25],
        ]) {
          now = Date.parse(time);
          assert.equal(r.run(`ageOf(${JSON.stringify(birthday)})`), expected, `${tz}, ${time}`);
        }
      }
    } finally {if (originalTZ === undefined) delete process.env.TZ; else process.env.TZ = originalTZ;}
  });

  await test('archive finishes preserve existing daily wins and misses, including scored games', () => {
    for (const scored of [false, true]) for (const originalWon of [false, true]) {
      const original = scored ? {s: 4, w: originalWon} : {n: 3, w: originalWon};
      let history = original, writes = 0, stats = 0;
      const r = runtime({game: 'fixture', mode: 'archive', FALLBACK: '',
        S: {fixture: {day: '2026-10-12', target: 42, guesses: [1, 2]}},
        G: {fixture: {view: 'view', player: () => null, meta: () => '', cheers: [], score: () => 9}},
        isScored: () => scored, historyGet: () => history,
        historySet: (game, day, value) => {history = value; writes++;},
        recordResult: () => stats++, awardProgression: () => [], renderResultRecap() {},
        tick() {}, confetti() {}, submitPending() {}, toast() {}, setTimeout() {}, onHub: false,
      });
      r.run(part('function finish(won, fresh)', 'function restoreFrom'));
      r.run(`finish(${!originalWon}, true)`);
      assert.equal(history, original); assert.equal(writes, 0); assert.equal(stats, 0);
      r.run(`finish(${!originalWon}, false)`);
      assert.equal(history, original); assert.equal(writes, 0);
      // An archive puzzle with no earlier completion can still record its first result.
      history = null; r.run('finish(true, true)');
      assert.equal(writes, 1); assert.equal(history.w, true); assert.equal(stats, 0);
      // Unlimited results never enter daily history; a fresh daily still records normally.
      r.run('mode="unlimited"; finish(false, true)'); assert.equal(writes, 1);
      r.run('mode="daily"; finish(false, true)');
      assert.equal(writes, 2); assert.equal(history.w, false); assert.equal(stats, 1);
    }
  });

  function navigation() {
    let opened = null, hubCalls = 0, saved = null;
    const location = {hash: '', pathname: '/app.html', search: ''};
    const r = runtime({game: 'classic', onHub: true, location,
      G: {classic: {}, hl_points: {}, hl_goals: {}}, HL_IDS: ['hl_points', 'hl_goals'],
      MAINTENANCE_GAMES: new Set(), TEAMS: {VAN: []},
      store: {get: () => saved, set() {}},
      history: {pushState() {}, replaceState() {}}, window: {scrollTo() {}},
      document: {body: {classList: {add() {}, remove() {}}}},
      showHub: () => hubCalls++, rememberHubScroll() {}, rememberGame() {}, closeParty() {}, toast() {},
      setGame: id => {opened = id;}, openTeams() {}, openParty() {},
    });
    r.run(part('function openGame(id, push', 'window.addEventListener("popstate"'));
    return {...r, location, opened: () => opened, hubCalls: () => hubCalls, setSaved: value => {saved = value;}};
  }
  await test('inherited names and malformed hashes return to the hub; valid games still open', () => {
    for (const id of ['constructor', '__proto__', 'toString', 'not-a-game']) {
      const r = navigation(); r.location.hash = `#${id}`; r.run('route()');
      assert.equal(r.opened(), null); assert.equal(r.hubCalls(), 1);
      r.run(`openGame(${JSON.stringify(id)})`); assert.equal(r.hubCalls(), 2);
    }
    const malformed = navigation(); malformed.location.hash = '#%E0%A4%A'; malformed.run('route()');
    assert.equal(malformed.hubCalls(), 1);
    const valid = navigation(); valid.location.hash = '#classic'; valid.run('route()');
    assert.equal(valid.opened(), 'classic'); assert.equal(valid.hubCalls(), 0);
  });
  await test('Higher or Lower only restores a valid Higher or Lower variant', () => {
    for (const saved of ['constructor', '__proto__', 'classic', null]) {
      const r = navigation(); r.setSaved(saved); r.run('openGame("hl")'); assert.equal(r.opened(), 'hl_points');
    }
    const saved = navigation(); saved.setSaved('hl_goals'); saved.run('openGame("hl")'); assert.equal(saved.opened(), 'hl_goals');
    saved.run('game="hl_points";openGame("hl")'); assert.equal(saved.opened(), 'hl_points');
  });

  await test('game selectors include playable EDGE modes and preserve each selected game', () => {
    const r = runtime({esc: String, HL_STATS: {points: {name: 'Points'}, goals: {name: 'Goals'}}});
    r.run(part('const HUB = [', '/* Short, repeatable labels'));
    r.run('var G=Object.fromEntries(HUB.flatMap(s=>s.games.filter(([id])=>id!=="hl").map(([id])=>[id,{title:id}])).concat(EDGE_GAMES.map(x=>[x.id,{title:x.title}]),HL_IDS.map((id,i)=>[id,{stat:i?"goals":"points"}])));');
    r.run(part('function gameOptions(selected)', '$("hlStatSel").innerHTML'));
    for (const id of ['edgerush', 'edgespeed', 'edgeshot', 'edgebuild', 'classic', 'hl_goals']) {
      const html = r.run(`gameOptions(${JSON.stringify(id)})`);
      assert(html.includes(`value="${id}" selected`));
      assert.equal((html.match(/ selected/g) || []).length, 1);
      assert(html.includes('label="NHL EDGE"')); assert(!html.includes('value="edgemap"'));
    }
  });

  function partyRuntime(status = 503) {
    let attempts = 0, renderCount = 0, pending;
    const r = runtime({party: {role: 'player', code: 'ABCD', pid: 'fixture', key: 'fixture', picked: null,
      state: {status: 'question', qi: 0, endsAt: 1000}},
      partyNow: () => 100, partyRender: () => renderCount++, toast() {},
      api: () => {attempts++; return new Promise((resolve, reject) => {pending = {resolve, reject};});},
    });
    r.run(part('async function partyAnswer(choice)', 'function partyLeave()'));
    return {...r, attempts: () => attempts, renders: () => renderCount,
      fail: () => pending.reject(Object.assign(new Error('Temporary failure'), status ? {status} : {})),
      succeed: () => pending.resolve({ok: true})};
  }
  await test('recoverable Party failures unlock a retry; successful and recorded answers stay locked', async () => {
    for (const status of [503, 0, 408, 429]) {
      const r = partyRuntime(status), first = r.run('partyAnswer(0)');
      assert.equal(r.run('party.picked'), 0); await r.run('partyAnswer(1)'); assert.equal(r.attempts(), 1);
      r.fail(); await first; assert.equal(r.run('party.picked'), null); assert.equal(r.renders(), 2);
      const retry = r.run('partyAnswer(1)'); assert.equal(r.attempts(), 2); r.succeed(); await retry;
      assert.equal(r.run('party.picked'), 1); await r.run('partyAnswer(2)'); assert.equal(r.attempts(), 2);
    }
    const recorded = partyRuntime(), answer = recorded.run('partyAnswer(0)');
    recorded.run('party.state.you={choice:0}'); recorded.fail(); await answer;
    assert.equal(recorded.run('party.picked'), 0);
    recorded.run('party.picked=null'); await recorded.run('partyAnswer(1)'); assert.equal(recorded.attempts(), 1);
  });
  await test('late Party failures cannot clear a different question or session, or reopen closed answers', async () => {
    for (const change of [
      'party={...party,state:{...party.state},picked:2}',
      'party.state={...party.state,qi:1};party.picked=2',
      'party.state={...party.state,status:"reveal"}',
      'party.state={...party.state,endsAt:50}',
    ]) {
      const r = partyRuntime(), answer = r.run('partyAnswer(0)'); r.run(change);
      const selected = r.run('party.picked'); r.fail(); await answer;
      assert.equal(r.run('party.picked'), selected); assert.equal(r.renders(), 1);
    }
    const closed = partyRuntime(409), answer = closed.run('partyAnswer(0)'); closed.fail(); await answer;
    assert.equal(closed.run('party.picked'), 0); await closed.run('partyAnswer(1)'); assert.equal(closed.attempts(), 1);
    const expired = partyRuntime(); expired.run('party.state.endsAt=50'); await expired.run('partyAnswer(0)'); assert.equal(expired.attempts(), 0);
  });
  console.log(`${checks} frontend regression checks passed.`);
})().catch(error => {console.error(error); process.exitCode = 1;});
