// Verify full shot setup, load, contact and follow-through for both hands and wings.
// Run from repository root: node tests/rush_shots.cjs
const fs=require('fs'),vm=require('vm'),assert=require('assert'),source=fs.readFileSync('build_sweater.py','utf8');global.$=()=>null;global.esc=s=>String(s);global.BYID=new Map([[1,{id:1,shoots:'L',number:29}],[2,{id:2,shoots:'R',number:97}]]);
vm.runInThisContext(source.slice(source.indexOf('function edgeRushStickMarkup'),source.indexOf('function edgeRushActor')));vm.runInThisContext(source.slice(source.indexOf('function edgeRushUniform'),source.indexOf('function edgeRushSet')));vm.runInThisContext(source.slice(source.indexOf('const rushClamp='),source.indexOf('function edgeRushRenderAgent')));vm.runInThisContext(source.slice(source.indexOf('function edgeRushDefenderStick'),source.indexOf('function edgeRushReadStickChecks')));
class Node{constructor(){this.attrs={};this.children={};this.style={};}querySelector(k){return this.children[k]||(this.children[k]=new Node());}setAttribute(k,v){this.attrs[k]=String(v);}}
const distance=(a,b)=>Math.hypot(a.d-b.d,a.l-b.l,a.z-b.z),poses=[];let checks=0,maxReach=0;
function render(a,def=false,now=0,name){delete a.skaterRig;delete a.stickEl;a.el=new Node();edgeRushRenderSkater(a,def,now);for(const key of ['leg.left','leg.right','arm.top','arm.bottom']){const j=a.skaterJoints[key],bone=key.startsWith('leg')?20:17;maxReach=Math.max(maxReach,j.reach);assert(Math.abs(distance(j.origin,j.middle)-bone)<.002,`${key} upper ${name}`);assert(Math.abs(distance(j.middle,j.end)-bone)<.002,`${key} lower ${name}: ${j.reach}, ${JSON.stringify({hand:a.hand,angle:a.stickAngle,phase:a.skatePhase,speed:a.vx,def})}`);}for(const key of ['top','bottom']){const p=a.skaterJoints['grip.'+key];assert(Math.hypot(p.x-p.shaftX,p.y-p.shaftY)<.0001,'Hand must grip actual rendered shaft');}checks++;if(name)poses.push({name,def,stickMatrix:edgeRushStickMatrix(a),state:Object.fromEntries(Object.entries(a).filter(([k])=>!['el','skaterRig','skaterJoints'].includes(k))),stickMarkup:edgeRushStickMarkup(),markup:edgeRushSkaterMarkup(def?'D1':a.hand<0?'29':'97',def),attrs:Object.fromEntries(Object.entries(a.el.children).map(([k,n])=>[k,n.attrs]))});}
vm.runInThisContext(source.slice(source.indexOf('function edgeRushGoalieMarkup'),source.indexOf('async function edgeRushAnimate')));
let cases=0;
for(const hand of [-1,1])for(const wing of [-1,1])for(const type of ['slap','wrist','snap'])for(const angle of [-24,0,24])for(const fps of [15,30,60,144]){
 const a={id:hand<0?1:2,hand,x:type==='snap'?.75:.60,y:.5+wing*.23,rot:wing*-20,vx:0,vy:0,stickAngle:angle,stickX:-3,stickY:wing*4,wristRoll:0,state:'route',skatePhase:0,oneHandBlend:0,brain:{handling:.8,shot:type==='slap'?.95:.45,release:type==='snap'?.20:.29,scoring:{signature:{release:'wrist'},pct:[.22,.15,.08]}}};
 const goalie={x:628/720,y:.5,brain:edgeRushGoalieBrain()};
 edgeRushPrepareShooting(a,10000,[],goalie);
 assert.equal(a.releaseType,type,'Natural shot choice');assert.equal(a.shotOffWing,wing*hand<0);assert(a.shotSetupDuration>0);
 const label=`${hand<0?'LH':'RH'} ${wing<0?'upper':'lower'} ${type}`,capture=angle===0&&fps===60;
 edgeRushShotSetupPose(a,0);assert.equal(a.stickAngle,angle,'Setup begins from carried stick');
 const steps=Math.ceil(a.shotSetupDuration/Math.min(.05,1/fps));
 for(let i=0;i<=steps;i++){edgeRushShotSetupPose(a,i/steps);render(a,false,0);}
 assert.equal(a.rot,a.shotTargetRot,'Body faces actual net target before load');assert.equal(a.stickAngle,hand*8,'Forehand shooting box mirrors shooting hand');
 edgeRushBeginWindup(a);render(a,false,0,capture?label+' setup':null);
 const topStart={...a.skaterJoints['grip.top']};edgeRushShootingPose(a,0);render(a);assert(Math.hypot(topStart.x-a.skaterJoints['grip.top'].x,topStart.y-a.skaterJoints['grip.top'].y)<.001,'Setup-to-load hand continuity');
 let maxLoad=0,maxFlex=0,maxPitch=0;const windupSteps=Math.ceil(a.windupDuration/Math.min(.05,1/fps));
 for(let i=0;i<=windupSteps;i++){
  const t=i/windupSteps;edgeRushShootingPose(a,t);render(a);maxLoad=Math.max(maxLoad,a.shotLoad);maxFlex=Math.max(maxFlex,a.shotFlex);maxPitch=Math.max(maxPitch,a.stickPitch);
 }
 assert(maxLoad>(type==='slap'?.9:type==='wrist'?.7:.4),'Distinct body loading before release');assert(maxFlex>.6,'Lower shaft loads below attached bottom hand');
 if(type==='slap'){assert(maxPitch>55,'Slap backswing raises the stick');const blade=edgeRushStick(a);assert(edgeRushDistance(blade,a.shotPuckIce)<.00001,'Slap returns to planted puck');}
 for(const t of [.30,.48,1]){edgeRushShootingPose(a,t);render(a,false,0,capture?label+(t===1?' contact':t===.30?' load':' drive'):null);}
 const release={...a.skaterJoints['grip.top']};edgeRushShootingPose(a,0,true);render(a);assert(Math.hypot(release.x-a.skaterJoints['grip.top'].x,release.y-a.skaterJoints['grip.top'].y)<.001,'Release-to-follow hand continuity');
 for(let i=0;i<=Math.ceil(.48/Math.min(.05,1/fps));i++){edgeRushShootingPose(a,i/Math.ceil(.48/Math.min(.05,1/fps)),true);render(a);}
 edgeRushShootingPose(a,.35,true);render(a,false,0,capture?label+' follow':null);cases++;
}
if(process.env.RUSH_SHOT_PREVIEW)fs.writeFileSync(process.env.RUSH_SHOT_PREVIEW,JSON.stringify({poses}));
console.log({cases,checks,maxReach});
