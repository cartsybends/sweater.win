// Run from the repository root: node tests/rush_scenarios.cjs
// Simulate 480 varied 3v2 attacks and check open/blocked backdoor feeds.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('build_sweater.py','utf8');global.$=()=>null;
const edges=Object.values(JSON.parse(fs.readFileSync('edge_cache.json')).players),careers=JSON.parse(fs.readFileSync('career_cache.json'));
global.EDGE_BYID=new Map(edges.map(e=>[Number(e.id),e]));global.BYID=new Map(edges.map((e,i)=>[Number(e.id),{id:Number(e.id),car:careers[e.id]?.car||[],shoots:i%2?'R':'L'}]));global.EDGE_POOL=edges.map(e=>({...BYID.get(Number(e.id)),edge:e}));
vm.runInThisContext(source.slice(source.indexOf('function hash(str)'),source.indexOf('// ---- dates:')));
vm.runInThisContext(source.slice(source.indexOf('const edgeValue ='),source.indexOf('function edgePairRandom')));
vm.runInThisContext(source.slice(source.indexOf('const rushClamp='),source.indexOf('function edgeRushRenderAgent')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushGoalieMarkup'),source.indexOf('async function edgeRushAnimate')));
vm.runInThisContext(source.slice(source.indexOf('function edgeRushUniform'),source.indexOf('function edgeRushSet')));
const eligible=edges.filter(e=>e.speed&&e.shot&&e.total>=20);
function def(x,y){return{x,y,tx:x,ty:y,vx:0,vy:0,mode:'gap'};}
function steerDef(d,dt){const dx=d.tx-d.x,dy=d.ty-d.y,len=Math.hypot(dx,dy),max=Math.min(.164,len*2.4),dv=.36*dt;d.vx=rushMoveToward(d.vx,len?dx/len*max:0,dv);d.vy=rushMoveToward(d.vy,len?dy/len*max:0,dv);d.x=rushClamp(d.x+d.vx*dt,.48,.87);d.y=rushClamp(d.y+d.vy*dt,.16,.84);edgeRushSkaterStride(d,dt);}
let stats={cases:0,passes:0,backdoors:0,dekes:0,taps:0,maxSeconds:0,minQuality:1,soloAttempts:0,soloPairBeaten:0};
for(const fps of [30,60,144])for(let i=0;i<160;i++){
 const ids=[eligible[i*3%eligible.length].id,eligible[(i*3+117)%eligible.length].id,eligible[(i*3+271)%eligible.length].id];
 const agents=ids.map((id,j)=>edgeRushAgent(id,['Carrier','Support','Finisher'][j],.54-j*.02,[.52,.29,.72][j]));const defs=[def(.64,.38),def(.67,.63)],g={x:640/720,y:.5,brain:edgeRushGoalieBrain(),stance:.35};
 const puck={mode:'carry',owner:agents[0],x:.57,y:.52,entry:{entered:true,insideX:.45}},plan={start:10000,lastPassAt:0,decisionAt:0,passes:0,ownerId:ids[0]};let shot=false,soloAttempt=false;
 for(let f=0;f<fps*22;f++){
  const now=10000+f/fps*1000;soloAttempt ||= agents.some(a=>a.soloRush);
  if(now>=(plan.readAt||0)){
   plan.readAt=now+100;const r=edgeRushPlanAttack(puck,agents,defs,g,plan,now);
   if(r.action==='pass'){r.choice.a.receiveFromY=puck.owner.y;assert(edgeRushPass(puck,r.choice.a));stats.passes++;if(r.play==='backdoor')stats.backdoors++;}
   if(r.action==='deke')stats.dekes++;
   if(r.action==='shoot'){stats.cases++;stats.maxSeconds=Math.max(stats.maxSeconds,(now-plan.start)/1000);stats.minQuality=Math.min(stats.minQuality,r.quality.value);if(edgeRushReleaseType(r.owner,now)==='tap-in')stats.taps++;shot=true;break;}
  }
  edgeRushReadStickChecks(puck,defs,now,1/fps,agents);agents.forEach(a=>{edgeRushUpdateMove(a,now);edgeRushSteer(a,1/fps,[...defs,...agents.filter(b=>b!==a)]);});edgeRushReadDefenders(defs,puck,agents,now);defs.forEach(d=>steerDef(d,1/fps));edgeRushSeparate(agents,defs);edgeRushUpdatePuck(puck,1/fps);edgeRushUpdateGoalie(g,puck,1/fps);
  assert(Math.hypot(g.x*720-660,g.y*405-202.5)<41);
 }
 if(soloAttempt)stats.soloAttempts++;if(agents.some(a=>a.soloBeatPair))stats.soloPairBeaten++;if(!shot)console.log(JSON.stringify({fps,i,ids,plan,agents:agents.map(a=>({id:a.id,x:a.x,y:a.y,tx:a.tx,ty:a.ty,intent:a.intent,quality:edgeRushShotQuality(a,defs,g)})),defs,puck:{mode:puck.mode}}));assert(shot,`Attack stalled ${ids}`);
}
// Isolated open backdoor and blocked-lane decisions, mirrored and both hands.
for(const side of [-1,1])for(const hand of [-1,1]){
 const from=edgeRushAgent(eligible[0].id,'Carrier',.77,.5+side*.22),to=edgeRushAgent(eligible[1].id,'Finisher',.84,.5-side*.055-.019*hand);to.hand=hand;const neutral=edgeRushStick(to);to.y+=.5-side*.055-neutral.y;
 const defs=[def(.72,.5+side*.18),def(.73,.5+side*.10)],g={x:.9,y:.5+side*.07};
 assert(edgeRushBackdoor(from,to,defs,g));assert.equal(edgeRushChoosePass(from,[to],defs,g).play,'backdoor');
 const start=edgeRushStick(from),end=edgeRushStick(to),blocked=[def((start.x+end.x)/2,(start.y+end.y)/2),defs[1]];assert.equal(edgeRushBackdoor(from,to,blocked,g),null);
 to.backdoorUntil=11000;to.receiveAt=10000;assert.equal(edgeRushReleaseType(to,10100),'tap-in');
}
console.log(stats);
