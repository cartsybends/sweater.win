// Run from the repository root: node tests/who_scored.cjs
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('build_sweater.py','utf8');
const clips = JSON.parse(fs.readFileSync('static/who-scored/clips.json'));
const players = Object.values(JSON.parse(fs.readFileSync('schedule.json')).players);
const storage = new Map(), elements = new Map(), modeButtons = [];
class Element {
  constructor() {
    this.hidden=false; this.disabled=false; this.style={}; this.attrs={}; this.events={};
    this.paused=true; this.ended=false; this.currentTime=0; this.duration=4; this.dataset={};
    this.classList={add(){},remove(){},toggle(){},contains(){return false;}};
  }
  setAttribute(k,v){this.attrs[k]=String(v);}
  removeAttribute(k){delete this.attrs[k]; if(k==='src')this.src='';}
  addEventListener(k,fn){this.events[k]=fn;}
  querySelector(){return this;}
  appendChild(){}
  pause(){this.paused=true;this.events.pause?.();}
  play(){this.paused=false;this.events.play?.();return Promise.resolve();}
  load(){}
}
const $ = id => {if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
for(const mode of ['daily','unlimited']){const b=new Element();b.dataset.wsMode=mode;modeButtons.push(b);}
const ctx = vm.createContext({console,Math,Map,Set,Date,Array,Number,String,JSON,
  G:{}, BYID:new Map(players.map(p=>[p.id,p])), $, DAILY:{whoscored:{'2026-10-12':clips[0].pid}}, START:{whoscored:'2026-10-12'},
  store:{get:k=>storage.has(k)?JSON.parse(storage.get(k)):null,set:(k,v)=>storage.set(k,JSON.stringify(v))},
  document:{hidden:false,querySelectorAll:sel=>sel==='[data-ws-mode]'?modeButtons:[],addEventListener(){}},
  uiIcon:()=>'<svg></svg>', esc:s=>String(s), countryName:s=>s, toast:()=>{}, addWrong:()=>{}, FALLBACK:'',
  renderOptions(){},updateLabels(){},tick(){},renderResultRecap(){},recordResult(){},awardProgression:()=>[],submitPending(){},confetti(){},
  archiveGet:()=>null, archiveSet(){}, historyGet:()=>null, historySet(){},
  dayKey:()=> '2026-10-12', shortDay:k=>k, dailyNumber:()=>1, onHub:false, setTimeout:()=>0,
});
const run=s=>vm.runInContext(s,ctx);
function part(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert(a>=0&&b>a);return source.slice(a,b);}
run(part('function hash(str)','// ---- dates:'));
run(part('function shuffled(arr','// ---- Draft Day:'));
run(part('// ---- Who Scored?','// ======================= game engine').replace('/*__GOAL_CLIPS__*/[]',JSON.stringify(clips)));
run(part('const GAME_IDS =','// ---- archive progress'));
run(part('function startGame(t','const niceDay ='));
run('game="whoscored"; mode="unlimited";');

// Full rotations are permutations, the cycle boundary differs, and state survives a fresh context read.
let last=null;
for(let cycle=0;cycle<30;cycle++){
  const ids=[];
  for(let i=0;i<clips.length;i++){const id=run('wsRandom().id');if(i===0)assert.notEqual(id,last);ids.push(id);last=id;}
  assert.equal(new Set(ids).size,clips.length);
}
run('loadUnlimited(true)');
const target=run('S.whoscored.target');
assert.equal($('wsVideo').src,'');assert.equal($('wsSetup').hidden,false);assert.equal($('wsRound').hidden,true);
// A guess cannot be consumed before the clip has loaded. Original playback is gated.
run(`doGuess(${target.pid})`);assert.equal(run('S.whoscored.guesses.length'),0);
$('wsOriginal').onclick();assert.equal($('wsVideo').src,'');
$('wsStart').onclick();assert.equal($('wsSetup').hidden,true);assert.equal($('wsRound').hidden,false);
assert.equal($('wsVideo').src,`who-scored/${target.masked}`);
$('wsVideo').events.loadeddata();
assert.equal($('wsLeft').textContent,'Guess 1 of 6');assert.equal($('wsHistory').hidden,true);
const wrong=clips.find(c=>c.pid!==target.pid).pid;
run(`doGuess(${wrong}); doGuess(${wrong})`);assert.equal(run('S.whoscored.guesses.length'),1,'duplicate guesses do not consume a try');
assert.equal($('wsLeft').textContent,'Guess 2 of 6');assert.equal($('wsHistory').hidden,false);assert($('wsWrong').innerHTML.includes('Miss'));
run('loadUnlimited()');assert.equal(run('S.whoscored.target.id'),target.id);assert.equal(run('S.whoscored.guesses.length'),1);
// Restore the browser-local round after clearing in-memory state.
run('S.whoscored.target=null; S.whoscored.mode=null; loadUnlimited()');
assert.equal(run('S.whoscored.target.id'),target.id);assert.equal(run('S.whoscored.guesses.length'),1);
$('wsVideo').events.loadeddata();run(`doGuess(${target.pid})`);
assert.equal(run('S.whoscored.over'),true);assert.equal($('wsOriginal').hidden,false);
assert.equal($('wsGuessing').hidden,true);assert.equal($('wsQuestionCopy').hidden,true);assert.equal($('wsFinishActions').hidden,false);assert.equal($('wsContinue').hidden,false);
assert($('wsWrong').innerHTML.includes('Correct'));
$('wsOriginal').onclick();assert.equal($('wsVideo').src,`who-scored/${target.reveal}`);
$('wsSlow').onclick();assert.equal($('wsVideo').playbackRate,.5);
$('wsOriginal').onclick();assert.equal($('wsVideo').src,`who-scored/${target.masked}`);
// The next round restores normal speed and keeps the answer unavailable.
run('G.whoscored.advance=true; loadUnlimited(true)');
assert.notEqual(run('S.whoscored.target.id'),target.id);assert.equal($('wsVideo').playbackRate,1);assert.equal($('wsOriginal').hidden,true);
$('wsVideo').events.error();assert.equal($('wsGuess').disabled,true);assert.equal($('wsWatch').hidden,false);
$('wsWatch').onclick();assert.equal(run('G.whoscored.failed'),false);
$('wsVideo').events.loadeddata();assert.equal(run('G.whoscored.ready'),true);
// Six different misses end the round; restore reproduces a completed loss.
const answer=run('S.whoscored.target.pid');
for(const c of clips.filter(c=>c.pid!==answer).slice(0,6))run(`doGuess(${c.pid})`);
assert.equal(run('S.whoscored.over'),true);assert.equal(run('S.whoscored.guesses.length'),6);
run('S.whoscored.target=null; S.whoscored.mode=null; loadUnlimited()');assert.equal(run('S.whoscored.over'),true);
// Daily is shared, deterministic, and separate from saved unlimited progress.
run('mode="daily";loadDaily()');assert.equal(run('S.whoscored.target.pid'),clips[0].pid);
$('wsStart').onclick();$('wsVideo').events.loadeddata();run(`doGuess(${clips[0].pid})`);
assert.equal($('wsContinue').hidden,false);assert(storage.has('sweater-daily-whoscored'));
$('wsContinue').onclick();assert.equal(run('mode'),'unlimited');assert.equal(run('S.whoscored.over'),false);
assert.equal(new Set(clips.map(c=>c.pid)).size,clips.length);
for(const c of clips){assert(ctx.BYID.has(c.pid));for(const k of ['masked','reveal','poster'])assert(!c[k].includes(ctx.BYID.get(c.pid).name.split(' ').at(-1).toLowerCase()));}
console.log(`Who Scored?: ${clips.length} scorers; 30 rotations, setup, load/retry, guesses, persistence, win/loss and reveal passed.`);
