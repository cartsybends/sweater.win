import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('analytics/client.js','utf8');
const storage=new Map();
function make({enabled=true,blocked=false,dnt=false,online=true}={}){
  let now=0;const sent=[],intervals=new Map(),events=new Map(),windowEvents=new Map();
  const doc={visibilityState:'visible',hasFocus:()=>true,addEventListener:(n,f)=>events.set(n,f)};
  const ctx=vm.createContext({API:'https://api.sweater.win',API_ON:true,location:{hostname:'sweater.win'},navigator:{doNotTrack:dnt?'1':'0'},crypto,AbortController,
    sessionStorage:{getItem:k=>{if(blocked)throw Error('blocked');return storage.get(k)||null},setItem:(k,v)=>{if(blocked)throw Error('blocked');storage.set(k,v)}},
    performance:{now:()=>now},document:doc,matchMedia:()=>({matches:false}),innerWidth:1200,
    window:{addEventListener:(n,f)=>windowEvents.set(n,f)},setInterval:(f,t)=>intervals.set(t,f),setTimeout:()=>0,clearTimeout(){},
    fetch:async(url,opts)=>{if(!online)throw Error('offline');if(url.endsWith('/status'))return {ok:true,json:async()=>({enabled})};sent.push(JSON.parse(opts.body));return {ok:true,status:200};}
  });
  vm.runInContext(source,ctx);
  return {api:ctx.SweaterAnalytics,sent,doc,intervals,events,windowEvents,time:v=>now=v};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
storage.clear();let c=make();
c.api.context('whoscored','daily','2026-10-12:goal-01');await settle();assert.equal(c.sent.filter(e=>e.kind==='mode_open').length,1);assert.equal(c.sent.filter(e=>e.kind==='round_start').length,0);
c.api.beginRound();c.api.beginRound();c.api.completeRound(true);c.api.completeRound(true);await settle();assert.equal(c.sent.filter(e=>e.kind==='round_start').length,1);assert.equal(c.sent.filter(e=>e.kind==='round_complete').length,1);
let restored=make();restored.api.context('whoscored','daily','2026-10-12:goal-01');restored.api.beginRound();restored.api.completeRound(true);await settle();assert.equal(restored.sent.filter(e=>e.kind.startsWith('round')).length,0,'Restored finished round not counted again');
c.api.context('whoscored','unlimited','goal-01',true);c.api.beginRound();c.api.completeRound(false);c.api.context('whoscored','unlimited','goal-01',true);c.api.beginRound();c.api.completeRound(true);await settle();const starts=c.sent.filter(e=>e.kind==='round_start'&&e.variant==='unlimited');assert.equal(starts.length,2);assert.notEqual(starts[0].round,starts[1].round,'Replayed target counts as a separate round');
for(let i=1;i<=30;i++){c.time(i*1000);c.intervals.get(1000)();}c.intervals.get(30000)();await settle();assert.equal(c.sent.filter(e=>e.kind==='engagement').at(-1).active_ms,30000);
c.doc.visibilityState='hidden';c.events.get('visibilitychange')();const n=c.sent.length;c.time(200000);c.intervals.get(1000)();c.intervals.get(30000)();await settle();assert.equal(c.sent.length,n,'Hidden time excluded');
c.doc.visibilityState='visible';c.windowEvents.get('focus')();for(let i=1;i<=80;i++){c.time(200000+i*1000);c.intervals.get(1000)();}c.intervals.get(30000)();await settle();const active=c.sent.filter(e=>e.kind==='engagement').at(-1).active_ms;assert(active>=43000&&active<=45000,'Idle time excluded after45sec');
c.api.leave();const end=c.sent.length;c.time(900000);c.intervals.get(1000)();c.intervals.get(30000)();await settle();assert.equal(c.sent.length,end,'Hub navigation stops game engagement');
for(const options of [{enabled:false},{dnt:true},{online:false}]){const x=make(options);x.api.context('classic','daily','target');x.api.beginRound();await settle();assert.equal(x.sent.length,0,'Unavailable backend or privacy preference keeps collection off');}
const blocked=make({blocked:true});blocked.api.context('classic','daily','new-target');blocked.api.beginRound();await settle();assert.equal(blocked.sent.filter(e=>e.kind==='round_start').length,1,'Blocked browser storage does not break game or tracking');
for(const e of c.sent){assert(!('name' in e)&&!('guesses' in e)&&!('uid' in e)&&!('secret' in e));assert(!JSON.stringify(e).includes('goal-01'),'Scorer/target details not sent');}
// Build integration replaces the inline marker without requiring any network data.
const builder=fs.readFileSync('build_sweater.py','utf8'),template=builder.split("TEMPLATE = r'''")[1]?.split("'''\n")[0]||builder.split("TEMPLATE = '''")[1]?.split("'''\n")[0];
assert(builder.includes('/*__MODE_ANALYTICS__*/')&&builder.includes('analyticsNew = false'));
console.log('Analytics client: distinct visits/rounds, Daily restore, Unlimited replay, foreground/idle time, disabled backend, privacy preferences and blocked storage passed.');
