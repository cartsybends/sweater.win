// Equipment contours and ready joints follow the supplied frontal reference photograph.
const NET_ZONES=[[179,150],[461,150],[179,320],[461,320],[320,331]];
const SH_GOAL={left:134,right:506,top:110,bottom:358,postRadius:6,horizon:-32,scale:31/6,depth:40,roofDepth:22};
const SH_RIG={ground:390,padHalfWidth:35,padLength:163,hip:[0,228],shoulderL:[-68,137],shoulderR:[53,134],stickLength:152,blockerCuff:[-5,-42],gloveCuff:[-33.04,-15.34],grip:[19,-1]};
// World units are inches; gravity and time are slowed consistently for readable shot playback.
const SH_PHYS={gravity:180,step:1/240,startZ:-18,radius:12.2/(31/6),halfHeight:.55,netRestitution:.07,netTangent:.26,iceRestitution:.18,iceFriction:9};
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
const shOffset=(p,o,a)=>{const r=shRotate(o,a);return[p[0]+r[0],p[1]+r[1]];};
let shootSceneRun=null,shootMeshWarped=true;
const SH_PLAN_CACHE=new Map(),SH_CONTACTS=[];

function shootLaunch(point){
  const dt=.48,x=(point[0]-320)/SH_GOAL.scale,y=(358-point[1])/SH_GOAL.scale;
  return{vx:x/dt,vy:(y-SH_PHYS.halfHeight+.5*SH_PHYS.gravity*dt*dt)/dt,vz:-SH_PHYS.startZ/dt};
}
function shootFlight(plan,time){
  const t=Math.max(0,time-plan.release),v=plan.launch;
  return{x:v.vx*t,y:SH_PHYS.halfHeight+v.vy*t-.5*SH_PHYS.gravity*t*t,z:SH_PHYS.startZ+v.vz*t,vx:v.vx,vy:v.vy-SH_PHYS.gravity*t,vz:v.vz};
}
function shootReferenceContact(read){
  if(!SH_CONTACTS[read]){const p={release:.16,launch:shootLaunch(NET_ZONES[read])},w=shootFlight(p,.592);SH_CONTACTS[read]=shProject(w.x,w.y,w.z);}
  return SH_CONTACTS[read];
}
function shootPose(read,u=0,impact=0){
  const low=read>=2,side=read===0||read===2?-1:read===1||read===3?1:0,dx=side*(low?57:48);
  const drop=(low?88:2)*u,lean=side*(low?3:4)*u,contact=shootReferenceContact(read),push=low?0:Math.sin(u*Math.PI);
  const padL=shLerp(31+(side>0?5:-2)*push,84,low?u:0),padR=shLerp(-31+(side<0?-5:2)*push,-84,low?u:0);
  const shoulders=[shRotate(SH_RIG.shoulderL,lean,SH_RIG.hip),shRotate(SH_RIG.shoulderR,lean,SH_RIG.hip)].map(p=>[p[0],p[1]+drop]);
  const blockerAngle=shLerp(17,read===0?-8:low?7:17,u),gloveAngle=shLerp(0,read===1?-6:low?8:0,u);
  const blocker=shPoint([-100.3,245.49],read===0?[contact[0]-320-dx,contact[1]]:low?[-93,304]:[-101,247],u);
  const glove=shPoint([103.84,207.14],read===1?[contact[0]-320-dx,contact[1]]:low?[99,293]:[104,208],u);
  blocker[1]+=impact*1.1;glove[1]+=impact*1.1;
  const elbowL=[shoulders[0][0]-shLerp(28,read===0?42:low?42:28,u)-Math.sin(u*Math.PI)*(read===0?14:low?6:0),shoulders[0][1]+shLerp(50,read===0?46:low?50:50,u)];
  const elbowR=[shoulders[1][0]+shLerp(13,read===1?40:low?36:13,u)+(low?Math.sin(u*Math.PI)*9:0),shoulders[1][1]+shLerp(33,read===1?42:low?52:33,u)];
  return{x:dx*u,drop,lean,shoulderL:shoulders[0],shoulderR:shoulders[1],elbowL,elbowR,blocker,glove,
    wristL:shOffset(blocker,SH_RIG.blockerCuff,blockerAngle),wristR:shOffset(glove,SH_RIG.gloveCuff,gloveAngle),
    kneeL:[shLerp(-45+(side>0?-5:2)*push,read===4?-8:-20,low?u:0),shPadY(padL)],
    kneeR:[shLerp(45+(side<0?5:-2)*push,read===4?8:20,low?u:0),shPadY(padR)],padL,padR,
    head:side*3*u,blockerAngle,gloveAngle,gloveClose:read===1?impact:0,absorb:impact};
}
function shootNetBoundary(w){
  const a=36-SH_PHYS.radius,d=40-18*shClamp(w.y/48)-SH_PHYS.radius;
  return w.x*w.x/(a*a)+w.z*w.z/(d*d)-1;
}
function shootNetNormal(w){
  const a=36-SH_PHYS.radius,d=40-18*shClamp(w.y/48)-SH_PHYS.radius;
  const n=[2*w.x/(a*a),w.y>0&&w.y<48?.75*w.z*w.z/(d*d*d):0,2*w.z/(d*d)],len=Math.hypot(...n);
  return n.map(v=>v/len);
}
function shootMove(w,dt){return{...w,x:w.x+w.vx*dt,y:w.y+w.vy*dt-.5*SH_PHYS.gravity*dt*dt,z:w.z+w.vz*dt,vy:w.vy-SH_PHYS.gravity*dt};}
function shootGround(prev,w,dt,events,endTime){
  let onIce=0;
  if(w.y<SH_PHYS.halfHeight){
    const g=SH_PHYS.gravity,h=SH_PHYS.halfHeight,tau=shClamp((prev.vy+Math.sqrt(Math.max(0,prev.vy*prev.vy+2*g*(prev.y-h))))/g,0,dt);
    const hit=shootMove(prev,tau),speed=-hit.vy,remaining=dt-tau;hit.y=h;
    if(speed>7){hit.vy=speed*SH_PHYS.iceRestitution;events.push({kind:'ice',time:endTime-dt+tau,point:[hit.x,h,hit.z],speed});w=shootMove(hit,remaining);}
    else{hit.vy=0;w={...hit,x:hit.x+hit.vx*remaining,z:hit.z+hit.vz*remaining};onIce=remaining;}
  }
  if(w.y<=SH_PHYS.halfHeight+.0001&&Math.abs(w.vy)<.01){
    w.y=SH_PHYS.halfHeight;w.vy=0;
    const speed=Math.hypot(w.vx,w.vz),next=Math.max(0,speed-SH_PHYS.iceFriction*(onIce||dt));
    if(speed){w.vx*=next/speed;w.vz*=next/speed;}
  }
  return w;
}
function shootBuildTrajectory(plan){
  const events=[],samples=[];let t=plan.save?plan.contactAt:plan.planeAt,w=shootFlight(plan,t);
  if(plan.save&&plan.zone===1){plan.events=events;plan.samples=[];plan.duration=1.7;return;}
  if(plan.save){w.vz=-w.vz*(plan.zone<2?.50:.32);w.vx=w.vx*(plan.zone<2?.50:.22);w.vy=Math.min(w.vy*.28,8);}
  if(plan.post){
    // The inside of the tube reflects the lateral component while the puck keeps entering the goal.
    events.push({kind:'post',time:t,side:plan.zone%2,point:[w.x,w.y,w.z]});w.vx=-w.vx*.67;w.vy*=.88;
  }
  samples.push({t,...w});
  while(t<3){
    const dt=Math.min(SH_PHYS.step,3-t),prev=w;let next=shootMove(prev,dt),moveStart=prev,moveDt=dt;
    if(!plan.save&&next.z>=0&&shootNetBoundary(next)>0){
      let lo=0,hi=dt;
      for(let j=0;j<16;j++){const mid=(lo+hi)/2;if(shootNetBoundary(shootMove(prev,mid))>0)hi=mid;else lo=mid;}
      const tau=(lo+hi)/2,hit=shootMove(prev,tau),n=shootNetNormal(hit),vn=hit.vx*n[0]+hit.vy*n[1]+hit.vz*n[2];
      if(vn>0){
        const r=SH_PHYS.radius,cloth=[hit.x+n[0]*r,hit.y+n[1]*r,hit.z+n[2]*r],uv=[.5+Math.asin(shClamp(cloth[0]/36,-1,1))/Math.PI,shClamp(cloth[1]/48)];
        const point=shootNetPoint(...uv),weight=Math.min(1,vn/45);
        events.push({kind:'net',time:t+tau,point,uv,world:[hit.x,hit.y,hit.z],normal:n,incoming:[hit.vx,hit.vy,hit.vz],speed:vn,amplitude:18+weight*7});
        const v=[hit.vx,hit.vy,hit.vz].map((v,i)=>(v-vn*n[i])*SH_PHYS.netTangent-vn*n[i]*SH_PHYS.netRestitution);
        events.at(-1).outgoing=v;hit.vx=v[0];hit.vy=v[1];hit.vz=v[2];
        hit.x-=n[0]*.0001;hit.y-=n[1]*.0001;hit.z-=n[2]*.0001;
        next=shootMove(hit,dt-tau);moveStart=hit;moveDt=dt-tau;
      }
    }
    next=shootGround(moveStart,next,moveDt,events,t+dt);
    // Ground friction brings each shot to its own rest point; there is no scripted landing destination.
    w=next;t+=dt;samples.push({t,...w});
  }
  plan.samples=samples;plan.events=events;plan.netAt=events.find(e=>e.kind==='net')?.time??null;plan.duration=3;
  const final=samples.at(-1);plan.rest=shProject(final.x,final.y,final.z);
}
function shootPlan(zone,keep,seed=0){
  if(!Number.isInteger(zone)||zone<0||zone>4)throw new Error('Invalid shootout target');
  const save=keep.includes(zone),post=!save&&zone<4&&Math.abs(seed)%5===0,key=[zone,save,post,Math.abs(seed)%2].join(':');
  if(SH_PLAN_CACHE.has(key))return SH_PLAN_CACHE.get(key);
  const read=save?zone:zone===0||zone===2?1:zone===1||zone===3?0:Math.abs(seed)%2;
  const inside=SH_GOAL.postRadius+12.2,point=post?[zone%2?SH_GOAL.right-inside:SH_GOAL.left+inside,NET_ZONES[zone][1]]:NET_ZONES[zone];
  const plan={zone,save,read,post,point,launch:shootLaunch(point),release:.16,contactAt:.592,planeAt:.64,goalAt:.64+SH_PHYS.radius/37.5,duration:3,netAt:null};
  const w=shootFlight(plan,plan.contactAt);plan.contact=shProject(w.x,w.y,w.z);
  shootBuildTrajectory(plan);
  if(SH_PLAN_CACHE.size>=20)SH_PLAN_CACHE.delete(SH_PLAN_CACHE.keys().next().value);SH_PLAN_CACHE.set(key,plan);return plan;
}
function shootState(plan,time){
  const start=plan.save?plan.contactAt:plan.planeAt;
  if(time<=start||!plan.samples.length)return shootFlight(plan,Math.min(time,start));
  const samples=plan.samples,index=shClamp(Math.floor((time-start)/SH_PHYS.step),0,samples.length-2),a=samples[index],b=samples[index+1],u=shClamp((time-a.t)/(b.t-a.t));
  const out={};for(const k of ['x','y','z','vx','vy','vz'])out[k]=shLerp(a[k],b[k],u);return out;
}
function shootFrame(plan,time){
  const t=shClamp(time,0,plan.duration),action=shEase((t-.12)/.43),after=Math.max(0,t-plan.contactAt),absorb=plan.save?Math.sin(shClamp(after/.18)*Math.PI)*Math.exp(-after*4):0;
  const pose=shootPose(plan.read,action,absorb);if(!plan.save&&plan.zone===4)pose.x=0;
  pose.gloveClose=plan.save&&plan.zone===1?shEase(after/.11):0;
  const w=shootState(plan,t),p=shProject(w.x,w.y,w.z),shadow=shProject(w.x,0,w.z),scale=1/(1+w.z*.007);
  const netEvents=(plan.events||[]).filter(e=>e.kind==='net'&&t>=e.time&&t-e.time<1),netImpacts=netEvents.map(e=>({...e,time:t-e.time}));
  const struck=(plan.events||[]).find(e=>e.kind==='net'&&t>=e.time),rock=struck?Math.sin((t-struck.time)*27)*Math.exp(-(t-struck.time)*3.4)*Math.min(11,Math.abs(w.vy)/7):0;
  let puck={x:p[0],y:p[1],scale,opacity:1,layer:!plan.save&&w.z>SH_PHYS.radius?'back':'front',shadow:.24*Math.exp(-Math.max(0,w.y)/18),shadowY:shadow[1],rotation:w.y<=.65?0:rock,world:w};
  if(plan.save&&plan.zone===1&&t>=plan.contactAt)puck={...puck,x:plan.contact[0],y:plan.contact[1]+absorb*1.1,opacity:Math.max(0,1-after/.08),shadow:0};
  return{t,pose,puck,scored:!plan.save&&t>=plan.goalAt,saved:plan.save&&t>=plan.contactAt,netImpact:netImpacts[0]??null,netImpacts,
    post:plan.post&&t>=plan.planeAt?{side:plan.zone%2,time:t-plan.planeAt}:null,snow:Math.sin(shClamp((t-.22)/.44)*Math.PI)*action};
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
  const impacts=Array.isArray(impact)?impact:[impact];let dx=0,dy=0;
  for(const hit of impacts){
    const [cx,cy]=hit.point,t=hit.time,distance=Math.hypot(point[0]-cx,point[1]-cy),arrival=distance/420,q=t-arrival;
    if(q<=0)continue;
    const amp=(hit.amplitude??22)*Math.sin(q*20)*Math.exp(-q*5.2)*Math.exp(-distance*distance/(2*72*72));
    const root=hit.uv??shootNetUV(hit.point),anchor=Math.max(.08,Math.sin(root[0]*Math.PI)*Math.sin(root[1]*Math.PI));
    const weight=Math.min(1.25,tie/anchor),normal=hit.normal??[(cx-320)/180,0,.7];
    dx+=normal[0]*amp*weight*.75;dy-=amp*weight*(.5+normal[2]*.45);
  }
  return[point[0]+dx,point[1]+dy];
}
function shootMeshPath(axis,index,impact){
  const line=SH_MESH_LINES.find(p=>p.axis===axis&&p.index===index);
  return line.points.map(({point,uv,tie},i)=>(i?'L':'M')+shootMeshPoint(point,impact,uv,tie).map(shNumber).join(' ')).join(' ');
}
function shootStick(p){
  const grip=shOffset(p.blocker,SH_RIG.grip,p.blockerAngle),rise=139.91,run=Math.sqrt(SH_RIG.stickLength**2-rise**2);
  // The rigid stick pitches about its horizontal blade in a drop; its hidden depth increases.
  const dy=shClamp(SH_RIG.ground-grip[1],0,rise),depth=Math.sqrt(Math.max(0,SH_RIG.stickLength**2-run**2-dy**2));
  const end=[grip[0]+run,grip[1]+dy],projection=Math.hypot(run,dy)/SH_RIG.stickLength;
  return{grip,end,depth,projection,angle:Math.atan2(dy,run)*180/Math.PI-90};
}
function shootPostPath(side,w=0,shine=false){
  const x=side?506:134,s=side?-1:1,offset=shine?-s*1.8:0;
  return`M${shNumber(x+offset)} 358 C${shNumber(x+offset)} 277 ${shNumber(x+w+offset)} 193 ${shNumber(x+w*.6+offset)} 122 Q${shNumber(x+w*.6+offset)} ${shine?112:110} ${shNumber(x+s*8+w*.3+offset)} ${shine?112:110}`;
}
function shootPaint(frame){
  const a=(id,key,value)=>$(id).setAttribute(key,value),p=frame.pose;
  a('shGoalie','transform',`translate(${shNumber(320+p.x)} 0)`);
  a('shBody','transform',`translate(0 ${shNumber(p.drop)}) rotate(${shNumber(p.lean)} 0 228)`);
  a('shHead','transform',`rotate(${shNumber(p.head)} 0 107)`);
  a('shPants','transform',`translate(0 ${shNumber(p.drop)})`);
  for(const side of ['L','R']){
    const k=p['knee'+side],s=p['shoulder'+side],e=p['elbow'+side],h=p['wrist'+side];
    a('shPad'+side,'transform',`translate(${k.map(shNumber).join(' ')}) rotate(${shNumber(p['pad'+side])})`);
    a('shArm'+side,'d',`M${s.map(shNumber).join(' ')} L${e.map(shNumber).join(' ')}`);
    a('shForearm'+side,'d',`M${e.map(shNumber).join(' ')} L${h.map(shNumber).join(' ')}`);
    a('shArm'+side+'Stripe','d',`M${shPoint(e,h,.3).map(shNumber).join(' ')} L${shPoint(e,h,.57).map(shNumber).join(' ')}`);
    a('shElbow'+side,'transform',`translate(${e.map(shNumber).join(' ')}) rotate(${shNumber(Math.atan2(h[1]-e[1],h[0]-e[0])*180/Math.PI)})`);
  }
  a('shBlocker','transform',`translate(${p.blocker.map(shNumber).join(' ')}) rotate(${shNumber(p.blockerAngle)})`);
  a('shGlove','transform',`translate(${p.glove.map(shNumber).join(' ')}) rotate(${shNumber(p.gloveAngle)})`);
  a('shBlockerHand','transform',`translate(${p.blocker.map(shNumber).join(' ')}) rotate(${shNumber(p.blockerAngle)})`);
  a('shGloveThumb','transform',`rotate(${shNumber(p.gloveClose*13)} -33 -15)`);
  a('shGlovePocket','transform',`translate(-33 -15) scale(${shNumber(1-p.gloveClose*.18)} 1) translate(33 15)`);
  const stick=shootStick(p);a('shStick','transform',`translate(${stick.grip.map(shNumber).join(' ')}) rotate(${shNumber(stick.angle)}) scale(1 ${shNumber(stick.projection)})`);
  a('shStickBlade','transform',`translate(${stick.end.map(shNumber).join(' ')}) rotate(0)`);
  a('shKeeperShadow','cx',320+p.x);a('shKeeperShadow','rx',p.drop>20?174:148);a('shKeeperShadow','cy',389);
  for(const layer of ['Front','Back']){const visible=frame.puck.layer.toLowerCase()===layer.toLowerCase();
    a('shPuck'+layer,'transform',`translate(${shNumber(frame.puck.x)} ${shNumber(frame.puck.y)}) scale(${shNumber(frame.puck.scale)}) rotate(${shNumber(frame.puck.rotation)})`);a('shPuck'+layer,'opacity',visible?frame.puck.opacity:0);
    a('shPuckShadow'+layer,'cx',frame.puck.x);a('shPuckShadow'+layer,'cy',frame.puck.shadowY);a('shPuckShadow'+layer,'rx',8*frame.puck.scale);a('shPuckShadow'+layer,'opacity',visible?frame.puck.shadow*frame.puck.opacity:0);
  }
  if((frame.netImpacts?.length||frame.netImpact)||shootMeshWarped){for(const line of SH_MESH_LINES)a(line.id,'d',shootMeshPath(line.axis,line.index,frame.netImpacts??frame.netImpact));shootMeshWarped=!!(frame.netImpacts?.length||frame.netImpact);}
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
  shootCancelAnimation();const start=shProject(0,SH_PHYS.halfHeight,SH_PHYS.startZ),shadow=shProject(0,0,SH_PHYS.startZ);const frame={pose:shootPose(4),puck:{x:start[0],y:start[1],scale:1/(1+SH_PHYS.startZ*.007),opacity:aim?1:0,layer:'front',shadow:aim?.24:0,shadowY:shadow[1],rotation:0},scored:false,saved:false,netImpact:null,post:null,snow:0};
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
