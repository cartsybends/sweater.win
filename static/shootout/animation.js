// The goal is a projected U-shaped frame; the keeper uses connected, forward-facing joints.
const NET_ZONES=[[179,150],[461,150],[179,320],[461,320],[320,331]];
const SH_GOAL={left:134,right:506,top:110,bottom:358,postRadius:6,horizon:-32,scale:31/6,depth:40,roofDepth:22};
const SH_RIG={ground:390,padHalfWidth:35,padLength:163,hip:[0,253],shoulderL:[-68,173],shoulderR:[68,173],stickLength:164};
const shClamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const shLerp=(a,b,u)=>a+(b-a)*u;
const shEase=u=>{u=shClamp(u);return u*u*u*(u*(u*6-15)+10);};
const shPoint=(a,b,u)=>[shLerp(a[0],b[0],u),shLerp(a[1],b[1],u)];
const shRotate=(p,degrees,c=[0,0])=>{const a=degrees*Math.PI/180,x=p[0]-c[0],y=p[1]-c[1];return[c[0]+x*Math.cos(a)-y*Math.sin(a),c[1]+x*Math.sin(a)+y*Math.cos(a)];};
const shNumber=x=>Number(x.toFixed(3));
const shProject=(x,y,z)=>{const s=1/(1+z*.007);return[320+x*SH_GOAL.scale*s,SH_GOAL.horizon+(SH_GOAL.bottom-y*SH_GOAL.scale-SH_GOAL.horizon)*s];};
function shootNetPoint(u,v){const theta=(u-.5)*Math.PI;return shProject(36*Math.sin(theta),48*v,(SH_GOAL.depth+(SH_GOAL.roofDepth-SH_GOAL.depth)*v)*Math.cos(theta));}
function shootNetUV(p){return[.5+Math.asin(shClamp((p[0]-320)/186,-1,1))/Math.PI,shClamp((358-p[1])/248)];}
const shRear=p=>shootNetPoint(...shootNetUV(p));
const shPadY=a=>SH_RIG.ground-SH_RIG.padHalfWidth*Math.abs(Math.sin(a*Math.PI/180))-SH_RIG.padLength*Math.cos(a*Math.PI/180);
let shootSceneRun=null,shootMeshWarped=true;

function shootPose(read,u=0,impact=0){
  const low=read>=2,side=read===0||read===2?-1:read===1||read===3?1:0;
  const dx=side*(low?57:48),drop=(low?74:2)*u,lean=side*(low?3:4)*u;
  const contact=shPoint([320,414],NET_ZONES[read],.9),push=low?0:Math.sin(u*Math.PI);
  const padL=shLerp(31+(side>0?5:-2)*push,84,low?u:0),padR=shLerp(-31+(side<0?-5:2)*push,-84,low?u:0);
  const shoulders=[shRotate(SH_RIG.shoulderL,lean,SH_RIG.hip),shRotate(SH_RIG.shoulderR,lean,SH_RIG.hip)].map(p=>[p[0],p[1]+drop]);
  const elbowL=[shoulders[0][0]-shLerp(37,read===0?40:low?30:37,u),shoulders[0][1]+shLerp(58,read===0?36:low?57:58,u)];
  const elbowR=[shoulders[1][0]+shLerp(37,read===1?43:low?45:37,u),shoulders[1][1]+shLerp(69,read===1?48:69,u)];
  const blocker=shPoint([-108,268],read===0?[contact[0]-320-dx,contact[1]]:low?[-91,316]:[-106,270],u);
  const glove=shPoint([120,224],read===1?[contact[0]-320-dx,contact[1]]:low?[96,298]:[122,225],u);
  blocker[1]+=impact*1.5;glove[1]+=impact*1.5;
  return{x:dx*u,drop,lean,shoulderL:shoulders[0],shoulderR:shoulders[1],elbowL,elbowR,blocker,glove,
    kneeL:[shLerp(-45+(side>0?-5:2)*push,read===4?-8:-20,low?u:0),shPadY(padL)],
    kneeR:[shLerp(45+(side<0?5:-2)*push,read===4?8:20,low?u:0),shPadY(padR)],padL,padR,
    head:side*3*u,blockerAngle:shLerp(16,read===0?-8:low?7:16,u),gloveAngle:shLerp(12,read===1?-10:low?25:12,u),gloveClose:read===1?impact:0,absorb:impact};
}
function shootPlan(zone,keep,seed=0){
  if(!Number.isInteger(zone)||zone<0||zone>4)throw new Error('Invalid shootout target');
  const save=keep.includes(zone),read=save?zone:zone===0||zone===2?1:zone===1||zone===3?0:Math.abs(seed)%2,post=!save&&zone<4&&Math.abs(seed)%5===0;
  const inside=SH_GOAL.postRadius+14.5*.53;
  const point=post?[zone%2?SH_GOAL.right-inside:SH_GOAL.left+inside,NET_ZONES[zone][1]]:NET_ZONES[zone];
  const contact=shPoint([320,414],NET_ZONES[zone],.9),uv=shootNetUV(point);
  if(post){uv[0]+=zone%2?-.035:.035;uv[1]=Math.max(0,uv[1]-.015);}
  const back=shootNetPoint(...uv),rest=shootNetPoint(uv[0],0);rest[1]-=3;
  return{zone,save,read,post,point,contact,uv,back,rest,release:.16,contactAt:.592,planeAt:.64,netAt:post?.9:.81,duration:1.5};
}
function shootFrame(plan,time){
  const t=shClamp(time,0,plan.duration),flight=shClamp((t-plan.release)/(plan.planeAt-plan.release));
  const action=shEase((t-.12)/.43),after=Math.max(0,t-plan.contactAt);
  const absorb=plan.save?Math.sin(shClamp(after/.18)*Math.PI)*Math.exp(-after*4):0;
  const pose=shootPose(plan.read,action,absorb);
  // A missed read opens the actual puck lane: wrong side for corners, upright for five-hole.
  if(!plan.save&&plan.zone===4)pose.x=0;
  pose.gloveClose=plan.save&&plan.zone===1?shEase(after/.085):0;
  let puck={x:320,y:414,scale:1,opacity:1,layer:'front',shadow:1,shadowY:414,rotation:0};
  if(t>=plan.release){const p=shPoint([320,414],plan.point,flight);puck={...puck,x:p[0],y:p[1],scale:shLerp(1,.53,flight),shadow:Math.max(.08,1-flight*.85),shadowY:shLerp(414,358,flight),rotation:flight*4};}
  if(plan.save&&t>=plan.contactAt){
    const p=plan.contact,u=shClamp(after/.51),side=plan.zone%2===0?-1:1;
    if(plan.zone===1){puck={...puck,x:p[0],y:p[1]+absorb*1.5,opacity:Math.max(0,1-after/.055),shadow:0};}
    else{const end=plan.zone===4?[338,406]:[shClamp(p[0]+side*(plan.zone<2?112:99),52,588),405];const q=shPoint(p,end,1-(1-u)*(1-u));puck={...puck,x:q[0],y:q[1]-Math.sin(u*Math.PI)*(plan.zone<2?24:8),scale:shLerp(.577,.78,u),shadow:.22,shadowY:shLerp(363.6,405,u),rotation:3.6*(1-u)+Math.sin(u*Math.PI)*(plan.zone<2?65:12)};}
  }
  if(!plan.save&&t>=plan.planeAt){
    const u=shEase((t-plan.planeAt)/(plan.netAt-plan.planeAt)),q=shPoint(plan.point,plan.back,u);
    puck={...puck,x:q[0],y:q[1],scale:shLerp(.53,.41,u),layer:t>plan.planeAt+.015?'back':'front',shadow:.13,shadowY:shLerp(358,plan.rest[1]+3,u),rotation:4+(plan.post?Math.sin(u*Math.PI)*25:0)};
    if(t>=plan.netAt){const settle=shEase((t-plan.netAt)/.55),q2=shPoint(plan.back,plan.rest,settle);puck={...puck,x:q2[0],y:q2[1]-Math.sin(settle*Math.PI)*5,scale:.41,layer:'back',shadow:.12,rotation:4*(1-settle)+Math.sin(settle*Math.PI)*12};}
  }
  return{t,pose,puck,scored:!plan.save&&t>=plan.planeAt+(plan.post?.08:.025),saved:plan.save&&t>=plan.contactAt,
    netImpact:!plan.save&&t>=plan.netAt?{point:plan.back,uv:plan.uv,time:t-plan.netAt}:null,
    post:plan.post&&t>=plan.planeAt?{side:plan.zone%2,time:t-plan.planeAt}:null,
    snow:Math.sin(shClamp((t-.22)/.44)*Math.PI)*action};
}
const SH_MESH_COLS=40,SH_MESH_ROWS=20;
function shootMeshUV(axis,index){
  const sign=axis==='h'?1:-1;
  const start=Math.max(0,sign===1?-index/SH_MESH_ROWS:(index-SH_MESH_COLS)/SH_MESH_ROWS);
  const end=Math.min(1,sign===1?(SH_MESH_COLS-index)/SH_MESH_ROWS:index/SH_MESH_ROWS);
  return Array.from({length:10},(_,i)=>{const v=shLerp(start,end,i/9);return[(index+sign*SH_MESH_ROWS*v)/SH_MESH_COLS,v];});
}
const SH_MESH_LINES=['h','v'].flatMap(axis=>Array.from({length:SH_MESH_COLS+SH_MESH_ROWS+1},(_,i)=>{
  const index=axis==='h'?i-SH_MESH_ROWS:i;
  return{axis,index,id:'shMesh'+(axis==='h'?'H':'V')+i,points:shootMeshUV(axis,index).map(uv=>({uv,point:shootNetPoint(...uv),tie:Math.sin(uv[0]*Math.PI)*Math.sin(uv[1]*Math.PI)}))};
}));
function shootMeshPoint(point,impact,uv=shootNetUV(point),tie=Math.sin(uv[0]*Math.PI)*Math.sin(uv[1]*Math.PI)){
  if(!impact)return point;
  const [x,y]=point,[cx,cy]=impact.point,t=impact.time,envelope=7*Math.sin(t*23)*Math.exp(-t*6.7),r=48+t*65;
  const weight=Math.exp(-((x-cx)**2+(y-cy)**2)/(2*r*r))*tie;
  return[x+(320-cx)/145*envelope*weight,y-envelope*.75*weight];
}
function shootMeshPath(axis,index,impact){
  const line=SH_MESH_LINES.find(p=>p.axis===axis&&p.index===index);
  return line.points.map(({point,uv,tie},i)=>(i?'L':'M')+shootMeshPoint(point,impact,uv,tie).map(shNumber).join(' ')).join(' ');
}
function shootStick(p){
  const grip=[p.blocker[0]+13*Math.cos(p.blockerAngle*Math.PI/180),p.blocker[1]+13*Math.sin(p.blockerAngle*Math.PI/180)];
  const dx=5-grip[0],dy=SH_RIG.ground-grip[1],len=Math.hypot(dx,dy),s=SH_RIG.stickLength/len;
  let end=[grip[0]+dx*s,grip[1]+dy*s];
  if(end[1]>SH_RIG.ground){end=[grip[0]+Math.sqrt(Math.max(0,SH_RIG.stickLength**2-dy**2)),SH_RIG.ground];}
  return{grip,end,angle:Math.atan2(end[1]-grip[1],end[0]-grip[0])*180/Math.PI-90};
}
function shootPostPath(side,w=0,shine=false){
  const x=side?506:134,s=side?-1:1,offset=shine?-s*1.8:0;
  return`M${shNumber(x+offset)} 358 C${shNumber(x+offset)} 277 ${shNumber(x+w+offset)} 193 ${shNumber(x+w*.6+offset)} 122 Q${shNumber(x+w*.6+offset)} ${shine?112:110} ${shNumber(x+s*8+w*.3+offset)} ${shine?112:110}`;
}
function shootPaint(frame){
  const a=(id,key,value)=>$(id).setAttribute(key,value),p=frame.pose;
  a('shGoalie','transform',`translate(${shNumber(320+p.x)} 0)`);
  a('shBody','transform',`translate(0 ${shNumber(p.drop)}) rotate(${shNumber(p.lean)} 0 253)`);
  a('shHead','transform',`rotate(${shNumber(p.head)} 0 112)`);
  a('shPants','transform',`translate(0 ${shNumber(p.drop)})`);
  for(const side of ['L','R']){
    const k=p['knee'+side],s=p['shoulder'+side],e=p['elbow'+side],h=side==='L'?p.blocker:p.glove;
    a('shPad'+side,'transform',`translate(${k.map(shNumber).join(' ')}) rotate(${shNumber(p['pad'+side])})`);
    a('shArm'+side,'d',`M${s.map(shNumber).join(' ')} L${e.map(shNumber).join(' ')}`);
    a('shForearm'+side,'d',`M${e.map(shNumber).join(' ')} L${h.map(shNumber).join(' ')}`);
    a('shArm'+side+'Stripe','d',`M${shPoint(e,h,.3).map(shNumber).join(' ')} L${shPoint(e,h,.57).map(shNumber).join(' ')}`);
    a('shElbow'+side,'transform',`translate(${e.map(shNumber).join(' ')}) rotate(${shNumber(Math.atan2(h[1]-e[1],h[0]-e[0])*180/Math.PI)})`);
  }
  a('shBlocker','transform',`translate(${p.blocker.map(shNumber).join(' ')}) rotate(${shNumber(p.blockerAngle-p.absorb*3)})`);
  a('shGlove','transform',`translate(${p.glove.map(shNumber).join(' ')}) rotate(${shNumber(p.gloveAngle+p.absorb*3)})`);
  a('shGloveThumb','transform',`rotate(${shNumber(p.gloveClose*16)} -17 15)`);
  a('shGlovePocket','transform',`scale(${shNumber(1-p.gloveClose*.25)} 1)`);
  const stick=shootStick(p);a('shStick','transform',`translate(${stick.grip.map(shNumber).join(' ')}) rotate(${shNumber(stick.angle)})`);
  a('shStickBlade','transform',`translate(${stick.end.map(shNumber).join(' ')}) rotate(${shNumber(stick.end[1]<389?-8:0)})`);
  a('shKeeperShadow','cx',320+p.x);a('shKeeperShadow','rx',p.drop>20?174:148);a('shKeeperShadow','cy',389);
  for(const layer of ['Front','Back']){const visible=frame.puck.layer.toLowerCase()===layer.toLowerCase();
    a('shPuck'+layer,'transform',`translate(${shNumber(frame.puck.x)} ${shNumber(frame.puck.y)}) scale(${shNumber(frame.puck.scale)}) rotate(${shNumber(frame.puck.rotation)})`);a('shPuck'+layer,'opacity',visible?frame.puck.opacity:0);
    a('shPuckShadow'+layer,'cx',frame.puck.x);a('shPuckShadow'+layer,'cy',frame.puck.shadowY);a('shPuckShadow'+layer,'rx',8*frame.puck.scale);a('shPuckShadow'+layer,'opacity',visible?frame.puck.shadow*frame.puck.opacity:0);
  }
  if(frame.netImpact||shootMeshWarped){for(const line of SH_MESH_LINES)a(line.id,'d',shootMeshPath(line.axis,line.index,frame.netImpact));shootMeshWarped=!!frame.netImpact;}
  const wobble=frame.post?Math.sin(frame.post.time*65)*Math.exp(-frame.post.time*13)*.8:0;
  const wl=frame.post?.side===0?wobble:0,wr=frame.post?.side===1?wobble:0;
  for(const [side,w]of [[0,wl],[1,wr]]){a(side?'shPostRTube':'shPostLTube','d',shootPostPath(side,w));a(side?'shPostRShine':'shPostLShine','d',shootPostPath(side,w,true));}
  a('shCrossbarTube','d',`M${shNumber(142+wl*.3)} 110 Q320 ${shNumber(110+wobble*.12)} ${shNumber(498+wr*.3)} 110`);
  a('shCrossbarShine','d',`M${shNumber(142+wl*.3)} 108.2 Q320 ${shNumber(108.2+wobble*.12)} ${shNumber(498+wr*.3)} 108.2`);
  a('shLampGlow','opacity',frame.scored?.22:0);a('shLamp','fill',frame.scored?'#ff5351':'#a8b7bf');
  a('shSnow','opacity',frame.snow*.62);a('shSnow','transform',`translate(${shNumber(320+p.x)} 388) scale(${shNumber(.6+frame.snow)} 1)`);
  $('shNet').classList.toggle('scored',frame.scored);$('shNet').classList.toggle('saved',frame.saved);
}
function shootSceneRest(aim=false){
  shootCancelAnimation();const frame={pose:shootPose(4),puck:{x:320,y:414,scale:1,opacity:aim?1:0,layer:'front',shadow:aim?.24:0,shadowY:414,rotation:0},scored:false,saved:false,netImpact:null,post:null,snow:0};
  shootPaint(frame);$('shNet').classList.remove('shooting','settled');
}
function shootCancelAnimation(){if(shootSceneRun){cancelAnimationFrame(shootSceneRun.raf);shootSceneRun=null;}}
function shootAnimate(zone,keep,seed,onComplete){
  shootCancelAnimation();const plan=shootPlan(zone,keep,seed),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const run={plan,start:null,raf:0,onComplete};shootSceneRun=run;$('shNet').classList.add('shooting');
  const step=now=>{if(shootSceneRun!==run)return;if(run.start===null)run.start=now;
    const time=reduced?plan.duration:Math.min(plan.duration,(now-run.start)/1000);shootPaint(shootFrame(plan,time));
    if(time>=plan.duration){shootSceneRun=null;$('shNet').classList.remove('shooting');$('shNet').classList.add('settled');onComplete();return;}
    run.raf=requestAnimationFrame(step);
  };run.raf=requestAnimationFrame(step);return plan;
}
function shootFastForward(){if(shootSceneRun){const run=shootSceneRun;cancelAnimationFrame(run.raf);shootSceneRun=null;shootPaint(shootFrame(run.plan,run.plan.duration));$('shNet').classList.remove('shooting');$('shNet').classList.add('settled');}}
