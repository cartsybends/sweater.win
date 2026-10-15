// Run from the repository root: node tests/home_challenges.cjs
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('build_sweater.py','utf8');
function part(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert(a>=0&&b>a);return source.slice(a,b);}
function runtime(storage=new Map()){
 let day='2026-10-13',random=.25,opened=null;
 const unavailable=new Set(),finished=new Set();
 const math=Object.create(Math);math.random=()=>random;
 const context=vm.createContext({Math:math,Date,Array,Set,Map,JSON,Number,String,console,HL_POOL:[1,2],HL_STATS:{points:{}},
  dayKey:()=>day,mode:'unlimited',esc:String,openGame:id=>{opened=id;},KEYS:{benchboss:{daily:'sweater-benchboss-daily'}},archiveGet:()=>null,
  hubStatus:id=>[finished.has(id)?'done':'',''],
  store:{get:key=>storage.has(key)?JSON.parse(storage.get(key)):null,set:(key,value)=>storage.set(key,JSON.stringify(value))},
 });
 const run=code=>vm.runInContext(code,context),plain=code=>JSON.parse(JSON.stringify(run(code)));
 run(source.match(/^const pick = arr.*$/m)[0]);
 run(part('const HUB = [','/* Short, repeatable labels'));
 context.G=Object.fromEntries(plain('HUB.flatMap(s=>s.games.map(([id])=>id)).concat(EDGE_GAMES.map(x=>x.id))').map(id=>[id,{pool:()=>unavailable.has(id)?[]:[1,2]}]));
 run(part('const hubIds =','const cleanHubIds ='));
 run(part('const gameIsReady =','const LIBRARY_FILTERS ='));
 run(part('// ---- player progression','function renderPlayerProfile()'));
 return {run,plain,storage,unavailable,finished,setDay:value=>day=value,setRandom:value=>random=value,opened:()=>opened,
  history:entries=>storage.set('sweater-history',JSON.stringify(entries))};
}
let checks=0;
function test(name,fn){fn();checks++;console.log('PASS',name);}
test('daily draws cover the playable library, including NHL EDGE, and skip unavailable modes',()=>{
 const r=runtime();r.unavailable.add('edgeshot');const ready=r.plain('hubIds().filter(gameIsReady)'),draws=new Set();
 for(let i=0;i<ready.length;i++){r.setRandom((i+.5)/ready.length);draws.add(r.run('randomDailyChallenge()'));}
 assert.deepEqual([...draws].sort(),ready.sort());assert(draws.has('edgebuild'));assert(!draws.has('blur'));assert(!draws.has('edgemap'));assert(!draws.has('edgeshot'));
 r.finished.add('classic');for(let i=0;i<50;i++){r.setRandom(i/50);assert.notEqual(r.run('randomDailyChallenge()'),'classic');}
 r.run('openChallenge("daily")');assert.equal(r.run('mode'),'daily');assert(ready.includes(r.opened()));
});
test('weekly draws belong to three separate categories and use more than the old fixed games',()=>{
 const selections=[new Set(),new Set(),new Set()];
 for(let i=0;i<100;i++){const r=runtime();r.setRandom(i/100);const games=r.plain('activeWeeklyTheme().games'),pools=r.plain('weeklyChallengePools()');assert.equal(new Set(games).size,3);games.forEach((id,j)=>{assert(pools[j].includes(id));assert(r.run(`gameIsReady(${JSON.stringify(id)})`));selections[j].add(id);});}
 assert(selections[0].has('whoscored'));assert(selections[1].has('number'));assert(selections[2].has('overtime'));assert(selections.every(ids=>ids.size>3));
});
test('weekly assignments survive renders, reloads and day changes, then refresh on Monday',()=>{
 const r=runtime();r.setRandom(.05);const games=r.plain('activeWeeklyTheme().games');r.setRandom(.95);assert.deepEqual(r.plain('activeWeeklyTheme().games'),games);
 const restored=runtime(r.storage);restored.setRandom(.9);assert.deepEqual(restored.plain('activeWeeklyTheme().games'),games);restored.setDay('2026-10-18');assert.deepEqual(restored.plain('activeWeeklyTheme().games'),games);
 restored.setDay('2026-10-19');assert.notDeepEqual(restored.plain('activeWeeklyTheme().games'),games);assert.equal(JSON.parse(r.storage.get('sweater-weekly-challenge-v1')).week,'2026-10-19');
});
test('weekly clicks advance through all picks, share progress with achievements, and recognize Higher or Lower',()=>{
 const r=runtime();r.storage.set('sweater-weekly-challenge-v1',JSON.stringify({week:'2026-10-12',games:['whoscored','number','hl']}));
 for(const id of ['whoscored','number','hl']){r.run('openChallenge("weekly")');assert.equal(r.opened(),id);assert.equal(r.run('mode'),'daily');const history=JSON.parse(r.storage.get('sweater-history')||'{}');history[`${id==='hl'?'hl_points':id}:2026-10-13`]={w:true,n:1};r.history(history);}
 assert.equal(r.run('weeklyProgress()'),3);assert.equal(r.run('achievementList().find(a=>a.id==="weekender").on'),true);
 r.finished.add('whoscored');r.finished.add('number');r.finished.add('hl');r.run('openChallenge("weekly")');assert(!['whoscored','number','hl'].includes(r.opened()));
 r.setDay('2026-10-19');assert.equal(r.run('weeklyProgress()'),0);
});
test('existing weekly completions carry into the new category picks; older and future results do not count',()=>{
 const r=runtime();r.history({'classic:2026-10-12':{w:true},'trophy:2026-10-13':{w:true},'shoot:2026-10-13':{w:false},'journey:2026-10-11':{w:true},'map:2026-10-14':{w:true}});
 assert.deepEqual(r.plain('activeWeeklyTheme().games'),['classic','trophy','shoot']);assert.equal(r.run('weeklyProgress()'),3);
});
test('invalid or unavailable weekly picks are repaired without changing valid or completed picks',()=>{
 const r=runtime();r.storage.set('sweater-weekly-challenge-v1',JSON.stringify({week:'2026-10-12',games:['blur','number','shoot']}));r.unavailable.add('shoot');
 const repaired=r.plain('activeWeeklyTheme().games');assert.notEqual(repaired[0],'blur');assert.equal(repaired[1],'number');assert.notEqual(repaired[2],'shoot');
 r.storage.set('sweater-weekly-challenge-v1',JSON.stringify({week:'2026-10-12',games:['classic','number','shoot']}));r.history({'shoot:2026-10-13':{w:true}});assert.equal(r.plain('activeWeeklyTheme().games')[2],'shoot');assert.equal(r.run('weeklyProgress()'),1);
 r.storage.set('sweater-weekly-challenge-v1',JSON.stringify({week:'2026-10-12',games:{bad:true}}));assert.equal(r.plain('activeWeeklyTheme().games').filter(Boolean).length,3);
});
test('finished libraries open an unlimited round; empty libraries never open a broken mode',()=>{
 const r=runtime();r.plain('hubIds()').forEach(id=>r.finished.add(id));r.run('openChallenge("daily")');assert.equal(r.run('mode'),'unlimited');assert(r.run(`gameIsReady(${JSON.stringify(r.opened())})`));
 const empty=runtime();empty.plain('hubIds()').forEach(id=>empty.unavailable.add(id));empty.run('HL_POOL.length=0;openChallenge("daily");openChallenge("weekly")');assert.equal(empty.opened(),null);
});
test('both challenge card variants expose the new action and accessible progress',()=>{
 const r=runtime();for(const locker of [false,true]){const html=r.run(`challengeCard({challenge:"daily",label:"Daily challenge",title:"Hat Trick",copy:"Finish three dailies.",count:4,action:"Pick me a random game",locker:${locker}})`);assert(html.includes('data-challenge="daily"'));assert(html.includes('Pick me a random game'));assert(html.includes('3 of 3 complete'));assert(!html.includes('data-open='));}
});
test('forfeited Bench Boss runs give no XP, badges, or daily/weekly challenge credit',()=>{
 const r=runtime();r.history({'classic:2026-10-13':{w:true,n:1},'shoot:2026-10-13':{w:false,s:4},'benchboss:2026-10-13':{w:false,s:0,forfeit:true}});
 assert.equal(r.run('xpFor({s:0,w:false,forfeit:true})'),0);assert.equal(r.run('dailyEntries(dayKey()).length'),2);assert.equal(r.run('progressSummary().entries.length'),2);assert.equal(r.run('achievementList().find(x=>x.id==="hat-trick").on'),false);assert.equal(r.run('completedThisWeek("benchboss")'),false);
 r.history({'benchboss:2026-10-13':{w:false,s:0}});r.storage.set('sweater-benchboss-daily',JSON.stringify({date:'2026-10-13',guesses:['END']}));assert.equal(r.run('progressSummary().xp'),0,'Legacy reveals lose their accidental XP on reload');
 r.history({'benchboss:2026-10-13':{w:true,s:10}});r.run('archiveGet = () => ({guesses:["END"]})');assert.equal(r.run('progressSummary().xp'),75,'An archive forfeit cannot erase a completed daily win');
});
console.log(`${checks} challenge checks passed: random library/category draws, weekly persistence, progression, forfeits, readiness, routing and accessibility.`);
