// Full breakout -> entry -> attack regression, including live painted blade anchors.
// Run from repository root: node tests/rush_flow.cjs
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.env.RUSH_SOURCE||'build_sweater.py','utf8');global.$=()=>null;
const edges=Object.values(JSON.parse(fs.readFileSync('edge_cache.json')).players),careers=JSON.parse(fs.readFileSync('career_cache.json'));
const players=JSON.parse(fs.readFileSync('tests/fixtures/rush_players.json'));
global.EDGE_BYID=new Map(edges.map(e=>[Number(e.id),e]));global.BYID=new Map(players.map(p=>[p.id,{...p,car:careers[p.id]?.car||[]}]));global.EDGE_POOL=edges.filter(e=>BYID.has(Number(e.id))).map(e=>({...BYID.get(Number(e.id)),edge:e}));
vm.runInThisContext(source.slice(source.indexOf('function hash(str)'),source.indexOf('// ---- dates:')));
vm.runInThisContext(source.slice(source.indexOf('const edgeValue ='),source.indexOf('function edgePairRandom')));
vm.runInThisContext(source.slice(source.indexOf('const rushClamp='),source.indexOf('function edgeRushRenderAgent')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushGoalieMarkup'),source.indexOf('async function edgeRushAnimate')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushUniform'),source.indexOf('function edgeRushSet')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushRoleScores'),source.indexOf('function edgeRushZone')));
vm.runInThisContext(source.slice(source.indexOf('function seeded(seed)'),source.indexOf('function hlExtend')));
vm.runInThisContext(source.slice(source.indexOf('function shuffled(arr'),source.indexOf('// ---- Draft Day:')));
global.edgeRushEligible=()=>EDGE_POOL.filter(p=>p.pos!=='G'&&edgeValue(p.id,'speed')>0&&edgeValue(p.id,'shot')>0&&edgeValue(p.id,'miles')>0&&Number(p.edge?.total)>=20);
const units=[0,1,2,3].flatMap(seed=>edgeRushRandom(seeded(hash(`sweater-edgerush-2026-10-${8+seed}`))).rounds.flatMap(r=>r.lines.map(line=>edgeRushLine(line.ids).roles)));
const stage={clientWidth:720,clientHeight:405,clientLeft:0,clientTop:0,getBoundingClientRect:()=>({left:0,top:0,width:720,height:405})};
global.$=id=>id==='erStage'?stage:null;
function paint(a){
 const p=edgeRushStick({...a,el:null});
 a.el={querySelector:()=>({getBoundingClientRect:()=>({left:p.x*stage.clientWidth,top:p.y*stage.clientHeight,width:0,height:0})})};
}
function steerDef(d,dt){
 const dx=d.tx-d.x,dy=d.ty-d.y,len=Math.hypot(dx,dy),speed=Math.min(.164,len*2.4),dv=(speed>Math.hypot(d.vx,d.vy)?.30:.46)*dt;
 d.vx=rushMoveToward(d.vx,len?dx/len*speed:0,dv);d.vy=rushMoveToward(d.vy,len?dy/len*speed:0,dv);
 d.x=rushClamp(d.x+d.vx*dt,.48,.87);d.y=rushClamp(d.y+d.vy*dt,.16,.84);edgeRushSkaterStride(d,dt);
}
const stats={cases:0,passes:0,passingRushes:0,multiPassRushes:0,backdoors:0,rejectedPasses:0,maxAttackSeconds:0,byFps:{},roundSets:{}};
for(const width of [360,720])for(const fps of [15,30,60,144])for(let i=0;i<units.length;i++){
 stage.clientWidth=width;stage.clientHeight=width*405/720;
 const ids=units[i];
 const agents=ids.map((id,j)=>edgeRushAgent(id,['Carrier','Support','Finisher'][j],[.065,.045,.04][j],[.53,.31,.72][j]));
 const [carrier,support,finisher]=agents;
 const defs=[{x:.61,y:.38,vx:0,vy:0,tx:.61,ty:.38,mode:'gap'},{x:.63,y:.63,vx:0,vy:0,tx:.63,ty:.63,mode:'middle'}];
 const goalie={x:628/720,y:.5,brain:edgeRushGoalieBrain(),stance:.35};
 const puck={mode:'carry',owner:carrier,x:carrier.x,y:carrier.y};
 const plan={start:0,decisionAt:0,lastPassAt:0,passes:0,ownerId:carrier.id};
 edgeRushEntry(puck,agents,width);agents.forEach(paint);edgeRushUpdatePuck(puck,0,width,stage.clientHeight);
 let phase='breakout',shot=false,passes=0,clock=10000;
 const step=Math.min(source.includes('rushClock+=dt*1000')?.05:.033,1/fps);
 for(let f=0;f<Math.ceil(35/step);f++){
  const dt=step,now=source.includes('rushClock+=dt*1000')?(clock+=dt*1000):10000+f/fps*1000;
  if(phase!=='attack'){
   const tx=phase==='breakout'?.205:phase==='neutral'?.415:Math.max(.56,puck.entry.insideX+.055);
   carrier.tx=tx;carrier.ty=.52;support.tx=tx-.025;support.ty=.29;finisher.tx=tx-.02;finisher.ty=.72;
   if(phase==='breakout'&&carrier.x>.175){phase='neutral';edgeRushBurst(carrier,.25);}
   if(phase==='neutral'&&carrier.x>.345)phase='entry';
   if(phase==='entry'&&edgeRushEntryReady(puck,agents)){phase='attack';plan.start=now;}
  }else{
   if(now>=(plan.readAt||0)){
    plan.readAt=now+100;const r=edgeRushPlanAttack(puck,agents,defs,goalie,plan,now);
    if(r.action==='pass'){
     r.choice.a.receiveFromY=puck.owner.y;
     if(edgeRushPass(puck,r.choice.a,.32-.07*puck.owner.brain.playmaking)){
      passes++;stats.passes++;if(r.play==='backdoor')stats.backdoors++;
     }else stats.rejectedPasses++;
    }else if(r.action==='shoot'){
     stats.cases++;stats.passingRushes+=passes>0;stats.multiPassRushes+=passes>1;
     const group=stats.byFps[fps]||(stats.byFps[fps]={cases:0,passingRushes:0,multiPassRushes:0});group.cases++;group.passingRushes+=passes>0;group.multiPassRushes+=passes>1;
     const roundKey=`${width}/${fps}/${Math.floor(i/15)}/${i%3}`;const roundSet=stats.roundSets[roundKey]||(stats.roundSets[roundKey]={rushes:0,passingRushes:0,passes:0});roundSet.rushes++;roundSet.passingRushes+=passes>0;roundSet.passes+=passes;
     stats.maxAttackSeconds=Math.max(stats.maxAttackSeconds,(now-plan.start)/1000);shot=true;break;
    }
   }
   agents.forEach(a=>edgeRushUpdateMove(a,now));
  }
  edgeRushEntry(puck,agents,width);edgeRushReadStickChecks(puck,defs,now,dt,agents);
  agents.forEach(a=>edgeRushSteer(a,dt,[...defs,...agents.filter(b=>b!==a)]));edgeRushEntry(puck,agents,width);agents.forEach(paint);
  edgeRushReadDefenders(defs,puck,agents,now);defs.forEach(d=>steerDef(d,dt));edgeRushSeparate(agents,defs);
  edgeRushEntry(puck,agents,width);agents.forEach(paint);
  const previousOwner=puck.owner;edgeRushUpdatePuck(puck,dt,width,stage.clientHeight);
  if(puck.mode==='carry'&&puck.owner!==previousOwner){puck.owner.receiveAt=now;plan.ownerId=puck.owner.id;plan.lastPassAt=now;}
  edgeRushUpdateGoalie(goalie,puck,dt);
 }
 assert(shot,`Full rush stalled at ${width}px/${fps}fps, unit ${ids}`);
}
const roundSets=Object.values(stats.roundSets);stats.minPassingRounds=Math.min(...roundSets.map(s=>s.passingRushes));stats.minPassesPerFiveRounds=Math.min(...roundSets.map(s=>s.passes));delete stats.roundSets;console.log(stats);
assert(roundSets.every(s=>s.rushes===5&&s.passingRushes>=2),'Every tested five-round set should develop multiple passing plays');
assert.equal(stats.rejectedPasses,0,'The planner must select receivers that can accept the pass');
assert(stats.passingRushes>=stats.cases*.80,'Ordinary contained 3v2s should regularly move the puck');
assert(stats.multiPassRushes>=stats.cases*.25,'Rushes must retain give-and-go and second-pass opportunities');
