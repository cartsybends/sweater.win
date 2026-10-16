// Run from the repository root: node tests/who_scored.cjs
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('build_sweater.py','utf8');
const sources = new Map(JSON.parse(fs.readFileSync('static/who-scored/sources.json')).map(s => [s.id, s]));
const games = JSON.parse(fs.readFileSync('static/who-scored/games.json'));
const clips = JSON.parse(fs.readFileSync('static/who-scored/clips.json')).map(c => ({...c, game: games[sources.get(c.id).game_id]}));
const players = Object.values(JSON.parse(fs.readFileSync('schedule.json')).players);
const storage = new Map(), elements = new Map();
let day="2026-10-12";
class Element {
  constructor() {
    this.hidden=false; this.disabled=false; this.style={}; this.attrs={}; this.events={};
    this.paused=true; this.ended=false; this.currentTime=0; this.duration=4; this.dataset={};
    const classes = new Set();
    this.classList={add:c=>classes.add(c),remove:c=>classes.delete(c),toggle:(c,on)=>on ? classes.add(c) : classes.delete(c),contains:c=>classes.has(c)};
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
const ctx = vm.createContext({console,Math,Map,Set,Date,Array,Number,String,JSON,
  G:{}, BYID:new Map(players.map(p=>[p.id,p])), $, DAILY:{whoscored:{'2026-10-12':clips[0].pid}}, START:{whoscored:'2026-10-12'},
  store:{get:k=>storage.has(k)?JSON.parse(storage.get(k)):null,set:(k,v)=>storage.set(k,JSON.stringify(v))},
  document:{hidden:false,querySelectorAll:()=>[],addEventListener(){}},
  uiIcon:()=>'<svg></svg>', esc:s=>String(s), countryName:s=>s, toast:()=>{}, addWrong:()=>{}, FALLBACK:'',
  renderOptions(){},updateLabels(){},tick(){},renderResultRecap(){},recordResult(){},awardProgression:()=>[],submitPending(){},confetti(){},
  archiveGet:()=>null, archiveSet(){}, historyGet:()=>null, historySet(){},
  dayKey:()=>day, secondsToEtMidnight:()=>3600, shortDay:k=>k, dailyNumber:()=>1, onHub:false, setTimeout:()=>0,
});
const run=s=>vm.runInContext(s,ctx);
function part(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert(a>=0&&b>a);return source.slice(a,b);}
run(part('function hash(str)','// ---- dates:'));
run(part('function shuffled(arr','// ---- Draft Day:'));
run(part('// ---- Who Scored?','// ======================= game engine').replace('/*__GOAL_CLIPS__*/[]',JSON.stringify(clips)));
run(part('const GAME_IDS =','// ---- archive progress'));
run(part('function startGame(t','const niceDay ='));
// Legacy global Unlimited preferences and old saved rounds cannot unlock extra clips.
run('game="whoscored"; mode="unlimited";');
ctx.store.set('sweater-unlimited-whoscored',{target:clips[2].id,guesses:[],opts:{}});
run('loadCurrent()');
const target=run('S.whoscored.target');
assert.equal(run('mode'),'daily');assert.equal(target.pid,clips[0].pid);
assert.equal($('wsVideo').src,'');assert.equal($('wsSetup').hidden,false);assert.equal($('wsRound').hidden,true);
assert.equal($('banner').style.display,'none');assert.equal($('wsSource').hidden,true);
// A guess cannot be consumed before loading; the original stays gated.
run(`doGuess(${target.pid})`);assert.equal(run('S.whoscored.guesses.length'),0);
$('wsOriginal').onclick();assert.equal($('wsVideo').src,'');
$('wsStart').onclick();assert.equal($('wsSetup').hidden,true);assert.equal($('wsRound').hidden,false);
assert.equal($('wsVideo').src,`who-scored/${target.masked}`);$('wsVideo').events.loadeddata();
const wrong=clips.find(c=>c.pid!==target.pid).pid;
run(`doGuess(${wrong}); doGuess(${wrong})`);assert.equal(run('S.whoscored.guesses.length'),1);
assert.equal($('wsLeft').textContent,'Guess 2 of 6');assert($('wsWrong').innerHTML.includes('Miss'));
for(const action of ['loadDaily()','loadUnlimited(true)','mode="archive";loadArchive("2026-10-11")']){
 run(action);assert.equal(run('mode'),'daily');assert.equal(run('S.whoscored.target.id'),target.id);assert.equal(run('S.whoscored.guesses.length'),1);
}
// Refresh resumes the same daily, without reading the old Unlimited save.
run('S.whoscored.target=null; S.whoscored.mode=null; mode="unlimited"; loadCurrent()');
assert.equal(run('S.whoscored.target.id'),target.id);assert.equal(run('S.whoscored.guesses.length'),1);
$('wsVideo').events.loadeddata();run(`doGuess(${target.pid})`);
assert.equal(run('S.whoscored.over'),true);assert.equal($('wsOriginal').hidden,false);
assert.equal($('wsGuessing').hidden,true);assert.equal($('wsQuestionCopy').hidden,true);assert.equal($('wsFinishActions').hidden,false);
assert($('wsWrong').innerHTML.includes('Correct'));assert(storage.has('sweater-daily-whoscored'));
assert.equal($('profile').href,`https://www.nhl.com/gamecenter/${target.game.id}/boxscore`);
assert($('profile').classList.contains('ws-game-result'));
assert($('profile').innerHTML.includes('Dec 10, 2024'));
assert($('profile').innerHTML.includes('TBL <b>1</b>'));
assert($('profile').innerHTML.includes('<b>2</b> EDM'));
assert($('profile').attrs['aria-label'].includes('Tampa Bay Lightning 1, Edmonton Oilers 2'));
$('wsOriginal').onclick();assert.equal($('wsVideo').src,`who-scored/${target.reveal}`);
$('wsSlow').onclick();assert.equal($('wsVideo').playbackRate,.5);
$('wsOriginal').onclick();assert.equal($('wsVideo').src,`who-scored/${target.masked}`);
for(const action of ['loadUnlimited(true)','mode="archive";loadArchive("2026-10-11")','S.whoscored.target=null; mode="unlimited"; loadCurrent()']){
 run(action);assert.equal(run('mode'),'daily');assert.equal(run('S.whoscored.target.id'),target.id);assert.equal(run('S.whoscored.over'),true);assert.equal(run('S.whoscored.guesses.length'),2);
 assert.equal($('profile').href,`https://www.nhl.com/gamecenter/${target.game.id}/boxscore`);
}
assert.equal(run('archiveDays("whoscored").length'),0);
// Midnight rollover is the only normal way to get a fresh goal.
run('DAILY.whoscored["2026-10-13"]=WS_CLIPS[1].pid');
run(part('function tick()','setInterval(tick'));
day='2026-10-13';run('tick()');
assert.equal(run('mode'),'daily');assert.equal(run('S.whoscored.target.pid'),clips[1].pid);
assert.equal(run('S.whoscored.over'),false);assert.equal(run('S.whoscored.guesses.length'),0);
assert.equal($('wsVideo').playbackRate,1);assert.equal($('wsOriginal').hidden,true);
assert.equal($('banner').style.display,'none');assert.equal($('wsSource').hidden,true);
$('wsStart').onclick();$('wsVideo').events.error();assert.equal($('wsGuess').disabled,true);assert.equal($('wsWatch').hidden,false);
$('wsWatch').onclick();assert.equal(run('G.whoscored.failed'),false);$('wsVideo').events.loadeddata();
// A completed loss is locked just like a completed win.
for(const [i,c] of clips.filter(c=>c.pid!==clips[1].pid).slice(0,6).entries()){
 run(`doGuess(${c.pid})`);
 const misses=i+1;
 assert.equal(($('wsFeedback').innerHTML.match(/class="ws-hint"/g)||[]).length,misses===6?0:misses>=4?2:misses>=2?1:0);
 assert(!$('wsFeedback').innerHTML.includes('Shoots'));
 if(misses===2){
  assert($('wsFeedback').innerHTML.includes('<small>Position</small><strong>Forward</strong>'));
  run('G.whoscored.render({...S.whoscored.target,p:{...S.whoscored.target.p,pos:"D"}},S.whoscored)');
  assert($('wsFeedback').innerHTML.includes('<strong>Defenseman</strong>'));
  run('G.whoscored.render(S.whoscored.target,S.whoscored)');
 }
 if(misses===4){
  assert($('wsFeedback').innerHTML.includes(`<small>Born in</small><strong>${run('S.whoscored.target.p.nation')}</strong>`));
  const hints=$('wsFeedback').innerHTML;
  run('S.whoscored.target=null; S.whoscored.mode=null; loadCurrent()');
  assert.equal(run('S.whoscored.guesses.length'),4);assert.equal($('wsFeedback').innerHTML,hints);
  $('wsVideo').events.loadeddata();
 }
}
assert.equal(run('S.whoscored.over'),true);assert.equal(run('S.whoscored.guesses.length'),6);
assert.equal($('profile').href,`https://www.nhl.com/gamecenter/${clips[1].game.id}/boxscore`);
assert($('profile').innerHTML.includes('Sep 18, 2019'));
run('S.whoscored.target=null; S.whoscored.mode=null; loadUnlimited(true)');
assert.equal(run('S.whoscored.over'),true);assert.equal(run('S.whoscored.guesses.length'),6);
// Dates describe the historical game consistently, even near timezone date boundaries.
const originalTZ = process.env.TZ;
try {
 for (const tz of ['America/Vancouver','Pacific/Kiritimati','Pacific/Pago_Pago']) {
  process.env.TZ=tz;
  assert(run('wsGameResult(WS_CLIPS[0]).html').includes('Dec 10, 2024'));
 }
} finally {if(originalTZ===undefined)delete process.env.TZ;else process.env.TZ=originalTZ;}
for(const c of clips){
 const result=run(`wsGameResult(WS_CLIPS.find(c=>c.id===${JSON.stringify(c.id)}))`);
 assert.equal(result.href,`https://www.nhl.com/gamecenter/${c.game.id}/boxscore`);
 assert(result.label.includes(`${c.game.away.name} ${c.game.away.score}, ${c.game.home.name} ${c.game.home.score}`));
 assert(result.html.includes(c.game.finish==='REG'?'Final ·':`Final/${c.game.finish} ·`));
}
// The shared results banner restores its normal player link in another game.
run('G.fixture={view:"view-fixture",player:()=>BYID.get(WS_CLIPS[0].pid),meta:()=>"",cheers:[]}; S.fixture={target:{},guesses:[],day:dayKey()}; game="fixture"; finish(false,false)');
assert.equal($('profile').textContent,'View profile on NHL.com');
assert.equal($('profile').href,`https://www.nhl.com/player/${clips[0].pid}`);
assert(!$('profile').classList.contains('ws-game-result'));
assert.equal($('profile').attrs['aria-label'],undefined);
assert.equal(new Set(clips.map(c=>c.pid)).size,clips.length);
for(const c of clips){assert(ctx.BYID.has(c.pid));for(const k of ['masked','reveal','poster'])assert(!c[k].includes(ctx.BYID.get(c.pid).name.split(' ').at(-1).toLowerCase()));}
console.log(`Who Scored?: ${clips.length} scorers; hint timing/bubbles/resume, daily-only guards, win/loss game stats, timezone-safe dates, banner reuse, rollover and replay/reveal passed.`);
