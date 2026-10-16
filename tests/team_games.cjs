const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const ctx = vm.createContext({console});
vm.runInContext(fs.readFileSync('static/team-games/games.js', 'utf8'), ctx);
const model = vm.runInContext('TEAM_GAME_MODEL', ctx);
const candidates = Array.from({length: 12}, (_, i) => ({id: i + 1, name: `Player ${i + 1}`, pos: 'C', first: 2000, last: 2010}));
const shuffle = arr => arr.slice().reverse();
let checks = 0;
function test(name, fn) {fn(); checks++; console.log('PASS', name);}
test('search accepts the full team pool, rejects invalid or repeated guesses, and scores by clue', () => {
  for (let wrong = 0; wrong < 3; wrong++) {
    const r = model.identityRound(candidates[0], candidates);
    assert.equal(r.candidates.size, 12);
    assert.equal(model.answerIdentity(r, 999), null);
    assert.equal(r.wrong.size, 0); assert.equal(r.clue, 1);
    for (let i = 0; i < wrong; i++) {
      assert.equal(model.answerIdentity(r, candidates[i + 5].id), false);
      assert.equal(model.answerIdentity(r, candidates[i + 5].id), null);
      assert.equal(r.wrong.size, i + 1); assert.equal(r.candidates.size, 12);
    }
    assert.equal(model.answerIdentity(r, 1), true);
    assert.equal(r.points, [10, 6, 3][wrong]); assert.equal(r.over, true);
    assert.equal(model.answerIdentity(r, 2), null);
  }
  const r = model.identityRound(candidates[0], candidates);
  for (const id of [7, 10, 12]) model.answerIdentity(r, id);
  assert.equal(r.over, true); assert.equal(r.won, false); assert.equal(r.points, 0);
  assert.equal(model.answerIdentity(r, 1), null);
  const hinted = model.identityRound(candidates[0], candidates);
  hinted.clue = 3;
  assert.equal(model.answerIdentity(hinted, 1), true); assert.equal(hinted.points, 3);
});
const p = {id: 7, name: 'Return visits', stints: ['NYI', 'FLA', 'VAN', 'FLA'].map(team => ({team, gp: 100}))};
test('search keeps namesakes distinct by player ID instead of removing valid alumni', () => {
  const namesake = {...candidates[0], id: 99, pos: 'D'};
  const r = model.identityRound(candidates[0], [...candidates, namesake]);
  assert.equal(r.candidates.get(99).name, r.player.name);
  assert.equal(model.answerIdentity(r, 99), false);
  assert.equal(model.answerIdentity(r, 1), true); assert.equal(r.points, 6);
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
test('every team has five Classic journeys and searchable identity answers, including goalies', () => {
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
    const searchable = [...new Map([...byPlayer.values(), ...goalies.map(p=>({...p,pos:'G'}))].map(p=>[p.id,p])).values()];
    const pool = model.pool(players, 'identity', 'classic', team);
    assert(pool.length >= 5, team); assert(players.some(p => p.pos === 'G'), team);
    for (const player of pool) {
      const r = model.identityRound(player, searchable);
      assert(r.candidates.size > 4, team); assert.equal(r.candidates.size, searchable.length);
      assert.equal(model.answerIdentity(r, player.id), true, `${team}: ${player.name}`);
      assert.equal(r.points, 10);
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
  vm.runInContext(section('function countUp(', '// ======================= more games:'),r);
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
test('Team versus Team counts stats up and rolls heights without rapid text replacement or losing results', () => {
  const source=fs.readFileSync('build_sweater.py','utf8');
  const section=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
  function runtime(reduced=false){
    const elements=new Map(),timers=new Map(),frames=[],animations=[];let clock=0,token=0;
    const $=id=>{
      if(!elements.has(id))elements.set(id,{textContent:'',offsetWidth:1,count:null,
        set innerHTML(value){
          this.html=value;const m=value.match(/data-count="([\d.]+)">/);
          if(!m){this.count=null;return;}
          const content=value.slice(m.index+m[0].length),label=content.match(/class="hlt-height-label">([^<]*)/);
          const track={innerHTML:content,style:{},animate(keyframes,options){animations.push({keyframes,options});}};
          this.count={dataset:{count:m[1]},textContent:label?label[1]:content.split('<')[0],track,
            querySelector:selector=>selector==='.hlt-height-track'?track:null};
        },
        get innerHTML(){return this.html||'';},querySelector(){return this.count;},addEventListener(){},
        classList:{values:new Set(),add(x){this.values.add(x);},remove(x){this.values.delete(x);}},
      });return elements.get(id);
    };
    const r=vm.createContext({$,G:{},S:{hlt:{}},HL_LEN:40,game:'hlt',Math,Number,String,console,
      esc:String,teamName:String,logo:String,store:{get:()=>0},paintHotStreak(){},
      performance:{now:()=>clock},matchMedia:()=>({matches:reduced}),requestAnimationFrame:fn=>frames.push(fn),
      setTimeout:(fn,delay)=>{const id=++token;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),
    });
    vm.runInContext(section('function countUp(', '// ======================= more games:'),r);
    vm.runInContext(section('// ---- Higher or Lower: Teams ----','// ---- Mystery Season ----'),r);
    return {$,r,frames,timers,animations,run:code=>vm.runInContext(code,r),frame:time=>{clock=time;frames.shift()(clock);}};
  }
  const cases=[
    ['age',31.4,'27.5','31.4'],['height',74.2,null,'6′2″'],
    ['height',70.8,null,'5′11″'],['height',69.8,null,'5′10″'],['height',71.6,null,'6′0″'],
    ['goals',1234,(1080).toLocaleString(),(1234).toLocaleString()],
    ['games',12345,(10802).toLocaleString(),(12345).toLocaleString()],['abroad',8,'7','8'],
  ];
  for(const [metric,value,half,final] of cases)for(const won of [true,false]){
    const t=runtime();t.r.target={rounds:[['VAN',value-1,'BOS',value,metric],['TOR',value,'MTL',value+1,metric]]};
    t.run('S.hlt={target,guesses:[],over:false};G.hlt.render(target,S.hlt)');
    const answer=won?'H':'L';assert.equal(t.run(`G.hlt.guess(target,"${answer}",true)`),won);
    t.run(`S.hlt.guesses.push("${answer}");S.hlt.over=${!won};G.hlt.render(target,S.hlt)`);
    const count=t.$('htB').count;assert.notEqual(count,null);
    const duration=metric==='height'?1200:600;
    if(metric==='height'){
      assert.equal(count.textContent,final);assert.equal(t.frames.length,0);
      assert.equal(t.animations.length,1);assert.equal(t.animations[0].options.duration,duration);
      assert.equal(t.animations[0].keyframes[0].transform,'translateY(0)');
      assert.equal(t.animations[0].keyframes[1].transform,count.track.style.transform);
      const values=[...count.track.innerHTML.matchAll(/class="hlt-height-inches">(\d+)</g)].map(m=>Number(m[1]));
      assert.equal(values.length,7);assert(values.every(n=>n>=0&&n<12));
      assert.equal(values.at(-1),Math.round(value)%12);
      const feet=[...count.track.innerHTML.matchAll(/class="hlt-height-row"><span>(\d+)</g)].map(m=>Number(m[1]));
      const totals=values.map((n,i)=>feet[i]*12+n);
      assert.equal(totals[0],Math.round(value)-6);assert.equal(totals.at(-1),Math.round(value));
      assert(totals.every((n,i)=>i===0||n===totals[i-1]+1));
    }else{
      assert.notEqual(count.textContent,final);assert.equal(t.animations.length,0);
      t.frame(duration/2);assert.equal(count.textContent,half,metric);assert.equal(t.$('htB').count,count);
      t.frame(duration);assert.equal(count.textContent,final,metric);assert.equal(t.frames.length,0);
    }
    const timer=[...t.timers.values()][0];assert.equal(timer.delay,duration+(won?500:800));
    timer.fn();assert.equal(t.run('G.hlt.score(target,S.hlt.guesses)'),won?1:0);
    if(won)assert(t.$('htA').innerHTML.includes(`data-count="${value}"`));
    else assert.equal(t.$('htB').count.textContent,final);
  }
  const quiet=runtime(true);quiet.r.target={rounds:[['VAN',30,'BOS',31.4,'age']]};
  quiet.run('S.hlt={target,guesses:[],over:false};G.hlt.guess(target,"H",true)');
  assert.equal(quiet.$('htB').count.textContent,'31.4');assert.equal(quiet.frames.length,0);
  quiet.run('G.hlt.reset()');assert.equal(quiet.timers.size,0);
  quiet.run('S.hlt.guesses=["H"];S.hlt.over=true;G.hlt.render(target,S.hlt,true)');
  assert(!quiet.$('htPair').classList.values.has('slide'));assert.equal(quiet.frames.length,0);
  quiet.r.target={rounds:[['VAN',70,'BOS',71,'height']]};
  quiet.run('S.hlt={target,guesses:[],over:false};G.hlt.guess(target,"H",true)');
  assert.equal(quiet.$('htB').count.textContent,'5′11″');assert.equal(quiet.animations.length,0);
  assert.equal((quiet.$('htB').count.track.innerHTML.match(/class="hlt-height-row"/g)||[]).length,1);
  const zero=runtime();zero.r.target={rounds:[['VAN',1,'BOS',0,'abroad']]};
  zero.run('S.hlt={target,guesses:[],over:false};G.hlt.guess(target,"L",true)');
  assert.equal(zero.$('htB').count.textContent,'0');assert.equal(zero.frames.length,0);
  const leaving=runtime();leaving.r.target=quiet.r.target;
  leaving.run('S.hlt={target,guesses:[],over:false};G.hlt.guess(target,"H",true)');
  const markup=leaving.$('htB').innerHTML;leaving.run('game="classic"');[...leaving.timers.values()][0].fn();
  assert.equal(leaving.$('htB').innerHTML,markup);
});
console.log(`${checks} team game checks passed.`);
