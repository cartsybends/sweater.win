// Behavioral checks for possession grips, pass readiness and 3v2 spacing.
// Run from the repository root: node tests/rush_behavior.cjs
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('build_sweater.py','utf8');global.$=()=>null;global.esc=String;
const edges=Object.values(JSON.parse(fs.readFileSync('edge_cache.json')).players);
const careers=JSON.parse(fs.readFileSync('career_cache.json'));
global.EDGE_BYID=new Map(edges.map(e=>[Number(e.id),e]));
global.BYID=new Map(edges.map((e,i)=>[Number(e.id),{id:Number(e.id),car:careers[e.id]?.car||[],shoots:i%2?'R':'L'}]));
global.EDGE_POOL=edges.map(e=>({...BYID.get(Number(e.id)),edge:e}));
for(const [start,end] of [['function hash(str)','// ---- dates:'],['const edgeValue =','function edgePairRandom'],['function edgeRushUniform','function edgeRushSet'],['const rushClamp=','function edgeRushRenderAgent'],['function edgeRushGoalieMarkup','async function edgeRushAnimate']])vm.runInThisContext(src.slice(src.indexOf(start),src.indexOf(end)));
const ids=edges.filter(e=>e.speed&&e.shot&&e.total>=20).slice(0,3).map(e=>Number(e.id));
const make=(x=.10)=>ids.map((id,i)=>edgeRushAgent(id,['Carrier','Support','Finisher'][i],x,[.52,.28,.72][i]));
let gripFrames=0;
for(const fps of [30,60,144])for(const hand of [-1,1]){
 const agents=make(),owner=agents[0];owner.hand=hand;
 const puck={mode:'carry',owner,x:owner.x,y:owner.y};
 for(let f=0;f<fps*3;f++){
  const now=10000+f/fps*1000;
  agents.forEach(a=>{a.vx=.27;a.vy=0;});
  edgeRushReadStickChecks(puck,[],now,1/fps,agents);
  agents.forEach(a=>{edgeRushSkaterStride(a,1/fps);a.x+=a.vx/fps;});
  assert.equal(owner.oneHandBlend,0,'Carrier retains both grips even at full speed with no pressure');
  if(f===fps/2)assert(agents[1].oneHandBlend>.95,'Off-puck neutral-zone sprint can release lower hand');
  for(const a of agents)if(a.x>=EDGE_RUSH_BLUE)assert.equal(a.oneHandBlend,0,'Both hands reattach before entering the offensive zone');
  gripFrames++;
 }
 const target=agents[1];assert(edgeRushPass(puck,target));
 for(let f=0;f<fps;f++){
  edgeRushReadStickChecks(puck,[],14000+f/fps*1000,1/fps,agents);
  agents.forEach(a=>edgeRushSkaterStride(a,1/fps));
  assert(agents.every(a=>a.oneHandBlend===0),'All in-zone players stay ready during passes');
  edgeRushUpdatePuck(puck,1/fps);
 }
 assert.equal(puck.owner,target);assert.equal(target.oneHandBlend,0);
}
// An unprepared receiver must regrip before a pass is sent.
{
 const agents=make(.60),puck={mode:'carry',owner:agents[0],x:.6,y:.5};agents[1].oneHandBlend=1;
 assert.equal(edgeRushPass(puck,agents[1]),false);assert.equal(puck.mode,'carry');
 for(let f=0;f<15;f++){edgeRushReadGrips(puck,agents,10000+f*16);agents.forEach(a=>edgeRushSkaterStride(a,1/60));}
 assert(edgeRushPass(puck,agents[1]));
}
// Mirror the entry and deep cycle. Always leave one distinct layer above the puck.
for(const x of [.57,.67,.82])for(const side of [-1,1]){
 const agents=make(x),owner=agents[0];owner.y=.5+side*.21;
 agents[1].y=.5-side*.18;agents[2].y=.5+side*.06;
 const defs=[{x:.68,y:.5+side*.10},{x:.73,y:.5-side*.15}],goalie={x:.89,y:.5};
 edgeRushSupportTargets(owner,agents,defs,goalie,10000);
 const mates=agents.slice(1),high=mates.filter(a=>a.intent==='high-outlet');
 assert.equal(high.length,1,'F3 stays high while the other teammate creates depth');
 assert(high[0].tx<owner.x,'High outlet is above the puck');
 assert(Math.abs(mates[0].tx-mates[1].tx)>=.095,'Support destinations occupy separate depth layers');
 assert(edgeRushDistance({x:mates[0].tx,y:mates[0].ty},{x:mates[1].tx,y:mates[1].ty})>=.17,'Support lanes remain separated');
}
// Proposed support routes must be independent of currently painted blade anchors.
{
 const targets=painted=>{
  const agents=make(.61),owner=agents[0];owner.y=.70;agents[1].y=.28;agents[2].y=.52;
  if(painted)agents.slice(1).forEach(a=>a.el={querySelector:()=>({getBoundingClientRect:()=>({left:650,top:340,width:0,height:0})})});
  edgeRushSupportTargets(owner,agents,[{x:.69,y:.62},{x:.72,y:.38}],{x:.88,y:.5},10000);
  return agents.slice(1).map(a=>({x:a.tx,y:a.ty,intent:a.intent}));
 };
 const normal=targets(false);global.$=id=>id==='erStage'?{clientWidth:720,clientHeight:405,getBoundingClientRect:()=>({left:0,top:0,width:720,height:405})}:null;
 assert.deepEqual(targets(true),normal,'Future destinations cannot read a stale on-screen stick position');global.$=()=>null;
}
// An uncontested close-range chance still earns an immediate shot.
{
 const agents=make(.80),owner=agents[0];owner.y=.45;agents[1].x=.60;agents[1].y=.25;agents[2].x=.65;agents[2].y=.75;
 assert.equal(edgeRushChooseAction(owner,agents.slice(1),[],10000,10000,{x:.88,y:.5}).action,'shoot');
}
// An elite shot does not imply enough time to load a slapshot.
{
 const a=make(.65)[0];a.brain.shot=.95;a.brain.scoring.signature.release='wrist';a.receiveAt=0;
 a.shotRead={pressure:.35,distance:.30};assert.notEqual(edgeRushReleaseType(a,10000),'slap');
 a.shotRead={pressure:1,distance:.30};assert.equal(edgeRushReleaseType(a,10000),'slap');
}
// Carry -> load -> release -> follow-through: no pose discontinuity for either hand.
const grip=(a)=>edgeRushSkaterGrip(a,10,5+4*16/49);
for(const hand of [-1,1])for(const type of ['snap','wrist','slap','one-timer','backhand']){
 const a={hand,x:.74,y:.52,rot:0,stickAngle:hand*14,stickX:-4,stickY:hand*3,wristRoll:.35,state:'shooting',releaseType:type,shotTargetRot:0,releaseGrip:{x:0,y:type==='backhand'?-hand*6:0}};
 a.windupStart={angle:a.stickAngle,x:a.stickX,y:a.stickY,roll:a.wristRoll};
 if(['slap','one-timer'].includes(type))a.shotPuckIce=edgeRushStick(a);
 const before=grip(a);edgeRushShootingPose(a,0);const start=grip(a);
 assert(Math.hypot(before.x-start.x,before.y-start.y)<1e-6,'The shooting pose starts at the existing carry grip');
 assert.equal(a.wristRoll,.35);assert.equal(a.shotWeight,0);
 edgeRushShootingPose(a,1);const release=grip(a),roll=a.wristRoll;
 edgeRushShootingPose(a,0,true);const follow=grip(a);
 assert(Math.hypot(release.x-follow.x,release.y-follow.y)<1e-6,'Top grip is continuous at release');
 assert(Math.abs(a.wristRoll-roll)<1e-9);assert(Math.abs(a.shotLoad)<1e-9,'Body does not suddenly dip after release');
}
console.log({gripFrames,mirroredSpacingScenarios:6,continuousShotTypes:5,shootingHands:2});
