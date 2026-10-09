// Full breakout -> entry -> attack regression, including live painted blade anchors.
// Run from repository root: node tests/rush_flow.cjs
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.env.RUSH_SOURCE||'build_sweater.py','utf8');global.$=()=>null;
const edges=Object.values(JSON.parse(fs.readFileSync('edge_cache.json')).players),careers=JSON.parse(fs.readFileSync('career_cache.json'));
global.EDGE_BYID=new Map(edges.map(e=>[Number(e.id),e]));global.BYID=new Map(edges.map((e,i)=>[Number(e.id),{id:Number(e.id),car:careers[e.id]?.car||[],shoots:i%2?'R':'L'}]));global.EDGE_POOL=edges.map(e=>({...BYID.get(Number(e.id)),edge:e}));
vm.runInThisContext(source.slice(source.indexOf('function hash(str)'),source.indexOf('// ---- dates:')));
vm.runInThisContext(source.slice(source.indexOf('const edgeValue ='),source.indexOf('function edgePairRandom')));
vm.runInThisContext(source.slice(source.indexOf('const rushClamp='),source.indexOf('function edgeRushRenderAgent')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushGoalieMarkup'),source.indexOf('async function edgeRushAnimate')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushUniform'),source.indexOf('function edgeRushSet')));
const eligible=edges.filter(e=>e.speed&&e.shot&&e.total>=20);
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
const stats={cases:0,passes:0,passingRushes:0,multiPassRushes:0,backdoors:0,rejectedPasses:0,maxAttackSeconds:0};
for(const width of [360,720])for(const fps of [30,60,144])for(let i=0;i<20;i++){
 stage.clientWidth=width;stage.clientHeight=width*405/720;
 const ids=[eligible[i*3%eligible.length].id,eligible[(i*3+117)%eligible.length].id,eligible[(i*3+271)%eligible.length].id];
 const agents=ids.map((id,j)=>edgeRushAgent(id,['Carrier','Support','Finisher'][j],[.065,.045,.04][j],[.53,.31,.72][j]));
 const [carrier,support,finisher]=agents;
 const defs=[{x:.61,y:.38,vx:0,vy:0,tx:.61,ty:.38,mode:'gap'},{x:.63,y:.63,vx:0,vy:0,tx:.63,ty:.63,mode:'middle'}];
 const goalie={x:628/720,y:.5,brain:edgeRushGoalieBrain(),stance:.35};
 const puck={mode:'carry',owner:carrier,x:carrier.x,y:carrier.y};
 const plan={start:0,decisionAt:0,lastPassAt:0,passes:0,ownerId:carrier.id};
 edgeRushEntry(puck,agents,width);agents.forEach(paint);edgeRushUpdatePuck(puck,0,width,stage.clientHeight);
 let phase='breakout',shot=false,passes=0;
 for(let f=0;f<fps*35;f++){
  const dt=Math.min(.033,1/fps),now=10000+f/fps*1000;
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
console.log(stats);
assert.equal(stats.rejectedPasses,0,'The planner must select receivers that can accept the pass');
assert(stats.passingRushes>=stats.cases*.70,'Ordinary contained 3v2s should regularly move the puck');
assert(stats.multiPassRushes>=stats.cases*.20,'Rushes must retain give-and-go and second-pass opportunities');
