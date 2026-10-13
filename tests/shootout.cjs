// Analytic contact, frame-rate independence, stored shots and canceled playback.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('build_sweater.py','utf8');
const animation=fs.readFileSync('static/shootout/animation.js','utf8');
const svg=fs.readFileSync('static/shootout/scene.svg','utf8');
const elements=new Map(),frames=new Map(),documentEvents={},windowEvents={};
let nextFrame=0,now=0,reduced=false,saves=0,finishes=[],marks=[];
class Element{
  constructor(){this.attrs={};this.events={};this.dataset={};this.hidden=false;this.classes=new Set();this.classList={add:(...x)=>x.forEach(c=>this.classes.add(c)),remove:(...x)=>x.forEach(c=>this.classes.delete(c)),toggle:(c,v)=>{if(v===undefined)v=!this.classes.has(c);v?this.classes.add(c):this.classes.delete(c);},contains:c=>this.classes.has(c)};}
  setAttribute(k,v){this.attrs[k]=String(v);}
  addEventListener(k,fn){this.events[k]=fn;}
  querySelectorAll(selector){return selector==='.zone'?zones:[];}
  closest(selector){return selector==='[data-z]'&&this.dataset.z!==undefined||selector==='[data-c]'&&this.dataset.c!==undefined?this:null;}
}
const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
for(const match of svg.matchAll(/id="([^"]+)"/g))$(match[1]);
const zones=Array.from({length:5},(_,i)=>{const el=new Element();el.dataset.z=String(i);return el;});
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
function drain(fps=60){for(let i=0;frames.size&&i<400;i++)frame(1000/fps);assert.equal(frames.size,0);}
function choose(zone){const el=new Element();el.dataset.c='0';$('shOpts').events.click({target:el});$('shNet').events.click({target:zones[zone]});}

let sampled=0;
for(let a=0;a<5;a++)for(let b=a+1;b<5;b++)for(let zone=0;zone<5;zone++)for(const seed of [1,5]){
  const plan=run(`shootPlan(${zone},[${a},${b}],${seed})`);
  assert.equal(plan.save,[a,b].includes(zone));
  if(plan.post)assert(Math.abs(Math.abs(plan.point[0]-(zone%2?506:134))-(6+14.5*.53))<1e-9,'Post contact respects the radii of the tube and puck');
  const before=run(`shootFrame(shootPlan(${zone},[${a},${b}],${seed}),${plan.contactAt-1e-6})`);
  const contact=run(`shootFrame(shootPlan(${zone},[${a},${b}],${seed}),${plan.contactAt})`);
  if(plan.save){assert(Math.hypot(before.puck.x-contact.puck.x,before.puck.y-contact.puck.y)<.01,'A save cannot teleport the puck');assert(Math.abs(before.puck.scale-contact.puck.scale)<.001);}
  for(let i=0;i<=150;i++){
    const f=run(`shootFrame(shootPlan(${zone},[${a},${b}],${seed}),${i/100})`);
    assert(Number.isFinite(f.puck.x)&&Number.isFinite(f.puck.y)&&Number.isFinite(f.pose.x));assert(f.puck.x>=40&&f.puck.x<=600);assert(f.puck.y>=50&&f.puck.y<=440);
    if(plan.save){assert.equal(f.scored,false);assert.equal(f.netImpact,null);assert.equal(f.puck.layer,'front');}
    if(f.scored)assert(f.t>plan.planeAt,'The goal light waits for the puck to cross the line');
    if(f.netImpact)assert(f.t>=plan.netAt,'Net motion starts only after contact');
    sampled++;
  }
  const final=run(`shootFrame(shootPlan(${zone},[${a},${b}],${seed}),1.5)`);
  if(!plan.save){assert.equal(final.puck.layer,'back');assert(final.puck.x>174&&final.puck.x<466);assert.equal(final.puck.y,255);assert(Math.abs(final.puck.rotation)<1e-9,'A goal settles flat on the ice inside the net');}
  if(zone===1&&plan.save){assert.equal(final.puck.opacity,0);assert.equal(final.pose.gloveClose,1,'The catching glove stays closed around the puck');}
}
// Hands remain on their correct sides; neither save swaps the catching glove and blocker.
for(const zone of [0,1]){const f=run(`shootFrame(shootPlan(${zone},[0,1],1),.592)`);const hand=zone===0?f.pose.blocker:f.pose.glove;assert(Math.hypot(320+f.pose.x+hand[0]-f.puck.x,hand[1]-f.puck.y)<.01);}
// Low-shot contact must intersect an actual projected pad, not an empty point in space.
for(const zone of [2,3,4]){
  const f=run(`shootFrame(shootPlan(${zone},[${zone},${zone===4?0:4}],1),.592)`);let intersects=false;
  for(const side of ['L','R']){const knee=f.pose['knee'+side],angle=-f.pose['pad'+side]*Math.PI/180,x=f.puck.x-320-f.pose.x-knee[0],y=f.puck.y-knee[1],px=x*Math.cos(angle)-y*Math.sin(angle),py=x*Math.sin(angle)+y*Math.cos(angle);const dx=Math.max(-25-px,0,px-25),dy=Math.max(-9-py,0,py-109);if(Math.hypot(dx,dy)<8)intersects=true;}
  assert(intersects,'Low save '+zone+' contacts the pad surface');
}
assert.equal(run('shootMeshPath("h",9,null)'),run('shootMeshPath("h",9,{point:[320,160],time:0})'));
assert.notEqual(run('shootMeshPath("h",9,null)'),run('shootMeshPath("h",9,{point:[320,160],time:.08})'));
assert.deepEqual([...run('shootMeshPoint([174,162],{point:[320,160],time:.08})')],[174,162],'Mesh ties remain attached to the frame');

for(const fps of [15,30,60,144]){
  reset();for(let i=0;i<5;i++){
    choose(2);assert.equal(context.S.shoot.guesses.length,i+1,'The accepted shot is stored immediately');assert.equal(run('shootUI.phase'),'shot');assert.equal($('shNext').hidden,true);assert.equal(marks[i],null,'The outcome marker waits for the shot');
    $('shNet').events.click({target:zones[3]});assert.equal(context.S.shoot.guesses.length,i+1,'Repeated taps cannot add a shot');
    if(i===4){assert.equal(context.S.shoot.over,false);assert.equal(finishes.length,0,'The final result waits for playback');}
    drain(fps);assert.equal(run('shootUI.phase'),'result');assert(marks[i]);assert.equal($('shPuckFront').attrs.opacity,'0','The scored puck is behind the goal frame');assert.equal($('shPuckShadowFront').attrs.opacity,'0','There is no front shadow left after a goal');
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
assert(svg.indexOf('id="shPuckBack"')<svg.indexOf('id="shPostL"')&&svg.indexOf('id="shPostL"')<svg.indexOf('id="shGoalie"'),'Pucks, posts and the advanced goalie are layered by depth');
console.log({sampledFrames:sampled,frameRates:[15,30,60,144],fullShootouts:4,contact:'glove, blocker and pads',storedShots:'immediate',cancellation:'settled',reducedMotion:'passed',keyboardTargets:'passed'});
