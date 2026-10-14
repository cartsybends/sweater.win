const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const ctx = vm.createContext({console});
vm.runInContext(fs.readFileSync('static/team-games/games.js', 'utf8'), ctx);
const model = vm.runInContext('TEAM_GAME_MODEL', ctx);
const choices = [1, 2, 3, 4].map(id => ({id, name: `Player ${id}`, pos: 'C', first: 2000, last: 2010}));
const shuffle = arr => arr.slice().reverse();
let checks = 0;
function test(name, fn) {fn(); checks++; console.log('PASS', name);}
test('four different names, no repeated guesses, earlier correct answers score more', () => {
  for (let wrong = 0; wrong < 3; wrong++) {
    const r = model.identityRound(choices[0], choices, shuffle);
    assert.equal(new Set(r.choices.map(p => p.id)).size, 4);
    assert.equal(model.answerIdentity(r, 999), null);
    for (let i = 0; i < wrong; i++) {
      assert.equal(model.answerIdentity(r, choices[i + 1].id), false);
      assert.equal(model.answerIdentity(r, choices[i + 1].id), null);
    }
    assert.equal(model.answerIdentity(r, 1), true);
    assert.equal(r.points, [10, 6, 3][wrong]); assert.equal(r.over, true);
    assert.equal(model.answerIdentity(r, 2), null);
  }
  const r = model.identityRound(choices[0], choices, shuffle);
  for (const id of [2, 3, 4]) model.answerIdentity(r, id);
  assert.equal(r.over, true); assert.equal(r.won, false); assert.equal(r.points, 0);
});
const p = {id: 7, name: 'Return visits', stints: ['NYI', 'FLA', 'VAN', 'FLA'].map(team => ({team, gp: 100}))};
test('players with the same name never create ambiguous answer buttons', () => {
  const duplicates = [...choices, {...choices[0],id:8}, {...choices[1],id:9}];
  const r = model.identityRound(choices[0], duplicates, shuffle);
  assert.equal(r.choices.length,4);assert.equal(new Set(r.choices.map(p=>p.name.toLowerCase())).size,4);
});
test('journeys never start solved, and identical return tiles are interchangeable', () => {
  const r = model.journeyRound(p, arr => arr);
  assert(r.order.some((tile, i) => p.stints[tile].team !== p.stints[i].team));
  r.order = [0, 3, 2, 1];
  assert.equal(model.checkJourney(r), true); assert.equal(r.points, 10);
  assert.equal(model.checkJourney(r), null); assert.equal(r.checks, 1);
});
test('correct stops lock without moving, hints respect locks and cap points', () => {
  const r = model.journeyRound(p, shuffle); r.order = [2, 1, 0, 3];
  assert.equal(model.checkJourney(r), false); assert(r.locked.has(1) && r.locked.has(3));
  assert.equal(model.swapJourney(r, 1, 2), false);
  assert.equal(model.swapJourney(r, -1, 2), false);
  assert.equal(model.swapJourney(r, 0, 99), false);
  assert.equal(model.hintJourney(r), true); assert(r.locked.has(0));
  assert.equal(model.hintJourney(r), false);
  assert.equal(model.checkJourney(r), true); assert.equal(r.points, 6);
  assert.equal(model.swapJourney(r, 0, 2), false);
});
test('three failed checks reveal the career with zero points', () => {
  const r = model.journeyRound(p, shuffle); r.order = [1, 2, 3, 0];
  for (let i = 0; i < 3; i++) assert.equal(model.checkJourney(r), false);
  assert.equal(r.over, true); assert.equal(r.points, 0); assert.equal(r.won, false);
});
test('every team has five Classic journeys and four-choice identity questions, including goalies', () => {
  const history = JSON.parse(fs.readFileSync('team_history_cache.json', 'utf8')).teams;
  const careers = JSON.parse(fs.readFileSync('team_careers.json', 'utf8')).players;
  for (const [team, raw] of Object.entries(history)) {
    const byPlayer = new Map();
    for (const r of raw.s) {
      if (!byPlayer.has(r[0])) byPlayer.set(r[0], {id:r[0],name:r[1],pos:r[2],rows:[]});
      byPlayer.get(r[0]).rows.push({y:r[3],gp:r[4],goals:r[5],assists:r[6],points:r[7]});
    }
    const goalies = raw.g.map(r => ({id:r[0],name:r[1],y:r[2],gp:r[3],wins:r[4]}));
    const players = model.identityPlayers({byPlayer,goalies});
    const pool = model.pool(players, 'identity', 'classic', team);
    assert(pool.length >= 5, team); assert(players.some(p => p.pos === 'G'), team);
    for (const player of pool) {
      const r = model.identityRound(player, players, shuffle);
      assert.equal(r.choices.length, 4); assert.equal(new Set(r.choices.map(p => p.id)).size, 4);
      assert.equal(new Set(r.choices.map(p => p.name.toLowerCase())).size, 4);
      assert(r.choices.every(p => byPlayer.has(p.id) || goalies.some(g => g.id === p.id)));
      assert(player.rows.includes(player.peak));
    }
    const paths = model.pool(careers, 'journey', 'classic', team); assert(paths.length >= 5, team);
    for (const player of paths) {
      const r = model.journeyRound(player, shuffle);
      assert(r.order.some((tile, i) => player.stints[tile].team !== player.stints[i].team), player.name);
      r.order = player.stints.map((_, i) => i); assert.equal(model.checkJourney(r), true);
    }
  }
});
test('team arrow controls cannot answer a hidden Higher or Lower round', () => {
  const source = fs.readFileSync('build_sweater.py', 'utf8');
  const start = source.indexOf('document.addEventListener("keydown", e => {\n  if (onHub');
  const end = source.indexOf('$("hlPair")', start);
  let listener, hidden = true, guessed = 0;
  const keyboard = vm.createContext({onHub:false,game:'hl_points',
    document:{addEventListener:(_name,fn)=>{listener=fn},querySelector:()=>null},
    $:()=>({hidden}),doGuess:()=>guessed++});
  vm.runInContext(source.slice(start,end), keyboard);
  const event = key => ({key,target:{tagName:'BUTTON'},preventDefault(){}});
  listener(event('ArrowUp')); listener(event('ArrowDown')); assert.equal(guessed,0);
  hidden = false; listener(event('ArrowUp')); listener(event('ArrowDown')); assert.equal(guessed,2);
  listener({...event('ArrowDown'),target:{tagName:'SELECT'}}); assert.equal(guessed,2);
});
test('Teams Higher/Lower finishes its number reveal before advancing and cancels stale runs', () => {
  const source = fs.readFileSync('build_sweater.py', 'utf8');
  const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
  const elements = new Map(), values = new Map(), timers = new Map(), frames = [], events = [];
  let clock = 0, token = 0, reduced = false;
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {textContent: '', innerHTML: '', offsetWidth: 1,
      classList: {values: new Set(), add(x) {this.values.add(x);}, remove(x) {this.values.delete(x);}},
      querySelector() {
        const count = this.innerHTML.match(/data-count="(\d+)"/);
        this.count = count ? {dataset: {count: count[1]}, textContent: count[1]} : null;
        return this.count;
      },
      querySelectorAll() {return this.buttons = this.innerHTML.includes('data-pick=') ? ['H','L'].map(pick => ({dataset: {pick}})) : [];},
    });
    return elements.get(id);
  };
  const players = [20,10,30].map(v => ({id:v,v,y:2000,name:`Player ${v}`,pos:'C'}));
  const r = vm.createContext({$,console,Math,Number,String,Set,teamMiniCleanup() {},
    historyForTeam: () => ({skaters:players}), teamHLPlayers: () => players,
    TEAM_HL_STATS: {points:{name:'Points',type:'high',label:'points',up:'Higher',down:'Lower'}},
    store: {get:key=>values.get(key),set:(key,value)=>values.set(key,value)},
    shuffled: arr=>arr.slice(), pick: arr=>arr[0], esc:String, teamFullName:()=> 'Vancouver Canucks',
    teamHistHeadshot:()=>'',logo:()=>'',seasonText:String,teamModeNoData(){},
    teamModeShell() {elements.clear();},paintHotStreak:(id,value)=>{$(id).textContent=String(value);},
    matchMedia:()=>({matches:reduced}),performance:{now:()=>clock},requestAnimationFrame:fn=>frames.push(fn),
    setTimeout:(fn,delay)=>{const id=++token;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),
    SweaterAnalytics:{context:()=> 'test',step:(...args)=>events.push(args),completeRound(){}},
  });
  vm.runInContext(section('function countUp(el)', '// ======================= more games:'),r);
  vm.runInContext(section('function startTeamHigher(t)', 'function openTeamMode('),r);
  const start = () => vm.runInContext('startTeamHigher("VAN")',r);
  const answer = () => {const button=$('teamHLB').buttons.find(b=>b.dataset.pick==='L');button.onclick();return button;};
  start();const old=answer();old.onclick();assert.equal(events.length,1,'One answer during the reveal');
  assert.equal($('teamHLB').count.textContent,0);assert.equal(timers.size,1);
  clock=300;frames.shift()(clock);assert(Number($('teamHLB').count.textContent)>0&&Number($('teamHLB').count.textContent)<10);
  clock=600;frames.shift()(clock);assert.equal($('teamHLB').count.textContent,10);
  const next=[...timers.values()][0];assert.equal(next.delay,1100);timers.clear();next.fn();
  assert.equal($('teamHLStreak').textContent,'1');assert($('teamHLA').innerHTML.includes('Player 10'));
  assert($('teamHLPair').classList.values.has('slide'));
  start();answer();const stale=[...timers.values()][0].fn;
  start();assert.equal(timers.size,0);const markup=$('teamHLB').innerHTML;
  stale();assert.equal($('teamHLB').innerHTML,markup);assert.equal($('teamHLStreak').textContent,'0');
  answer();const leaving=[...timers.values()][0].fn;vm.runInContext('teamMiniCleanup()',r);
  assert.equal(timers.size,0);const held=$('teamHLB').innerHTML;leaving();assert.equal($('teamHLB').innerHTML,held);
  reduced=true;start();answer();assert.equal($('teamHLB').count.textContent,'10');
  const quiet=[...timers.values()][0];timers.clear();quiet.fn();assert(!$('teamHLPair').classList.values.has('slide'));
});
console.log(`${checks} team game checks passed.`);
