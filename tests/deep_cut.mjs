import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {DEEP_CUT_MODEL as M} from '../static/deep-cut/model.mjs';
import {scoreGame} from '../backend/src/existing-api.mjs';
const data=JSON.parse(fs.readFileSync('static/deep-cut/data.json','utf8')),ix=M.index(data);
let checks=0;
function test(name,fn){fn();console.log('PASS',name);checks++;}
const player=name=>[...ix.players.values()].find(p=>p.name===name)?.id;
test('every daily/practice set has seven families and browser/server score parity',()=>{
  for(const run of data.runs){
    assert.equal(new Set(run.prompts.map(id=>ix.prompts.get(id).family)).size,7);
    const perfect=run.prompts.map(id=>String(ix.prompts.get(id).answers.find(a=>a[1]===100)[0]));
    assert.equal(M.state(run,perfect,data).score,700);
    assert.deepEqual(scoreGame('deepcut',{id:run.id},perfect,{deepcut:data}),{won:true,tries:7,points:700});
    assert.deepEqual(scoreGame('deepcut',{id:run.id},Array(7).fill('MISS'),{deepcut:data}),{won:false,tries:7,points:0});
  }
});
test('name matching accepts accents, aliases, unique surnames and transposed letters',()=>{
  const cases=[['Jaromir Jagr','team-PIT'],['Jagr','team-PIT'],['Joe Thorntno','team-SJS'],['Ovi','team-WSH'],['van Riemsdyk','team-TOR']];
  for(const [name,prompt] of cases)assert.equal(M.match(name,prompt,data).status,'accepted',name);
  assert.equal(M.match('Jaromír Jágr','team-PIT',data).id,player('Jaromir Jagr'));
  assert.equal(M.match('  Wayne-Gretzky  ','team-EDM',data).status,'accepted');
});
test('ambiguous names, nonexistent names, and correct names in the wrong category are not awarded',()=>{
  assert.equal(M.match('Sedin','team-VAN',data).status,'ambiguous');
  assert.equal(M.match('Henrik Sedin','team-VAN',data).status,'accepted');
  assert.equal(M.match('Wayne Gretzky','country-RUS',data).status,'wrong');
  assert.equal(M.match('zzzznotaplayerzzzz','team-VAN',data).status,'missing');
  assert.equal(M.match('','team-VAN',data).status,'missing');
  assert.equal(M.match('roy','team-MTL',data).status,'ambiguous');
});
test('unfinished and fabricated leaderboard logs are rejected',()=>{
  const run=data.runs[0],correct=run.prompts.map(id=>String(ix.prompts.get(id).answers[0][0]));
  for(const log of [correct.slice(0,6),[...correct,'MISS'],['9999999',...correct.slice(1)],['100:9999999',...correct.slice(1)],[100,...correct.slice(1)]])assert.throws(()=>scoreGame('deepcut',{id:run.id},log,{deepcut:data}),e=>e.status===400);
  assert.throws(()=>scoreGame('deepcut',{id:'unknown'},correct,{deepcut:data}),e=>e.status===503);
  const p=ix.prompts.get(run.prompts[0]),invalid=[...ix.players.keys()].find(id=>!p.points.has(id));
  assert.throws(()=>M.state(run,[String(invalid)],data));
  assert.equal(M.normalize('<script>alert(1)</script>'),'scriptalert1script');
});
function runtime(){
  let now=Date.parse('2026-11-04T17:00:00Z'),serial=0;
  const timers=new Map(),elements=new Map(),records=new Map(),events=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,{id,hidden:false,disabled:true,value:'',textContent:'',innerHTML:'',style:{},dataset:{},classList:{add(){},remove(){},toggle(){}},setAttribute(){},addEventListener(name,fn){events.set(id+':'+name,fn);},querySelectorAll(){return [];},focus(){this.focused=true;},select(){this.selected=true;},getContext(){return null;}});return elements.get(id);};
  class Clock extends Date{static now(){return now;}}
  const bodyClasses=new Set(),body={classList:{add:k=>bodyClasses.add(k),remove:k=>bodyClasses.delete(k),contains:k=>bodyClasses.has(k),toggle(k,on){if(on)bodyClasses.add(k);else bodyClasses.delete(k);}}};
  const ctx=vm.createContext({console,Date:Clock,Math,Map,Set,performance:{now:()=>now},G:{},S:{deepcut:{target:data.runs[0],guesses:[],opts:{},over:false,day:'2026-11-04'}},game:'deepcut',mode:'daily',onHub:false,$:el,
    document:{body,hidden:false,addEventListener(){}},window:{addEventListener(){}},store:{get:k=>records.get(k),set:(k,v)=>records.set(k,JSON.parse(JSON.stringify(v)))},matchMedia:()=>({matches:true}),esc:s=>String(s),hash:()=>0,pick:a=>a[0],dailyNumber:()=>1,
    setInterval:fn=>{timers.set(++serial,fn);return serial;},clearInterval:id=>timers.delete(id),setTimeout:()=>++serial,clearTimeout(){},requestAnimationFrame:()=>++serial,cancelAnimationFrame(){},saveProgress(){records.set('saved',JSON.parse(JSON.stringify(ctx.S.deepcut.opts)));},toast(){},DEEP_CUT_MODEL:M});
  ctx.doGuess=action=>{const st=ctx.S.deepcut,g=ctx.G.deepcut;if(g.guess(st.target,action)===null)return;st.guesses.push(action);st.over=g.isDone(st.target,st.guesses);ctx.saveProgress();g.render(st.target,st);};
  const source=fs.readFileSync('static/deep-cut/game.js','utf8').replace('/*__DEEP_CUT_DATA__*/{}',JSON.stringify(data));vm.runInContext(source,ctx);
  vm.runInContext('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts);G.deepcut.reset();G.deepcut.render(S.deepcut.target,S.deepcut)',ctx);
  return {ctx,el,records,timers,run:s=>vm.runInContext(s,ctx),advance(ms){now+=ms;for(const fn of [...timers.values()])fn();}};
}
test('a round has a three-second preview, a fixed deadline, and a three-second wrong-answer penalty',()=>{
  const r=runtime();r.run('dcBegin()');assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'preview');assert.equal(r.el('dcAnswer').disabled,true);
  r.advance(3000);assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'ask');assert.equal(r.el('dcAnswer').disabled,false);
  const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;r.el('dcAnswer').value='zzzznotaplayerzzzz';r.run('dcSubmit({preventDefault(){}})');
  assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline-3000);assert.equal(r.ctx.S.deepcut.guesses.length,0);
  r.advance(32000);assert.deepEqual([...r.ctx.S.deepcut.guesses],['MISS']);assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'reveal');assert.equal(r.timers.size,0);
});
test('reload/restoration and leaving the game never reset a running clock',()=>{
  const r=runtime();r.run('dcBegin()');r.advance(6000);const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
  r.run('dcCleanup();G.deepcut.reset();G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts);G.deepcut.render(S.deepcut.target,S.deepcut)');
  assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.timers.size,1);
  r.run('dcCleanup()');r.advance(40000);r.run('G.deepcut.render(S.deepcut.target,S.deepcut)');
  assert.deepEqual([...r.ctx.S.deepcut.guesses],['MISS']);assert.equal(r.timers.size,0,'Expired restored round must not leave a timer running');
});
test('passes and accepted names complete all seven rounds without double submissions or premature answer reveal',()=>{
  const r=runtime();
  assert(!r.el('dcBoard').innerHTML.includes('data-dc-sheet'));
  for(let i=0;i<7;i++){
    r.run('dcBegin()');r.advance(3000);const run=r.ctx.S.deepcut.target,id=ix.prompts.get(run.prompts[i]).answers.find(a=>a[1]===100)[0];
    r.run(`dcLand('${id}');dcLand('MISS')`);assert.equal(r.ctx.S.deepcut.guesses.length,i+1);
    if(i<6)assert(!r.el('dcBoard').innerHTML.includes('data-dc-sheet'));
  }
  assert.equal(r.ctx.S.deepcut.over,true);assert.equal(r.ctx.G.deepcut.score(r.ctx.S.deepcut.target,r.ctx.S.deepcut.guesses),700);
  assert(r.el('dcBoard').innerHTML.includes('data-dc-sheet'));assert.equal(r.timers.size,0);
});
test('corrupt saved timer state is reset safely',()=>{
  const r=runtime();r.ctx.S.deepcut.opts.dcRun={target:r.ctx.S.deepcut.target.id,index:0,phase:'ask',deadline:null};r.run('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts)');assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'ready');
});
test('jumbotron clock preserves tenths and turns expired time into zero',()=>{
 const r=runtime();
 for(const [ms,expected] of [[35000,'0:35.0'],[34900,'0:34.9'],[5010,'0:05.1'],[5000,'0:05.0'],[100,'0:00.1'],[0,'0:00.0'],[-10,'0:00.0']]){
  r.run(`dcPaintClock(${ms},false)`);assert.equal(r.el('dcClockText').textContent,expected);
 }
 r.run('dcBegin()');r.advance(3000);r.el('dcAnswer').value='zzzznotaplayerzzzz';r.run('dcSubmit({preventDefault(){}})');assert.equal(r.el('dcClockText').textContent,'0:32.0');
});
test('rarer accepted answers have six distinct celebration levels and new prompts clear prior effects',()=>{
 const r=runtime();r.ctx.matchMedia=()=>({matches:false});
 const complete=data.prompts.filter(p=>[10,15,30,60,85,100].every(score=>p.answers.some(a=>a[1]===score))).slice(0,7);
 r.ctx.S.deepcut.target={id:'animation-fixture',prompts:complete.map(p=>p.id)};r.run('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts)');
 for(const [i,score] of [10,15,30,60,85,100].entries()){
  r.run('dcBegin()');assert.equal(r.el('dcCabinet').dataset.celebration,undefined);r.advance(3000);
  const id=complete[i].answers.find(a=>a[1]===score)[0];r.run(`dcLand('${id}')`);
  assert.equal(r.el('dcCabinet').dataset.celebration,i+1);assert.equal(r.run('dcAnimation.score'),score);assert.equal(r.run('dcAnimation.level'),i+1);
 }
 r.run('dcCleanup()');assert.equal(r.el('dcCabinet').dataset.celebration,undefined);assert.equal(r.el('dcZoneAnnouncement').hidden,true);assert.equal(r.timers.size,0);
});
test('arena progression uses total points and announces each next threshold',()=>{
 const r=runtime();
 for(const [points,name,next] of [[0,'NEIGHBOURHOOD','150'],[149,'NEIGHBOURHOOD','150'],[150,'COMMUNITY','300'],[299,'COMMUNITY','300'],[300,'BIG LEAGUES','450'],[450,'RAFTERS','600'],[600,'LEGENDS','700'],[700,'LEGENDS','700']]){
  r.run(`dcHud({score:${points},distance:${points*10},rounds:[],over:false})`);assert(r.el('dcArenaTag').textContent.includes(name));assert(r.el('dcNextZone').textContent.includes(next));
 }
});
test('hidden game refreshes cannot trap the home page in fullscreen or start a background timer',()=>{
 const r=runtime();r.run('dcBegin()');assert(r.run('document.body.classList.contains("dc-immersive")'));
 r.run('dcCleanup();onHub=true;G.deepcut.render(S.deepcut.target,S.deepcut)');assert.equal(r.run('document.body.classList.contains("dc-immersive")'),false);assert.equal(r.timers.size,0);
 r.run('onHub=false;G.deepcut.render(S.deepcut.target,S.deepcut)');assert(r.run('document.body.classList.contains("dc-immersive")'));assert.equal(r.timers.size,1);
});
console.log(`${checks} Deep Cut checks passed`);
