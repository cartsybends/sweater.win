// Analytic contact, frame-rate independence, stored shots and canceled playback.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const source=fs.readFileSync('build_sweater.py','utf8');
const animation=fs.readFileSync('static/shootout/animation.js','utf8');
const svg=fs.readFileSync('static/shootout/scene.svg','utf8');
const elements=new Map(),frames=new Map(),documentEvents={},windowEvents={};
let nextFrame=0,now=0,reduced=false,saves=0,finishes=[],marks=[];
class Element{
  constructor(){this.attrs={};this.events={};this.dataset={};this.hidden=false;this.classes=new Set();this.classList={add:(...x)=>x.forEach(c=>this.classes.add(c)),remove:(...x)=>x.forEach(c=>this.classes.delete(c)),toggle:(c,v)=>{if(v===undefined)v=!this.classes.has(c);v?this.classes.add(c):this.classes.delete(c);},contains:c=>this.classes.has(c)};}
  setAttribute(k,v){this.attrs[k]=String(v);}
  addEventListener(k,fn){this.events[k]=fn;}
  querySelectorAll(selector){return selector==='.zone'?zones:selector==='button'?shotButtons:[];}
  closest(selector){return selector==='[data-z]'&&this.dataset.z!==undefined||selector==='[data-c]'&&this.dataset.c!==undefined?this:null;}
}
const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
for(const match of svg.matchAll(/id="([^"]+)"/g))$(match[1]);
const zones=Array.from({length:5},(_,i)=>{const el=new Element();el.dataset.z=String(i);return el;});
const shotButtons=Array.from({length:5},(_,i)=>{const el=new Element();el.dataset.z=String(i);return el;});
const context=vm.createContext({console,Math,Number,String,JSON,Array,Set,Map,$,G:{},S:{shoot:{target:null,guesses:[],over:false,mode:'unlimited'}},game:'shoot',mode:'unlimited',onHub:false,PLAYERS:Array(20),DAILY:{shoot:{}},
  esc:String,paintQuestionProgress:(_id,_n,_i,m)=>{marks=m;},paintOptions(){},renderOptions(){},updateLabels(){},
  saveProgress(){saves++;},isDone:(g,t,x)=>x.length>=5,
  finish(won,fresh){const st=context.S.shoot;st.over=true;finishes.push({won,fresh,quiet:context.G.shoot.quietFinish,mode:context.mode});},
  requestAnimationFrame:fn=>{const id=++nextFrame;frames.set(id,fn);return id;},cancelAnimationFrame:id=>frames.delete(id),
  matchMedia:()=>({matches:reduced}),document:{hidden:false,addEventListener:(name,fn)=>{documentEvents[name]=fn;}},window:{addEventListener:(name,fn)=>{windowEvents[name]=fn;}}});
const run=code=>vm.runInContext(code,context);
function part(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert(a>=0&&b>a);return source.slice(a,b);}
run(part('function hash(str)','// ---- dates:'));
run(animation);
run(part('// ---- Shootout: answer to earn a shot','// ---- Overtime ----'));
run(part('function doGuess(x, fresh = true)','function finish(won, fresh)'));
const target={rounds:Array.from({length:5},(_,i)=>({q:'Question '+i,o:['Correct','Wrong 1','Wrong 2','Wrong 3'],a:0,keep:[0,1]})),rid:1};
function reset(){run('shootCancelAnimation()');now=0;saves=0;finishes=[];context.game='shoot';context.mode='unlimited';context.document.hidden=false;Object.assign(context.S.shoot,{target:JSON.parse(JSON.stringify(target)),guesses:[],over:false,mode:'unlimited'});run('G.shoot.reset();G.shoot.render(S.shoot.target,S.shoot)');}
function frame(dt=1000/60){now+=dt;const batch=[...frames.values()];frames.clear();for(const fn of batch)fn(now);}
function drain(fps=60){for(let i=0;frames.size&&i<800;i++)frame(1000/fps);assert.equal(frames.size,0);}
function choose(zone){const el=new Element();el.dataset.c='0';$('shOpts').events.click({target:el});$('shNet').events.click({target:zones[zone]});}

let sampled=0;
const restPoints=new Set();
function padDistance(f,side){
  const p=f.pose,k=p['knee'+side],r=-p['pad'+side]*Math.PI/180,x=f.puck.x-320-p.x-k[0],y=f.puck.y-k[1],px=x*Math.cos(r)-y*Math.sin(r),py=x*Math.sin(r)+y*Math.cos(r);
  return Math.hypot(Math.max(-35-px,0,px-35),Math.max(-14-py,0,py-163));
}
for(let a=0;a<5;a++)for(let b=a+1;b<5;b++)for(let zone=0;zone<5;zone++)for(const seed of [1,5]){
  const expr=`shootPlan(${zone},[${a},${b}],${seed})`,plan=run(expr);run(`var qaPlan=${expr}`);
  assert.equal(plan.save,[a,b].includes(zone));
  if(plan.post)assert(Math.abs(Math.abs(plan.point[0]-(zone%2?506:134))-(6+12.2))<1e-9,'Tube contact includes the visible puck and post radii');
  for(const at of [plan.release,plan.contactAt,plan.planeAt,...plan.events.map(e=>e.time)]){
    const before=run(`shootFrame(qaPlan,${at-1e-6})`),after=run(`shootFrame(qaPlan,${at+1e-6})`);
    assert(Math.hypot(before.puck.x-after.puck.x,before.puck.y-after.puck.y)<.025,'Neither an impact nor a phase change can teleport the puck');
    assert(Math.abs(before.puck.scale-after.puck.scale)<.0001,'Puck scaling stays continuous through all impacts');
  }
  const contact=run('shootFrame(qaPlan,qaPlan.contactAt)');
  if(plan.save&&zone<2){const hand=zone===0?contact.pose.blocker:contact.pose.glove;assert(Math.hypot(320+contact.pose.x+hand[0]-contact.puck.x,hand[1]-contact.puck.y)<.01,'The actual equipment meets the puck');}
  if(plan.save&&zone>=2)assert(Math.min(padDistance(contact,'L'),padDistance(contact,'R'))<13,'A low save intersects a real pad');
  if(!plan.save)assert(Math.min(padDistance(contact,'L'),padDistance(contact,'R'))>13,'A goal clears both pads at the keeper plane');
  const release=run('shootFrame(qaPlan,qaPlan.release)'),plane=run('shootFrame(qaPlan,qaPlan.planeAt)');
  if(!plan.save)assert(plane.puck.scale/release.puck.scale>.87,'The short flight reduces puck diameter by less than 13%');
  for(let i=0;i<=300;i++){
    const f=run(`shootFrame(qaPlan,${i/100})`),w=f.puck.world;
    for(const value of [f.puck.x,f.puck.y,f.puck.scale,...Object.values(w)])assert(Number.isFinite(value));
    assert(w.y>=.55-1e-8,'The puck never penetrates the ice');
    if(plan.save){assert.equal(f.scored,false);assert.equal(f.netImpact,null);assert.equal(f.puck.layer,'front');}
    if(f.scored)assert(f.t>=plan.goalAt,'The lamp waits for the entire puck to cross the goal line');
    if(f.netImpact)assert(f.t>=plan.netAt,'Cloth movement waits for a physical net contact');
    sampled++;
  }
  const final=run('shootFrame(qaPlan,qaPlan.duration)');
  if(!plan.save){
    assert(plan.netAt!==null&&plan.netAt>plan.planeAt,'Every goal contacts the actual net');
    const w=final.puck.world,A=36-12.2/(31/6),D=40-18*w.y/48-12.2/(31/6);
    assert(w.z>12.2/(31/6)&&w.x*w.x/(A*A)+w.z*w.z/(D*D)<=1.0001,'The resting puck is fully inside the curved goal');
    assert.equal(w.y,.55);assert.equal(w.vx,0);assert.equal(w.vy,0);assert.equal(w.vz,0);assert.equal(final.puck.rotation,0,'Friction leaves a flat, stationary puck');
    assert.equal(final.puck.layer,'back');assert(final.puck.scale>.78,'The puck stays readable even at the back of the goal');
    restPoints.add([w.x.toFixed(2),w.z.toFixed(2)].join(','));
    for(const e of plan.events){
      if(e.kind==='net'){
        const[x,y,z]=e.world,d=40-18*Math.max(0,Math.min(1,y/48))-12.2/(31/6);
        assert(Math.abs(x*x/(A*A)+z*z/(d*d)-1)<.0001,'The impulse occurs on the curved net surface');
        assert(Math.abs(Math.hypot(...e.normal)-1)<1e-9);
        assert(Math.hypot(...e.outgoing)<Math.hypot(...e.incoming),'Net absorption reduces kinetic energy');
        assert(e.outgoing.reduce((n,v,i)=>n+v*e.normal[i],0)<=0,'The net reaction points back into the goal');
      }
      if(e.kind==='ice')assert.equal(e.point[1],.55,'A bounce starts exactly at the ice surface');
    }
  }
  if(plan.save&&zone===1){assert.equal(final.puck.opacity,0);assert.equal(final.pose.gloveClose,1);}
}
assert(restPoints.size>=7,'Shot height, side and post contact produce different physical resting locations');
// Before impact, world-space vertical acceleration is gravity, independent of animation frame rate.
run('var gravityPlan=shootPlan(0,[1,2],1)');
const y1=run('shootFrame(gravityPlan,.25).puck.world.y'),y2=run('shootFrame(gravityPlan,.30).puck.world.y'),y3=run('shootFrame(gravityPlan,.35).puck.world.y');
assert(Math.abs((y3-2*y2+y1)/(.05*.05)+180)<1e-8);
assert.equal(run('shootMeshPath("h",9,null)'),run('shootMeshPath("h",9,{point:[320,160],uv:[.5,.5],time:0})'));
const impact=run('shootPlan(0,[1,2],1).events.find(e=>e.kind==="net")');
let maxWarp=0;
for(const line of run('SH_MESH_LINES'))for(const p of line.points){
  const changed=run(`shootMeshPoint([${p.point}],[{point:[${impact.point}],uv:[${impact.uv}],normal:[${impact.normal}],amplitude:25,time:.12}],[${p.uv}],${p.tie})`);
  maxWarp=Math.max(maxWarp,Math.hypot(changed[0]-p.point[0],changed[1]-p.point[1]));
}
assert(maxWarp>5,'The cloth visibly flexes at the measured collision point');
for(const[u,v]of [[0,.5],[1,.5],[.5,0],[.5,1]]){
  const before=[...run(`shootNetPoint(${u},${v})`)],after=[...run(`shootMeshPoint(shootNetPoint(${u},${v}),{point:[320,160],uv:[.5,.5],time:.08},[${u},${v}])`)];
  assert(Math.hypot(after[0]-before[0],after[1]-before[1])<1e-9,'Frame ties remain fixed as the fabric moves');
}
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
function sleeveIntersections(points){
  let count=0;for(let i=0;i<points.length;i++)for(let j=i+2;j<points.length;j++){
    if(i===0&&j===points.length-1)continue;
    const a=points[i],b=points[(i+1)%points.length],c=points[j],d=points[(j+1)%points.length];
    if(cross(a,b,c)*cross(a,b,d)<-1e-7&&cross(c,d,a)*cross(c,d,b)<-1e-7)count++;
  }return count;
}
for(let read=0;read<5;read++)for(let i=0;i<=1000;i++){
  const p=run(`shootPose(${read},${i/1000})`),stick=run(`shootStick(shootPose(${read},${i/1000}))`);
  for(const side of ['L','R']){
    const s=p['shoulder'+side],e=p['elbow'+side],h=p['wrist'+side],sign=side==='L'?-1:1,depth=p['elbowDepth'+side];
    const a=[e[0]-s[0],e[1]-s[1],depth],b=[h[0]-e[0],h[1]-e[1],-depth],upper=Math.hypot(...a),fore=Math.hypot(...b),bend=Math.acos(a.reduce((sum,v,k)=>sum+v*b[k],0)/(upper*fore));
    assert(Math.abs(upper-run(`SH_RIG.upper${side}`))<1e-8&&Math.abs(fore-run(`SH_RIG.fore${side}`))<1e-8,'Both arm bones retain their lengths as the forearm turns toward the shooter');
    assert(bend>1&&bend<2.27,'The actual elbow angle stays in a natural flexion range through its full shoulder rotation');
    assert(sign*h[0]>30&&Math.hypot(b[0],b[1])>17,'Projected wrists cannot collapse or cross the torso');
    const expected=run(`shOffset([${side==='L'?p.blocker:p.glove}],SH_RIG.${side==='L'?'blockerCuff':'gloveCuff'},${side==='L'?p.blockerAngle:p.gloveAngle})`);
    assert(Math.hypot(h[0]-expected[0],h[1]-expected[1])<1e-9,'The sleeve ends at the wrist behind the padded hand');
    const shoulder=run(`shRotate(SH_RIG.shoulder${side},${p.lean},SH_RIG.hip)`);
    assert(Math.hypot(s[0]-shoulder[0],s[1]-shoulder[1]-p.drop)<1e-9,'The shoulder root follows the torso transform exactly');
    {
      const sleeve=run(`shootSleeve(shootPose(${read},${i/1000}),"${side}")`),outline=[...sleeve.points.map(q=>q.left),...sleeve.points.slice().reverse().map(q=>q.right)];
      assert.equal(sleeveIntersections(outline),0,'The single sleeve outline cannot cross itself or form a pinched elbow');
      assert(sleeve.outline.endsWith(' Z')&&!/NaN|Infinity/.test(sleeve.outline),'The sleeve remains a closed, continuous silhouette');
      assert(sleeve.yoke.endsWith(' Z')&&!/NaN|Infinity/.test(sleeve.yoke),'The shoulder yoke stays part of the continuous sleeve');
    }
    const angle=Math.abs(p['pad'+side])*Math.PI/180,k=p['knee'+side];
    assert(Math.abs(k[1]+35*Math.sin(angle)+163*Math.cos(angle)-390)<1e-8,'Skates and pads remain on the ice through the drop');
  }
  assert(p.blockerAngle>=-12&&p.blockerAngle<=17,'The blocker stays upright while the shoulder and elbow lift the hand');
  const reference=run('SH_STICK'),[a,b,c,d,x,y]=stick.matrix,[gx,gy]=reference.grip;
  assert(Math.hypot(a*gx+c*gy+x-stick.grip[0],b*gx+d*gy+y-stick.grip[1])<1e-8,'The photographed paddle shoulder stays inside the blocker grip');
  const theta=(p.stickTurn||0)*Math.PI/180,zx=reference.scale*Math.sin(theta)*stick.depth,zy=reference.scale*Math.cos(theta)*stick.depth;
  assert(Math.abs(Math.hypot(a,b,zx)-reference.scale)<1e-9&&Math.abs(Math.hypot(c,d,zy)-reference.scale)<1e-9,'The complete shaft, paddle and blade retain their rigid dimensions in 3D');
  assert(Math.abs(a*c+b*d+zx*zy)<1e-9,'The whole stick is projected without bending its heel or changing its blade separately');
  const bottom=Math.max(...reference.bounds.map(([px,py])=>b*px+d*py+y));
  assert(bottom<=390+1e-8,'No part of the traced blade can penetrate the ice');
  if(read===0&&i===1000)assert(bottom<330,'The stick lifts with the high blocker rather than stretching back to the ground');
}
for(const side of [0,1])for(const w of [-.8,0,.8])assert(run(`shootPostPath(${side},${w})`).startsWith(`M${side?506:134} 358 `),'Posts remain anchored during a ring');
assert(svg.indexOf('id="shBody"')<svg.indexOf('id="shSleeveL"'),'Continuous sleeves stay in front of the torso');
assert(svg.indexOf('id="shSleeveL"')<svg.indexOf('id="shBlocker"'),'Equipment stays in front of the wrist');
for(const id of ['shShoulderYokeL','shShoulderYokeR','shBlockerPalm','shBlockerThumb','shGlovePalm','shGloveHandThumb'])assert(svg.includes(`id="${id}"`),'Each shoulder and hand has visible artwork');
assert(svg.indexOf('id="shSleeveL"')<svg.indexOf('id="shBlockerHand"')&&svg.indexOf('id="shBlockerHand"')<svg.indexOf('id="shBlocker"'),'The blocker hand bridges the jersey cuff and the board');
assert(svg.indexOf('id="shSleeveR"')<svg.indexOf('id="shGloveHand"')&&svg.indexOf('id="shGloveHand"')<svg.indexOf('id="shGlove"'),'The catcher encloses a padded palm behind its cuff');
assert(!/id="sh(?:Forearm|Arm[LR]|Elbow|StickBlade)/.test(svg),'Separate arm modules and independently animated blade pieces are gone');
const photo=svg.match(/<image[^>]+id="shStickPhoto"[^>]+href="data:image\/webp;base64,([^"]+)"/);
assert(photo,'The plain stick finish stays inside its reference silhouette');
assert.equal(crypto.createHash('sha256').update(Buffer.from(photo[1],'base64')).digest('hex'),'60f627d29b80aec4d12bfc010d5d41967643535e22adfbf4577b3b6f732cc4c4','The stick keeps the reviewed unbranded finish');
assert.equal([...svg.matchAll(/class="sh-target-hit"[^>]*r="47"/g)].length,5,'Every on-net target retains a large touch area');
const css=fs.readFileSync('static/shootout/styles.css','utf8');
function luminance(hex){return hex.match(/[0-9a-f]{2}/gi).map(s=>parseInt(s,16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);}
assert((luminance('f4f4f5')+.05)/(luminance('171719')+.05)>9);
assert.match(css,/\.sh-shot\{[^}]*min-height:50px/);

for(const fps of [15,30,60,144]){
  reset();for(let i=0;i<5;i++){
    choose(2);assert.equal(context.S.shoot.guesses.length,i+1,'The accepted shot is stored immediately');assert.equal(run('shootUI.phase'),'shot');assert.equal($('shNext').hidden,true);assert.equal(marks[i],null,'The outcome marker waits for the shot');
    $('shNet').events.click({target:zones[3]});assert.equal(context.S.shoot.guesses.length,i+1,'Repeated taps cannot add a shot');
    if(i===4){assert.equal(context.S.shoot.over,false);assert.equal(finishes.length,0,'The final result waits for playback');}
    const beforePlayback=now;drain(fps);assert.equal(run('shootUI.phase'),'result');assert(marks[i]);assert.equal($('shPuckFront').attrs.opacity,'0','The scored puck is behind the goal frame');assert.equal($('shPuckShadowFront').attrs.opacity,'0','There is no front shadow left after a goal');
    assert(now-beforePlayback<2000+1000/fps,'A full shot settles in under two seconds at every playback frame rate');
    if(i<4)$('shNext').onclick();
  }
  assert.equal(context.S.shoot.over,true);assert.equal(finishes.length,1);assert.equal(finishes[0].won,true);assert.equal(saves,5);
}
reset();choose(1);drain();assert.equal($('shPuckFront').attrs.opacity,'0','A glove catch occludes the puck');assert.equal($('shPuckShadowFront').attrs.opacity,'0');assert($('shNet').classes.has('saved'));
reset();choose(2);frame();run('shootSettle(true)');assert.equal(frames.size,0);assert.equal(context.S.shoot.guesses.length,1);assert.equal($('shNext').hidden,false,'A resumed tab offers the next shooter after quiet completion');assert.match($('shMsg').textContent,/Goal/);context.game='classic';drain();assert.equal(context.S.shoot.guesses.length,1,'Leaving cannot execute a stale guess in another mode');
reset();for(let i=0;i<4;i++){choose(2);drain();$('shNext').onclick();}choose(2);context.document.hidden=true;documentEvents.visibilitychange();assert.equal(frames.size,0);assert.equal(context.S.shoot.over,true);assert.equal(finishes.length,1);assert.equal(finishes[0].quiet,true,'A hidden tab settles without opening a result modal');
reset();reduced=true;choose(2);frame();assert.equal(frames.size,0);assert.equal(run('shootUI.phase'),'result');assert.equal(context.S.shoot.guesses.length,1);reduced=false;
reset();const wrong=new Element();wrong.dataset.c='1';$('shOpts').events.click({target:wrong});assert.equal(context.S.shoot.guesses[0],'1:-1');assert.equal(frames.size,0,'A wrong trivia answer earns no shot');
reset();const correct=new Element();correct.dataset.c='0';$('shOpts').events.click({target:correct});assert(zones.every(z=>z.attrs.tabindex==='0'));let prevented=false;$('shNet').events.keydown({target:zones[2],key:'Enter',preventDefault(){prevented=true;}});assert(prevented);drain();assert.equal(context.S.shoot.guesses[0],'0:2');assert(zones.every(z=>z.attrs.tabindex==='-1'));
for(let zone=0;zone<5;zone++){
  reset();const correct=new Element();correct.dataset.c='0';$('shOpts').events.click({target:correct});assert.equal($('shAim').hidden,false);assert(shotButtons.every(b=>!b.disabled));
  $('shAim').events.click({target:shotButtons[zone]});assert.equal(context.S.shoot.guesses[0],`0:${zone}`);assert.equal($('shAim').hidden,true);assert(shotButtons.every(b=>b.disabled));drain();
}
assert(svg.indexOf('id="shPuckBack"')<svg.indexOf('id="shPostL"')&&svg.indexOf('id="shPostL"')<svg.indexOf('id="shGoalie"'),'Pucks, posts and the advanced goalie are layered by depth');
console.log({sampledFrames:sampled,frameRates:[15,30,60,144],fullShootouts:4,contact:'glove, blocker and pads',storedShots:'immediate',cancellation:'settled',reducedMotion:'passed',keyboardTargets:'passed'});
