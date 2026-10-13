// One connected rig and one clock for the goalie, puck, frame and net.
const NET_ZONES=[[179,137],[461,137],[179,304],[461,304],[320,321]];
const SH_GOAL={left:134,right:506,top:93,bottom:341,rearScale:.78,horizon:-32};
const shClamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const shLerp=(a,b,u)=>a+(b-a)*u;
const shEase=u=>{u=shClamp(u);return u*u*u*(u*(u*6-15)+10);};
const shPoint=(a,b,u)=>[shLerp(a[0],b[0],u),shLerp(a[1],b[1],u)];
const shRear=p=>[320+(p[0]-320)*SH_GOAL.rearScale,SH_GOAL.horizon+(p[1]-SH_GOAL.horizon)*SH_GOAL.rearScale];
const shRotate=(p,degrees,c=[0,0])=>{const a=degrees*Math.PI/180,x=p[0]-c[0],y=p[1]-c[1];return[c[0]+x*Math.cos(a)-y*Math.sin(a),c[1]+x*Math.sin(a)+y*Math.cos(a)];};
const shNumber=x=>Number(x.toFixed(3));
let shootSceneRun=null;

function shootPose(read,u=0,impact=0){
  const low=read>=2,side=read===0||read===2?-1:read===1||read===3?1:0;
  const drop=low?35:7,dx=side*(low?70:82),lean=side*(low?7:9);
  const contact=shPoint([320,414],NET_ZONES[read],.9);
  const blocker=read===0?[contact[0]-320-dx,contact[1]]:low?[-58,301]:[-68,248];
  const glove=read===1?[contact[0]-320-dx,contact[1]]:low?[67,296]:[76,242];
  const bodyDrop=drop*u,bodyLean=lean*u;
  const push=low?0:Math.sin(u*Math.PI);
  return {x:dx*u,drop:bodyDrop,lean:bodyLean,
    blocker:shPoint([-68,248],blocker,u),glove:shPoint([76,242],glove,u),
    kneeL:shPoint([-31+(side>0?-14:7)*push,265],[read===4?-10:-18,337],low?u:0),kneeR:shPoint([31+(side<0?14:-7)*push,265],[read===4?10:18,337],low?u:0),
    padL:shLerp(14+(side>0?18:-8)*push,read===3?73:82,low?u:0),padR:shLerp(-14+(side<0?-18:8)*push,read===2?-73:-82,low?u:0),
    stickScale:shLerp(1,.53,low?u:0),stickAngle:shLerp(0,-10,low?u:0),
    head:side*7*u,gloveClose:read===1?impact:0,absorb:impact};
}
function shootPlan(zone,keep,seed=0){
  if(!Number.isInteger(zone)||zone<0||zone>4)throw new Error('Invalid shootout target');
  const save=keep.includes(zone),read=save?zone:keep[0];
  const post=!save&&zone<4&&Math.abs(seed)%5===0;
  const point=post?[zone%2?SH_GOAL.right-5.5:SH_GOAL.left+5.5,NET_ZONES[zone][1]]:NET_ZONES[zone];
  const contact=shPoint([320,414],NET_ZONES[zone],.9),back=shRear(point);
  return {zone,save,read,post,point,contact,back,release:.16,contactAt:.592,planeAt:.64,netAt:post?.9:.81,duration:1.5};
}
function shootFrame(plan,time){
  const t=shClamp(time,0,plan.duration),flight=shClamp((t-plan.release)/(plan.planeAt-plan.release));
  const preparation=Math.sin(shClamp(t/plan.release)*Math.PI)*1.7;
  const action=shEase((t-.12)/.43),after=Math.max(0,t-plan.contactAt);
  const absorb=plan.save?Math.sin(shClamp(after/.18)*Math.PI)*Math.exp(-after*4):0;
  const pose=shootPose(plan.read,action,absorb);pose.drop+=preparation;
  pose.gloveClose=plan.save&&plan.zone===1?shEase(after/.085):0;
  let puck={x:320,y:414,scale:1,opacity:1,layer:'front',shadow:1,shadowY:414,rotation:0};
  if(t>=plan.release){const p=shPoint([320,414],plan.point,flight);puck={...puck,x:p[0],y:p[1],scale:shLerp(1,.53,flight),shadow:Math.max(.08,1-flight*.85),shadowY:shLerp(414,341,flight),rotation:flight*4};}
  if(plan.save&&t>=plan.contactAt){
    const p=plan.contact,u=shClamp(after/.51),side=plan.zone%2===0?-1:1;
    if(plan.zone===1){puck={...puck,x:p[0],y:p[1]+absorb*2,opacity:Math.max(0,1-after/.055),shadow:0};}
    else {const end=plan.zone===4?[338,406]:[shClamp(p[0]+side*(plan.zone<2?112:99),52,588),405];const q=shPoint(p,end,1-(1-u)*(1-u));puck={...puck,x:q[0],y:q[1]-Math.sin(u*Math.PI)*(plan.zone<2?24:8),scale:shLerp(.577,.78,u),shadow:.22,shadowY:shLerp(348.3,405,u),rotation:3.6*(1-u)+Math.sin(u*Math.PI)*(plan.zone<2?65:12)};}
  }
  if(!plan.save&&t>=plan.planeAt){
    const u=shEase((t-plan.planeAt)/(plan.netAt-plan.planeAt));
    // A glancing inner-post hit still crosses the line; it never changes the quiz outcome.
    const back=plan.post?[plan.back[0]+(plan.zone%2?-18:18),plan.back[1]+5]:plan.back;
    const q=shPoint(plan.point,back,u);
    puck={...puck,x:q[0],y:q[1],scale:shLerp(.53,.41,u),layer:t>plan.planeAt+.015?'back':'front',shadow:.13,shadowY:shLerp(341,259,u),rotation:4+(plan.post?Math.sin(u*Math.PI)*25:0)};
    if(t>=plan.netAt){const settle=shEase((t-plan.netAt)/.55),q2=shPoint(back,[back[0]+(320-back[0])*.045,255],settle);puck={...puck,x:q2[0],y:q2[1]-Math.sin(settle*Math.PI)*8,scale:.41,layer:'back',shadow:.12,rotation:4*(1-settle)+Math.sin(settle*Math.PI)*16};}
  }
  return {t,pose,puck,scored:!plan.save&&t>=plan.planeAt+(plan.post?.08:.025),saved:plan.save&&t>=plan.contactAt,
    netImpact:!plan.save&&t>=plan.netAt?{point:plan.post?[plan.back[0]+(plan.zone%2?-18:18),plan.back[1]+5]:plan.back,time:t-plan.netAt}:null,
    post:plan.post&&t>=plan.planeAt?{side:plan.zone%2,time:t-plan.planeAt}:null,
    snow:Math.sin(shClamp((t-.22)/.44)*Math.PI)*action};
}
function shootElbow(shoulder,hand,side){
  const mid=shPoint(shoulder,hand,.51),dx=hand[0]-shoulder[0],dy=hand[1]-shoulder[1],len=Math.hypot(dx,dy)||1,bend=Math.max(7,22-len*.13);
  return[mid[0]+side*dy/len*bend,mid[1]-side*dx/len*bend];
}
function shootMeshPoint(point,impact){
  if(!impact)return point;
  const [x,y]=point,[cx,cy]=impact.point,t=impact.time;
  const envelope=7*Math.sin(t*23)*Math.exp(-t*6.7),r=56+t*65;
  const weight=Math.exp(-((x-cx)**2+(y-cy)**2)/(2*r*r))*Math.sin((x-174)/292*Math.PI)*Math.sin((y-65)/194*Math.PI);
  return[x+(320-cx)/145*envelope*weight,y-envelope*.75*weight];
}
function shootMeshPath(axis,index,impact){
  const points=Array.from({length:13},(_,i)=>shootMeshPoint(axis==='h'?[174+i*292/12,65+index*194/18]:[174+index*292/26,65+i*194/12],impact));
  return points.map((p,i)=>(i?'L':'M')+p.map(shNumber).join(' ')).join(' ');
}
function shootPaint(frame){
  const a=(id,key,value)=>$(id).setAttribute(key,value),p=frame.pose;
  a('shGoalie','transform',`translate(${shNumber(320+p.x)} 0)`);
  a('shBody','transform',`translate(0 ${shNumber(p.drop)}) rotate(${shNumber(p.lean)} 0 259)`);
  a('shHead','transform',`rotate(${shNumber(p.head)} 0 174)`);
  a('shPants','transform',`translate(0 ${shNumber(p.drop)})`);
  for(const side of ['L','R']){const k=p['knee'+side];a('shPad'+side,'transform',`translate(${k.map(shNumber).join(' ')}) rotate(${shNumber(p['pad'+side])})`);}
  const sl=shRotate([-43,210+p.drop],p.lean,[0,259+p.drop]),sr=shRotate([43,210+p.drop],p.lean,[0,259+p.drop]);
  for(const [id,s,h,side] of [['shArmL',sl,p.blocker,-1],['shArmR',sr,p.glove,1]]){
    const e=shootElbow(s,h,side),path=`M${s.map(shNumber).join(' ')} Q${e.map(shNumber).join(' ')} ${h.map(shNumber).join(' ')}`;
    a(id,'d',path);a(id+'Stripe','d',`M${shPoint(e,h,.38).map(shNumber).join(' ')} L${shPoint(e,h,.6).map(shNumber).join(' ')}`);
  }
  a('shBlocker','transform',`translate(${p.blocker.map(shNumber).join(' ')}) rotate(${shNumber(-6-p.head*.8+p.absorb*7)})`);
  a('shGlove','transform',`translate(${p.glove.map(shNumber).join(' ')}) rotate(${shNumber(12+p.head+p.absorb*5)})`);
  a('shGloveThumb','transform',`rotate(${shNumber(p.gloveClose*17)} -12 12)`);
  a('shStick','transform',`translate(${shNumber(p.blocker[0]+8)} ${shNumber(p.blocker[1]+9)}) rotate(${shNumber(p.stickAngle)}) scale(1 ${shNumber(p.stickScale)})`);
  a('shKeeperShadow','cx',320+p.x);a('shKeeperShadow','rx',p.drop>20?100:77);a('shKeeperShadow','opacity',.23);
  for(const layer of ['Front','Back']){const visible=frame.puck.layer.toLowerCase()===layer.toLowerCase();
    a('shPuck'+layer,'transform',`translate(${shNumber(frame.puck.x)} ${shNumber(frame.puck.y)}) scale(${shNumber(frame.puck.scale)}) rotate(${shNumber(frame.puck.rotation)})`);a('shPuck'+layer,'opacity',visible?frame.puck.opacity:0);
    a('shPuckShadow'+layer,'cx',frame.puck.x);a('shPuckShadow'+layer,'cy',frame.puck.shadowY);a('shPuckShadow'+layer,'rx',8*frame.puck.scale);a('shPuckShadow'+layer,'opacity',visible?frame.puck.shadow*frame.puck.opacity:0);
  }
  for(let i=0;i<=18;i++)a('shMeshH'+i,'d',shootMeshPath('h',i,frame.netImpact));
  for(let i=0;i<=26;i++)a('shMeshV'+i,'d',shootMeshPath('v',i,frame.netImpact));
  const wobble=frame.post?Math.sin(frame.post.time*65)*Math.exp(-frame.post.time*13)*1.3:0;
  a('shPostL','transform',`translate(${frame.post?.side===0?shNumber(wobble):0} 0)`);a('shPostR','transform',`translate(${frame.post?.side===1?shNumber(wobble):0} 0)`);
  a('shCrossbar','transform',`translate(0 ${shNumber(wobble*.18)})`);
  a('shLampGlow','opacity',frame.scored?.22:0);a('shLamp','fill',frame.scored?'#ff5351':'#a8b7bf');
  a('shSnow','opacity',frame.snow*.62);a('shSnow','transform',`translate(${shNumber(320+p.x*.35)} 356) scale(${shNumber(.6+frame.snow)} 1)`);
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
