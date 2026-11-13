import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {DEEP_CUT_MODEL as M} from '../static/deep-cut/model.mjs';
import {DEEP_CUT_SCENERY as SCENERY} from '../static/deep-cut/scenery.mjs';
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
test('Mike Cammalleri is accepted for Calgary and every other qualifying prompt at his existing score',()=>{
  const id=8469500,calgary=ix.prompts.get('team-CGY');assert(calgary.points.has(id));
  for(const name of ['Mike Cammalleri','mike cammalleri','Michael Cammalleri','Mike Cammalleri 1982','Mike Cammaleri']){
    const hit=M.match(name,'team-CGY',data);assert.equal(hit.status,'accepted',name);assert.equal(hit.id,id);assert.equal(hit.score,calgary.points.get(id));
  }
  for(const prompt of data.prompts){
    const hit=M.match('Mike Cammalleri',prompt.id,data);
    assert.equal(hit.status,prompt.answers.some(a=>a[0]===id)?'accepted':'wrong',prompt.id);
    if(hit.status==='accepted')assert.equal(hit.score,ix.prompts.get(prompt.id).points.get(id));
  }
  const run=data.runs.find(run=>run.prompts.includes('team-CGY')),actions=run.prompts.map(key=>String(key==='team-CGY'?id:ix.prompts.get(key).answers[0][0]));
  assert.deepEqual(scoreGame('deepcut',{id:run.id},actions,{deepcut:data}),M.result(run,actions,data));
});
test('common given-name aliases retain surnames and respect exact identities and ambiguity',()=>{
  const cases=[['Mike Cammalleri','Michael Cammalleri'],['Matthew Duchene','Matt Duchene'],['Christopher Tanev','Chris Tanev'],['William Guerin','Bill Guerin'],['Joseph Sakic','Joe Sakic']];
  for(const [alias,canonical] of cases){const id=player(canonical);assert(id,canonical);const p=data.prompts.find(p=>p.answers.some(a=>a[0]===id));assert.equal(M.match(alias,p.id,data).id,id,alias);}
  const fixture={players:[[1111111,'Michael Smith',1980],[2222222,'Michael Smith',1985],[3333333,'Mike Smith',1990]],prompts:[{id:'all',answers:[[1111111,10],[2222222,60],[3333333,85]]},{id:'one',answers:[[1111111,10]]}],runs:[]};
  assert.equal(M.match('Mike Smith','all',fixture).id,3333333,'An exact canonical name takes priority over nickname aliases');
  assert.equal(M.match('Michael Smith','all',fixture).status,'ambiguous');
  assert.equal(M.match('Mike Smith 1980','all',fixture).id,1111111,'Aliases also support birth-year disambiguation');
  assert.equal(M.match('Mike Smith','one',fixture).status,'wrong','An exact name cannot become a different eligible player');
  assert.equal(M.match('Mike Jones','all',fixture).status,'missing','A shared first name does not establish a player match');
});
test('answer corrections support useful partial names and hard spellings without guessing short fragments',()=>{
  for(const text of ['Cammal','Mike Camm','Niederretr','Niederrieter']){
    const prompt=text.startsWith('Nied')?'team-MIN':'team-CGY',id=prompt==='team-MIN'?8475799:8469500;
    const hit=M.match(text,prompt,data);assert.equal(hit.status,'accepted',text);assert.equal(hit.id,id,text);
  }
  for(const text of ['Mike','Camm','Mike Ca','Tkach'])assert.equal(M.match(text,'team-CGY',data).status,'missing',text);
  assert.equal(M.match('Sedin','team-VAN',data).status,'ambiguous');
  assert.equal(M.match('Wayne Gretzky','country-RUS',data).status,'wrong');
  const fixture={players:[[1111111,'Adam Examplelong',1980],[2222222,'Adam Examplerong',1981]],prompts:[{id:'one',answers:[[2222222,100]]}],runs:[]};
  assert.equal(M.match('Adam Examplelonx','one',fixture).status,'wrong','A nearer nonqualifying identity cannot be replaced by a more distant qualifying player');
});
test('turning corrections off requires full names but still ignores accents, case and punctuation',()=>{
  const off={corrections:false};
  for(const text of ['Cammalleri','Mike Camm','Michael Cammaleri'])assert.equal(M.match(text,'team-CGY',data,off).status,'missing',text);
  assert.equal(M.match('Mike Cammalleri','team-CGY',data,off).id,8469500,'Known complete name variants remain valid with spelling assistance off');
  assert.equal(M.match('MICHAEL CAMMALLERI','team-CGY',data,off).id,8469500);
  assert.equal(M.match('Jaromír-Jágr','team-PIT',data,off).id,8448208);
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
    setInterval:fn=>{timers.set(++serial,fn);return serial;},clearInterval:id=>timers.delete(id),setTimeout:()=>++serial,clearTimeout(){},requestAnimationFrame:()=>++serial,cancelAnimationFrame(){},saveProgress(){records.set('saved',JSON.parse(JSON.stringify(ctx.S.deepcut.opts)));},toast(){},DEEP_CUT_MODEL:M,DEEP_CUT_SCENERY:SCENERY});
  ctx.doGuess=action=>{const st=ctx.S.deepcut,g=ctx.G.deepcut;if(g.guess(st.target,action)===null)return;st.guesses.push(action);st.over=g.isDone(st.target,st.guesses);ctx.saveProgress();g.render(st.target,st);};
  const source=fs.readFileSync('static/deep-cut/game.js','utf8').replace('/*__DEEP_CUT_DATA__*/{}',JSON.stringify(data));vm.runInContext(source,ctx);
  vm.runInContext('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts);G.deepcut.reset();G.deepcut.render(S.deepcut.target,S.deepcut)',ctx);
  return {ctx,el,records,timers,events,run:s=>vm.runInContext(s,ctx),advance(ms){now+=ms;for(const fn of [...timers.values()])fn();}};
}
test('a round has a three-second preview and wrong or unrecognized guesses never shorten its deadline',()=>{
  const r=runtime();r.run('dcBegin()');assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'preview');assert.equal(r.el('dcAnswer').disabled,true);
  r.advance(3000);assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'ask');assert.equal(r.el('dcAnswer').disabled,false);
  const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;r.el('dcAnswer').value='zzzznotaplayerzzzz';r.run('dcSubmit({preventDefault(){}})');
  assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.guesses.length,0);
  assert(!r.el('dcFeedback').textContent.includes('seconds'));
  r.advance(32000);assert.equal(r.ctx.S.deepcut.guesses.length,0);assert.equal(r.el('dcClockText').textContent,'0:03.0');
  r.advance(3000);assert.deepEqual([...r.ctx.S.deepcut.guesses],['MISS']);assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'reveal');assert.equal(r.timers.size,0);
});
test('submitting Mike Cammalleri locks the correct Calgary player without a time penalty',()=>{
  const r=runtime();r.ctx.S.deepcut.target={id:'calgary-alias-fixture',prompts:['team-CGY',...data.runs[0].prompts.filter(id=>id!=='team-CGY').slice(0,6)]};
  r.run('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts);dcBegin()');r.advance(3000);const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
  r.el('dcAnswer').value='Mike Cammalleri';r.run('dcSubmit({preventDefault(){}})');
  assert.deepEqual([...r.ctx.S.deepcut.guesses],['8469500']);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.opts.dcRun.phase,'reveal');
});
test('wrong players, missing names, arbitrary text and blanks keep the same deadline with corrections on or off',()=>{
 for(const corrections of [true,false]){
  const r=runtime();r.ctx.S.deepcut.target={id:'no-penalty-fixture',prompts:['country-RUS',...data.runs[0].prompts.filter(id=>id!=='country-RUS').slice(0,6)]};
  r.run('G.deepcut.prepareTarget(S.deepcut.target,S.deepcut.opts);dcBegin()');r.advance(3000);r.el('dcCorrections').checked=corrections;r.run('$("dcCorrections").onchange()');
  const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
  for(const answer of ['Wayne Gretzky','zzzznotaplayerzzzz','anything at all','   ']){
   r.el('dcAnswer').value=answer;r.run('dcSubmit({preventDefault(){}})');assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.guesses.length,0);assert(!r.el('dcFeedback').textContent.includes('−3'));
  }
  r.advance(2000);assert.equal(r.el('dcClockText').textContent,'0:33.0');assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);
 }
});
test('the corrections preference defaults on, persists, and never resets an active clock',()=>{
  const r=runtime();assert.equal(r.el('dcCorrections').checked,true);r.run('dcBegin()');r.advance(3000);const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
  r.el('dcCorrections').checked=false;r.run('$("dcCorrections").onchange()');assert.equal(r.records.get('sweater-deepcut-corrections'),false);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);
  r.run('dcCleanup();G.deepcut.reset();G.deepcut.render(S.deepcut.target,S.deepcut)');assert.equal(r.el('dcCorrections').checked,false);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);
  r.el('dcCorrections').checked=true;r.run('$("dcCorrections").onchange()');assert.equal(r.records.get('sweater-deepcut-corrections'),true);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);
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
 r.run('dcBegin()');r.advance(3000);r.el('dcAnswer').value='zzzznotaplayerzzzz';r.run('dcSubmit({preventDefault(){}})');assert.equal(r.el('dcClockText').textContent,'0:35.0');
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
test('deeper answers sprint faster with quicker strides and begin braking sooner',()=>{
 let previous=null;
 for(const score of [10,15,30,60,85,100]){
  const m=SCENERY.skateMotion(score,500);
  assert.equal(m.phase,'sprint');assert(m.speed>0&&m.cadence>0);
  if(previous){assert(m.speed>previous.speed);assert(m.cadence>previous.cadence);assert(m.runMs<previous.runMs);assert(m.travelPixels>previous.travelPixels);}
  previous=m;
 }
 assert.equal(SCENERY.skateMotion(0,500).speed,0);
});
test('skating acceleration and braking are continuous and finish at the exact awarded distance',()=>{
 for(const score of [10,15,30,60,85,100]){
  const profile=SCENERY.skateMotion(score,0);let previous=profile;
  for(let time=0;time<=profile.duration+100;time+=10){
   const m=SCENERY.skateMotion(score,time);
   assert(m.distanceRatio>=previous.distanceRatio&&m.distanceRatio<=1);assert(m.travelPixels>=previous.travelPixels);assert(m.speed>=0);
   assert(Math.abs(m.speed-previous.speed)<20,'No jump in camera speed at phase boundaries');previous=m;
  }
  const ended=SCENERY.skateMotion(score,profile.duration),late=SCENERY.skateMotion(score,profile.duration+2000);
  assert.equal(ended.done,true);assert.equal(ended.distanceRatio,1);assert.equal(ended.speed,0);assert.equal(ended.turn,0);assert.equal(ended.travelPixels,late.travelPixels);
 }
 const m=SCENERY.skateMotion(100,1500);assert(m.turn>.9);assert(m.speed<SCENERY.skateMotion(100,500).speed);
});
test('the deepest pull turns onto the edges with a larger snow fan and one puck at the stick toe',()=>{
 const render=(score,time)=>{
  const rows=[],motion=SCENERY.skateMotion(score,time),puck=SCENERY.skater((...row)=>rows.push(row),{x:55,foot:240,zone:2,motion});
  assert(rows.every(row=>row.slice(0,4).every(Number.isFinite)));assert.equal(puck.y,240);
  const blade=rows.find(row=>row[4]==='#eee9cd');assert.equal(puck.x,blade[0]+13);
  return {rows,snow:rows.filter(row=>/^#(?:edfff8|b8e2ed)[0-9a-f]{2}$/.test(row[4])).length,puck};
 };
 const common=render(10,SCENERY.skateMotion(10,0).runMs+180),deep=render(85,1380),legend=render(100,1230);
 assert.equal(common.snow,0);assert(deep.snow>20);assert(legend.snow>deep.snow);assert(legend.puck.x<common.puck.x,'The blade and puck tuck in during the stop');
 const duration=SCENERY.skateMotion(100,0).duration;assert.equal(render(100,duration).snow,0);
});
test('the rink comes to rest after a stop and animation cleanup never changes the game clock or score',()=>{
 const r=runtime();r.ctx.matchMedia=()=>({matches:false});
 const c={fillRect(){},beginPath(){},moveTo(){},lineTo(){},closePath(){},fill(){},ellipse(){}};
 r.el('dcCanvas').getContext=()=>c;r.el('dcCanvas').getBoundingClientRect=()=>({left:0,top:0,width:1440,height:900});
 r.run('dcBegin()');r.advance(3000);const p=ix.prompts.get(r.ctx.S.deepcut.target.prompts[0]),id=p.answers.find(a=>a[1]===100)[0],deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
 r.run(`dcLand('${id}')`);const start=r.run('dcAnimation.start'),duration=r.run('dcAnimation.duration');
 r.run(`dcDraw(${start+600})`);const first=r.run('dcOffset');assert(first>0);
 r.run(`dcDraw(${start+600})`);assert.equal(r.run('dcOffset'),first,'Drawing twice at one timestamp must not advance the rink');
 r.run(`dcDraw(${start+duration+10})`);assert.equal(r.run('dcAnimation'),null);const stopped=r.run('dcOffset');
 r.run(`dcDraw(${start+duration+1000})`);assert.equal(r.run('dcOffset'),stopped);assert.equal(r.run('dcVisualDistance'),1000);
 assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.guesses.length,1);assert.equal(r.ctx.G.deepcut.score(r.ctx.S.deepcut.target,r.ctx.S.deepcut.guesses),100);
 r.run('dcBegin();dcCleanup()');assert.equal(r.run('dcAnimation'),null);assert.equal(r.run('dcOffset'),stopped);
});
test('reduced motion suppresses the sprint, stop and snow while keeping the awarded points',()=>{
 for(const score of [10,15,30,60,85,100]){
  const a=SCENERY.skateMotion(score,0,true),b=SCENERY.skateMotion(score,1500,true);
  assert.deepEqual(a,b);assert.equal(a.speed,0);assert.equal(a.turn,0);assert.equal(a.done,true);assert.equal(a.distanceRatio,1);
 }
 const r=runtime();r.run('dcBegin()');r.advance(3000);const p=ix.prompts.get(r.ctx.S.deepcut.target.prompts[0]),id=p.answers.find(a=>a[1]===100)[0];r.run(`dcLand('${id}')`);
 assert.equal(r.run('dcAnimation'),null);assert.equal(r.run('dcVisualDistance'),1000);assert.equal(r.run('dcOffset'),0);
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
test('rink clicks use the visible zone and leave the running clock, answers and score untouched',()=>{
 const r=runtime();r.ctx.matchMedia=()=>({matches:false});r.el('dcCanvas').getBoundingClientRect=()=>({left:0,top:0,right:900,bottom:600,width:900,height:600});
 r.run('dcBegin()');r.advance(3000);const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
 const palettes=[];
 for(let zone=0;zone<5;zone++){
  r.run(`dcClearRinkParticles();dcVisualDistance=${zone*1500};dcSprinkleRink(60,90)`);
  assert.equal(r.run('dcRinkParticles.length'),10);assert(r.run(`dcRinkParticles.every(p=>p.zone===${zone}&&p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1)`));palettes.push(r.run('dcRinkParticles[0].color'));
 }
 assert.equal(new Set(palettes).size,5);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.guesses.length,0);
});
test('rink particles have a hard limit, expire, and clear when their scene or game changes',()=>{
 const r=runtime();r.ctx.matchMedia=()=>({matches:false});r.el('dcCanvas').getBoundingClientRect=()=>({left:0,top:0,right:900,bottom:600,width:900,height:600});
 r.run('for(let i=0;i<50;i++)dcSprinkleRink(60,90)');assert.equal(r.run('dcRinkParticles.length'),120);
 r.ctx.paint=()=>{};r.ctx.canvasContext={globalAlpha:1};r.run('dcDrawRinkParticles(canvasContext,paint,performance.now()+1300,300,200,3,0)');assert.equal(r.run('dcRinkParticles.length'),0);assert.equal(r.ctx.canvasContext.globalAlpha,1);
 r.run('dcSprinkleRink(60,90);dcDrawRinkParticles(canvasContext,paint,performance.now(),300,200,3,1)');assert.equal(r.run('dcRinkParticles.length'),0);
 r.run('dcSprinkleRink(-1,90);dcSprinkleRink(901,90)');assert.equal(r.run('dcRinkParticles.length'),0);
 r.run('dcSprinkleRink(60,90);dcCleanup()');assert.equal(r.run('dcRinkParticles.length'),0);assert.equal(r.run('dcRinkPointer'),null);
});
test('scenery pointer effects respect controls, reduced motion and inactive games without canceling events',()=>{
 const r=runtime();r.el('dcCanvas').getBoundingClientRect=()=>({left:0,top:0,right:900,bottom:600,width:900,height:600});
 const click={button:0,pointerId:1,isPrimary:true,clientX:60,clientY:90,target:{closest:()=>null},preventDefault(){throw Error('Do not cancel native pointer behavior');}};
 const down=r.events.get('dcCabinet:pointerdown');down(click);assert.equal(r.run('dcRinkParticles.length'),0,'Reduced motion disables scenery particles');
 r.ctx.matchMedia=()=>({matches:false});down({...click,target:{closest:()=>({})}});assert.equal(r.run('dcRinkParticles.length'),0,'Controls and panels do not spawn effects');
 down(click);assert.equal(r.run('dcRinkParticles.length'),10);
 r.run('dcClearRinkParticles();onHub=true');down(click);assert.equal(r.run('dcRinkParticles.length'),0);
});
test('community spectators stand, use the aisle, exit through the door, and return without jumping',()=>{
 for(const W of [160,188,480,640])for(let i=0;i<3;i++){
  const stages=new Set();let previous=null;
  for(let ms=0;ms<=64000;ms+=100){
   const actor=SCENERY.communityActor(i,W,228,ms);stages.add(actor.stage);
   assert(Number.isFinite(actor.x)&&Number.isFinite(actor.y));assert(actor.x>=0&&actor.x<W);
   if(previous?.visible&&actor.visible)assert(Math.hypot(actor.x-previous.x,actor.y-previous.y)<Math.max(3,W*.02));
   if(actor.stage==='outside'){assert.equal(actor.visible,false);assert(Math.abs(actor.x-(W*.82+7))<.001);assert.equal(actor.y,189);}
   previous=actor;
  }
  for(const stage of ['seated','standing','to-aisle','up-steps','to-door','outside','returning','down-steps','to-seat'])assert(stages.has(stage),stage);
 }
});
test('larger arenas have two bowls, separated aisles and ribbon screens, and about 75 percent occupied seats',()=>{
 for(const [W,ice] of [[160,99],[188,254],[480,228],[640,300]]){
  const layout=SCENERY.arenaLayout(W,ice);assert(layout.upperBottom<layout.ribbonY);assert(layout.ribbonY<layout.lowerTop);
  for(const bowl of [0,1]){const seats=layout.seats.filter(s=>s.bowl===bowl),fill=seats.filter(s=>s.occupied).length/seats.length;assert(fill>=.7&&fill<=.8,`${W}/${ice}: ${fill}`);}
  for(const seat of layout.seats){const section=layout.sections.find(s=>s.index===seat.section);assert(seat.x<section.aisle-4);}
  assert(layout.travellers.length>0);assert(layout.travellers.every(seat=>seat.occupied));
 }
});
test('fans turn left, right or down toward the actual rink action instead of sharing one fixed gaze',()=>{
 const x=200,head=90;
 assert.equal(SCENERY.fanGaze(x,head,{x:30,y:220}).direction,-1);
 assert.equal(SCENERY.fanGaze(x,head,{x:370,y:220}).direction,1);
 const down=SCENERY.fanGaze(x,head,{x,y:220}),up=SCENERY.fanGaze(x,head,{x,y:30});
 assert.equal(down.direction,0);assert(down.eyeY>up.eyeY);assert.equal(down.headShift,0);
 assert(Math.abs(SCENERY.fanGaze(x,40,{x:30,y:220}).headShift)<Math.abs(SCENERY.fanGaze(x,170,{x:30,y:220}).headShift),'The upper bowl looks more steeply down toward the ice');
 for(let target=-100;target<=500;target+=5){const g=SCENERY.fanGaze(x,head,{x:target,y:220});assert(Number.isFinite(g.headShift)&&Math.abs(g.headShift)<=.65);assert(g.eyeY>=1&&g.eyeY<=2.8);}
 for(const seed of [8,9])for(const pose of ['sit','stand','cheer']){
  const eyes=target=>{const rows=[];SCENERY.person((...p)=>rows.push(p),x,110,seed,{pose,zone:3,cheer:1,carry:'popcorn',lookAt:target});assert(rows.every(p=>p.slice(0,4).every(Number.isFinite)));return rows.filter(p=>p[4]==='#1b2937');};
  assert(eyes({x:0,y:230}).every(p=>p[0]<x));assert(eyes({x:400,y:230}).every(p=>p[0]>x));
  const center=eyes({x,y:230});assert.equal(center.length,2);assert(center[0][0]<x&&center[1][0]>x);
 }
});
test('both bowls and standing fans follow the supplied skater in levels three through five',()=>{
 for(const [W,ice] of [[160,99],[188,254],[480,228],[640,300]])for(const zone of [2,3,4]){
  const eyes=watchTarget=>{const rows=[];SCENERY.arena((...p)=>{if(p[4]==='#1b2937')rows.push(p);},{W,ice,zone,still:true,time:0,watchTarget});return rows;};
  const left=eyes({x:-1000,y:ice+40}),right=eyes({x:W+1000,y:ice+40}),layout=SCENERY.arenaLayout(W,ice,zone);
  assert.equal(left.length,layout.seats.filter(s=>s.occupied).length+layout.travellers.filter(s=>s.standingRoom).length);
  assert.equal(left.length,right.length);for(let i=0;i<left.length;i++)assert(left[i][0]<right[i][0]);
 }
});
test('the game passes its moving skater position to the crowd on every arena frame',()=>{
 const r=runtime(),gazes=[],sprites=[];r.ctx.matchMedia=()=>({matches:false});
 r.ctx.DEEP_CUT_SCENERY={...SCENERY,arena(p,options){gazes.push(options.watchTarget);return SCENERY.arena(p,options);},skater(p,options){sprites.push(options);return SCENERY.skater(p,options);}};
 r.el('dcCanvas').getContext=()=>({fillRect(){},beginPath(){},moveTo(){},lineTo(){},closePath(){},fill(){},ellipse(){}});
 r.el('dcCanvas').getBoundingClientRect=()=>({left:0,top:0,width:1440,height:900});
 for(const from of [3000,4500,6000]){
  r.run(`dcAnimation={start:0,duration:2030,offset:0,from:${from},to:${from+1000},score:100,level:6,color:'#ffdb82'}`);
  for(const time of [500,1400]){r.run(`dcDraw(${time})`);const gaze=gazes.at(-1),sprite=sprites.at(-1);assert.equal(gaze.x,sprite.x+7+sprite.motion.lean*.6);assert.equal(gaze.y,sprite.foot-20+sprite.motion.bob+sprite.motion.turn*3);}
  assert.notEqual(gazes.at(-1).x,gazes.at(-2).x,'Eyes track the sprint-to-stop position change');
 }
 assert.equal(r.ctx.S.deepcut.guesses.length,0);
});
test('concessions trips leave seats vacant, return with snacks, and stay on continuous aisle paths',()=>{
 for(const seat of SCENERY.arenaLayout(480,228).travellers){
  let previous=null,sawAway=false,sawSnack=false;
  for(let ms=0;ms<=64000;ms+=100){
   const actor=SCENERY.arenaActor(seat,ms);
   if(previous?.visible&&actor.visible)assert(Math.hypot(actor.x-previous.x,actor.y-previous.y)<3);
   if(!actor.visible){sawAway=true;assert.equal(actor.stage,'concessions');assert.equal(actor.x,seat.door);}
   if(actor.stage==='returning'){sawSnack=true;assert(['popcorn','drink'].includes(actor.carry));}
   previous=actor;
  }
  assert(sawAway&&sawSnack);
 }
});
test('reduced motion freezes spectators, ribbon screens and vending flicker in every indoor scene',()=>{
 const capture=(zone,time,still)=>{const commands=[],paint=(...args)=>commands.push(args);if(zone===1)SCENERY.community(paint,{W:480,ice:228,time,still});else SCENERY.arena(paint,{W:480,ice:228,time,still,zone});return commands;};
 for(let zone=1;zone<5;zone++)assert.deepEqual(capture(zone,0,true),capture(zone,47200,true));
 assert.notDeepEqual(capture(1,0,false),capture(1,14200,false));assert.notDeepEqual(capture(2,0,false),capture(2,47200,false));
 assert.equal(SCENERY.vendingLit(1,14200),false);assert.equal(SCENERY.vendingLit(0,14200),true);assert.equal(SCENERY.vendingLit(1,14200,true),true);assert.equal(SCENERY.vendingLit(1,16000),true);
});
test('crowd density grows from big leagues to rafters to a full legends crowd, including concessions trips',()=>{
 for(const [W,ice] of [[160,99],[188,254],[480,228],[640,300]])for(const [zone,min,max] of [[2,.7,.8],[3,.85,.9],[4,1,1]]){
  const layout=SCENERY.arenaLayout(W,ice,zone),occupied=layout.seats.filter(seat=>seat.occupied).length;
  for(let time=0;time<=64000;time+=500){
   const away=layout.travellers.filter(seat=>!seat.standingRoom&&SCENERY.arenaActor(seat,time).pose!=='sit').length;
   const fill=(occupied-away)/layout.seats.length;assert(fill>=min&&fill<=max,`${W}/${ice}/${zone}/${time}: ${fill}`);
  }
 }
});
test('the crowd wave travels across the lower bowl, then follows through the upper bowl and ends',()=>{
 const wave={start:0},left={x:48,bowl:0,row:0},right={x:432,bowl:0,row:0},upper={...left,bowl:1};
 assert(SCENERY.waveLift(left,480,945,wave)>.99);assert.equal(SCENERY.waveLift(right,480,945,wave),0);
 assert(SCENERY.waveLift(right,480,3505,wave)>.99);assert.equal(SCENERY.waveLift(left,480,3505,wave),0);
 assert(SCENERY.waveLift(upper,480,1595,wave)>.99);assert.equal(SCENERY.waveLift(upper,480,400,wave),0);
 for(const seat of [left,right,upper])assert.equal(SCENERY.waveLift(seat,480,6200,wave),0);
 assert.equal(SCENERY.waveLift(left,480,945,null),0);
});
test('interactive waves respect cooldown, cleanup and reduced motion and never reset the answer clock',()=>{
 const r=runtime();r.ctx.matchMedia=()=>({matches:false});r.run('dcBegin()');r.advance(3000);const deadline=r.ctx.S.deepcut.opts.dcRun.deadline;
 r.run('dcVisualDistance=1500;dcStartCrowdWave()');assert.equal(r.run('dcCrowdWave'),null);
 r.run('dcVisualDistance=3000;dcStartCrowdWave()');const start=r.run('dcCrowdWave.start');assert.equal(r.el('dcWave').disabled,true);
 r.advance(500);r.run('dcStartCrowdWave()');assert.equal(r.run('dcCrowdWave.start'),start);assert.equal(r.ctx.S.deepcut.opts.dcRun.deadline,deadline);assert.equal(r.ctx.S.deepcut.guesses.length,0);
 r.run('dcWaveState(dcCrowdWave.start+6200,2)');assert.equal(r.run('dcCrowdWave'),null);assert.equal(r.el('dcWave').disabled,false);
 r.run('dcStartCrowdWave();dcCleanup()');assert.equal(r.run('dcCrowdWave'),null);assert.equal(r.el('dcWave').hidden,true);
 r.ctx.matchMedia=()=>({matches:true});r.run('dcStartCrowdWave();dcWaveState(performance.now(),2)');assert.equal(r.run('dcCrowdWave'),null);assert.equal(r.el('dcWave').hidden,true);
});
test('new scoring editions keep browser/server parity and current-club answers follow 10/15 usage tiers',()=>{
 const current=JSON.parse(fs.readFileSync('deep_cut_scoring_cache.json','utf8')),currentIndex=M.index(current);
 for(const id of current.practice_runs){const run=currentIndex.runs.get(id),actions=run.prompts.map(key=>String(currentIndex.prompts.get(key).answers.find(a=>a[1]===100)[0]));assert.deepEqual(scoreGame('deepcut',{id},actions,{deepcut:current}),{won:true,tries:7,points:700});}
 for(const id of Object.values(current.current_prompts)){
  const prompt=currentIndex.prompts.get(id);
  for(const pid of prompt.currentRoster||[]){const p=currentIndex.players.get(pid);assert.equal(M.match(p.name+' '+p.born,id,current).score,prompt.lowToiRoster?.includes(pid)?15:10);}
 }
 const old=ix.prompts.get('team-CGY').points.get(8448208),reviewed=currentIndex.prompts.get(current.current_prompts['team-CGY']).points.get(8448208);
 assert.equal(old,10);assert.equal(reviewed,85);assert.equal(ix.prompts.get('team-CGY').points.get(8469500),10);
});
test('windows alternate watching, walking away and lowering blinds without rapid light cycling',()=>{
 for(const [seed,expected] of [[0,'closing-blinds'],[4,'leaving']]){
  const stages=new Set();let switches=0,previous;
  for(let time=0;time<=180000;time+=250){const state=SCENERY.windowState(seed,time);stages.add(state.stage);assert(state.blind>=0&&state.blind<=1);if(previous&&previous.lit!==state.lit)switches++;previous=state;}
  assert(stages.has('watching'));assert(stages.has(expected));assert(stages.has('off'));assert(switches<10);
  assert.deepEqual(SCENERY.windowState(seed,0,true),SCENERY.windowState(seed,90000,true));
 }
});
test('dog walkers stay behind the rink and reduced motion freezes their positions',()=>{
 for(const W of [160,188,480])for(const index of [0,1]){
  let previous=null;for(let time=0;time<180000;time+=1000){const actor=SCENERY.dogWalkerState(index,W,228,time);assert(actor.y<228);assert.equal(Math.sign(actor.dogX-actor.x),actor.direction);if(previous&&actor.x>=0&&actor.x<=W&&previous.x>=0&&previous.x<=W)assert(Math.abs(actor.x-previous.x)<=8.01);previous=actor;}
  assert.deepEqual(SCENERY.dogWalkerState(index,W,228,0,true),SCENERY.dogWalkerState(index,W,228,80000,true));
 }
});
test('ribbon messages track round, points, distance and milestones while reduced motion stops scrolling',()=>{
 const message=SCENERY.ribbonMessage({score:315,round:5,lastScore:85});for(const part of ['ROUND 5 OF 7','315 POINTS','3150 M SKATED','NEXT ARENA 450','DEEP CUT +85'])assert(message.includes(part));
 const perfect=SCENERY.ribbonMessage({score:700,round:7,over:true});assert(perfect.includes('SHIFT COMPLETE'));assert(perfect.includes('PERFECT 700'));assert(!perfect.includes('CHASE 700'));
 const capture=(time,still)=>{const out=[];SCENERY.ribbon((...args)=>out.push(args),{W:480,y:100,time,still,zone:3,progress:{score:450,round:6}});return out;};
 assert.deepEqual(capture(0,true),capture(5000,true));assert.notDeepEqual(capture(0,false),capture(5000,false));
});
console.log(`${checks} Deep Cut checks passed`);
