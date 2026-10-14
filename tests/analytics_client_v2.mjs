import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync('analytics/client.js','utf8');
const settle=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function make({diagnostics=0,online=true,local=new Map(),session=new Map(),blocked=false,dnt=false,gpc=false,enabled=true,failures=0,url='https://sweater.win/',referrer='',coarse=false,width=1200,ua='Mozilla/5.0 Chrome/130.0 Windows NT 10.0',nav={loadEventEnd:1000,responseStart:120},observerTypes=['largest-contentful-paint','layout-shift']}={}){
  let now=0;const sent=[],calls=[],intervals=new Map(),timers=[],events=new Map(),windowEvents=new Map(),observers=new Map();
  const storage=map=>({getItem:k=>{if(blocked)throw Error('blocked');return map.get(k)||null;},setItem:(k,v)=>{if(blocked)throw Error('blocked');map.set(k,v);},removeItem:k=>{if(blocked)throw Error('blocked');map.delete(k);}});
  const doc={visibilityState:'visible',hasFocus:()=>true,referrer:'https://sweater.win/',documentElement:{dataset:{theme:'dark'}},addEventListener:(n,f)=>events.set(n,f)};
  const root={location:new URL(url),document:{referrer}},location=new URL('https://sweater.win/app.html'),window={location,parent:root,addEventListener:(n,f)=>windowEvents.set(n,f)};
  class Observer{constructor(fn){this.fn=fn;}observe({type}){observers.set(type,this.fn);}}
  Observer.supportedEntryTypes=observerTypes;
  const context=vm.createContext({API:'https://api.sweater.win',API_ON:true,BUILT:'2026-10-13 (builder v138)',SITE_RELEASE:'0123456789ab',G:{shoot:{},whoscored:{},classic:{}},location,window,document:doc,
    navigator:{onLine:online,doNotTrack:dnt?'1':'0',globalPrivacyControl:gpc,userAgent:ua,maxTouchPoints:coarse?5:0},crypto,AbortController,URL,Date,PerformanceObserver:Observer,
    localStorage:storage(local),sessionStorage:storage(session),performance:{now:()=>now,getEntriesByType:()=>nav?[nav]:[]},matchMedia:()=>({matches:coarse}),innerWidth:width,
    setInterval:(f,t)=>intervals.set(t,f),setTimeout:(f,t)=>{timers.push({f,t});return timers.length;},clearTimeout(){},
    fetch:async(url,opts)=>{calls.push({url,opts});if(url.endsWith('/status'))return {ok:true,json:async()=>({enabled,version:2,diagnostics})};const body=JSON.parse(opts.body);sent.push(body);if(failures-->0)throw Error('offline');return {ok:true,status:200};}
  });
  vm.runInContext(source,context);
  return {api:context.SweaterAnalytics,sent,calls,doc,window,events,windowEvents,intervals,timers,observers,local,session,time:n=>now=n,all:()=>sent.flatMap(b=>b.events),emit:(type,entries)=>observers.get(type)?.({getEntries:()=>entries})};
}

const local=new Map(),session=new Map(),c=make({local,session,url:'https://sweater.win/?utm_source=instagram&utm_medium=social&utm_campaign=hockey-launch&email=private@example.com#whoscored',referrer:'https://www.google.ca/search?q=private-name'});
const token=c.api.context('whoscored','daily','private-scorer-123');await settle();
assert.equal(c.all().filter(e=>e.kind==='site_visit').length,1);assert.equal(c.all()[0].mode,'whoscored','Landing attribution reads the outer bootstrap URL');assert.equal(c.all().filter(e=>e.kind==='round_start').length,0,'Reading a game does not invent a started round');
for(let i=1;i<=4;i++){c.time(i*1000);c.intervals.get(1000)();}
c.api.step(1,false,token);c.api.step(1,true,token);c.api.step(0,true,token);
for(let i=5;i<=6;i++){c.time(i*1000);c.intervals.get(1000)();}
c.api.step(2,true,token);c.api.completeRound(true,{attempts:2,score:5,token});c.api.completeRound(true,{token});await settle();
const steps=c.all().filter(e=>e.kind==='round_step'),complete=c.all().filter(e=>e.kind==='round_complete');assert.equal(steps.length,2);assert.equal(steps[0].response_ms,4000);assert.equal(steps[1].response_ms,2000);assert.equal(complete.length,1);assert.equal(complete[0].elapsed_ms,6000);assert.equal(complete[0].step,2);assert.equal(complete[0].score,5);
c.api.hub();c.api.interaction('favorite_add',{mode:'shoot'});c.api.team('CGY');await settle();
assert.equal(c.all().find(e=>e.action==='favorite_add').mode,'hub','Favouriting a game does not claim it was visited');assert.equal(c.all().find(e=>e.action==='favorite_add').from_mode,'shoot');assert(c.all().some(e=>e.kind==='page_view'&&e.from_mode==='whoscored'));
const restored=make({local,session});restored.api.context('whoscored','daily','private-scorer-123');restored.api.step(3,true);restored.api.completeRound(true);await settle();assert(!restored.all().some(e=>e.kind.startsWith('round')),'Finished Daily rounds remain deduplicated after reload');
assert.equal(restored.all()[0].visitor,c.all()[0].visitor);assert.equal(restored.all()[0].session,c.all()[0].session);assert.notEqual(restored.all()[0].visit,c.all()[0].visit,'Reload is a new visit within the same browser session');
const otherTab=make({local});await settle();assert.equal(otherTab.all()[0].visitor,c.all()[0].visitor);assert.notEqual(otherTab.all()[0].session,c.all()[0].session,'Returning recognition survives a new tab session');
const unfinished=c.api.context('shoot','unlimited','private-target',true);c.api.step(1,false,unfinished);c.api.leave();c.api.leave();c.api.context('shoot','unlimited','private-target');c.api.leave();await settle();
const exits=c.all().filter(e=>e.kind==='round_exit');assert.equal(exits.length,2);assert.equal(exits[0].id,exits[1].id,'Leaving a resumed unfinished round retries the same first-exit event');assert.equal(exits[0].step,1);
const current=c.api.context('classic','unlimited','next',true),before=c.all().length;c.api.step(1,true,unfinished);c.api.completeRound(true,{token:unfinished});await settle();assert.equal(c.all().length,before+1,'A stale Teams callback cannot start or finish the newly opened round');c.api.step(1,true,current);await settle();assert(c.all().some(e=>e.kind==='round_start'&&e.mode==='classic'));

c.emit('largest-contentful-paint',[{startTime:1750}]);c.emit('layout-shift',[{startTime:100,value:.1,hadRecentInput:false},{startTime:500,value:.2,hadRecentInput:false},{startTime:700,value:2,hadRecentInput:true},{startTime:2200,value:.05,hadRecentInput:false}]);
c.windowEvents.get('load')();c.timers.filter(t=>t.t===5000).at(-1).f();c.doc.visibilityState='hidden';c.events.get('visibilitychange')();
for(let i=0;i<12;i++)c.windowEvents.get('error')({target:c.window,message:'private-name / private-url / password'});c.windowEvents.get('pagehide')();await settle();
const perf=c.all().filter(e=>e.kind==='performance');assert.equal(perf.length,1);assert.equal(perf[0].load_ms,1000);assert.equal(perf[0].ttfb_ms,120);assert.equal(perf[0].lcp_ms,1750);assert(Math.abs(perf[0].cls-.3)<1e-10,'CLS uses the largest shift window and excludes input shifts');assert.equal(c.all().filter(e=>e.kind==='error').length,10);assert(c.all().some(e=>e.kind==='page_exit'));
const unsupported=make({observerTypes:[]});unsupported.windowEvents.get('load')();unsupported.timers.filter(t=>t.t===5000).at(-1).f();await settle();const partial=unsupported.all().find(e=>e.kind==='performance');assert.equal(partial.ttfb_ms,120);assert(!('lcp_ms' in partial));assert(!('cls' in partial),'Unsupported measurements are absent rather than fabricated zeroes');assert.equal(unsupported.observers.size,0);
const shiftOnly=make({observerTypes:['layout-shift']});shiftOnly.emit('layout-shift',[{startTime:100,value:.05,hadRecentInput:false}]);shiftOnly.windowEvents.get('load')();shiftOnly.timers.filter(t=>t.t===5000).at(-1).f();await settle();assert.equal(shiftOnly.all().find(e=>e.kind==='performance').cls,.05,'Supported metrics remain available independently');
for(const b of c.sent)assert(b.events.length>=1&&b.events.length<=5);for(const e of c.all()){assert.equal(e.version,2);assert.equal(e.source,'instagram');assert.equal(e.campaign,'hockey-launch');assert.equal(e.build,'138');assert(!JSON.stringify(e).includes('private'));assert(!('name' in e)&&!('message' in e)&&!('referrer' in e)&&!('url' in e));}
for(const {url,opts}of c.calls.filter(r=>r.url.endsWith('/collect'))){assert.equal(opts.credentials,'omit');assert.equal(opts.keepalive,true);}
// Real error-event shapes supply useful locations without leaking messages, input or full URLs.
const diagnostic=make({diagnostics:1,online:false});
diagnostic.api.context('whoscored','daily','private-target');
diagnostic.windowEvents.get('error')({target:diagnostic.window,error:new TypeError('private-input'),filename:'https://sweater.win/app.html?email=private@example.com#private-target',lineno:4500,colno:17});
diagnostic.windowEvents.get('unhandledrejection')({reason:{name:'ReferenceError',message:'private-name',stack:'ReferenceError: private-name\n    at privateFunction (https://sweater.win/app.html?token=private-secret:4600:22)\n    at https://extension.example/private-path:1:2'}});
diagnostic.windowEvents.get('error')({target:{tagName:'VIDEO',currentSrc:'https://sweater.win/who-scored/goal-79-masked-v2.mp4?token=private-secret',error:{code:3}}});
diagnostic.windowEvents.get('error')({target:{tagName:'IMG',src:'https://assets.nhle.com/mugs/nhl/20252026/CGY/8476399.png?private=secret'}});
diagnostic.windowEvents.get('error')({target:diagnostic.window,error:{name:'private-name'},filename:'https://extension.example/private-user.js',lineno:100,colno:7});
await settle();
const errors=diagnostic.all().filter(e=>e.kind==='error');assert.equal(errors.length,5);
assert.equal(errors[0].error_type,'TypeError');assert.equal(errors[0].error_file,'app.html');assert.equal(errors[0].error_line,4500);assert.equal(errors[0].error_column,17);assert.equal(errors[0].release,'0123456789ab');assert.equal(errors[0].online,false);
assert.equal(errors[1].error_type,'ReferenceError');assert.equal(errors[1].error_line,4600);assert.equal(errors[1].error_column,22);
assert.equal(errors[2].resource,'goal_video');assert.equal(errors[2].asset,'goal-79-masked-v2.mp4');assert.equal(errors[2].error_type,'MediaDecodeError');
assert.equal(errors[3].resource,'headshot');assert(!('asset' in errors[3]));assert.equal(errors[4].error_file,'external');assert.equal(errors[4].error_type,'unknown');assert(!('error_line' in errors[4]));
for(const privateText of ['private','https://','8476399','privateFunction','secret'])assert(!JSON.stringify(errors).includes(privateText));
assert(!diagnostic.all().filter(e=>e.kind!=='error').some(e=>'release' in e));
// Unsupported collectors receive the original payload so a staged frontend rollout cannot drop batches.
const older=make();older.windowEvents.get('error')({target:older.window,error:new TypeError('private'),filename:'https://sweater.win/app.html',lineno:10,colno:2});await settle();
for(const field of ['release','error_type','error_file','error_line','error_column','resource','asset','online'])assert(!(field in older.all().find(e=>e.kind==='error')));
assert(older.all().some(e=>e.kind==='site_visit'));
const webkit=make({diagnostics:1});webkit.windowEvents.get('unhandledrejection')({reason:{name:'TypeError',stack:'privateFunction@https://sweater.win/app.html?private=secret:4500:17'}});await settle();
assert.equal(webkit.all().find(e=>e.kind==='error').error_line,4500);assert.equal(webkit.all().find(e=>e.kind==='error').error_column,17);assert(!JSON.stringify(webkit.all()).includes('private'));
const filenameMissing=make({diagnostics:1});filenameMissing.windowEvents.get('error')({target:filenameMissing.window,error:{name:'TypeError',stack:'TypeError: private message\n    at https://sweater.win/app.html:4501:18'}});await settle();
assert.equal(filenameMissing.all().find(e=>e.kind==='error').error_line,4501);

for(const options of [{dnt:true},{gpc:true},{enabled:false},{url:'https://sweater.win/?analytics=off'}]){const x=make(options);x.api.context('classic','daily','target');x.api.step(1,true);await settle();assert.equal(x.sent.length,0);if(options.dnt||options.gpc||options.url)assert.equal(x.calls.length,0,'Opted-out browsers make no analytics requests');}
const excluded=new Map();make({local:excluded,url:'https://sweater.win/?analytics=off'});const x=make({local:excluded});x.api.hub();await settle();assert.equal(x.calls.length,0);const included=make({local:excluded,url:'https://sweater.win/?analytics=on'});await settle();assert.equal(included.all().length,1,'The owner can re-enable collection in that browser');
const blocked=make({blocked:true});blocked.api.context('classic','daily','new');blocked.api.step(1,true);await settle();assert.equal(blocked.all().filter(e=>e.kind==='round_start').length,1,'Storage denial leaves gameplay and ephemeral tracking usable');
const phone=make({coarse:true,width:390,ua:'Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 Safari/605.1.15 DuckDuckGo/7'});await settle();assert.equal(phone.all()[0].browser,'duckduckgo');assert.equal(phone.all()[0].os,'ios');assert.equal(phone.all()[0].device,'mobile');
for(const [referrer,expected]of [['https://www.google.co.uk/search?q=secret','google'],['https://instagram.com.evil.example/path','referral'],['https://google.com.evil.example/path','referral']]){const r=make({referrer});await settle();assert.equal(r.all()[0].source,expected);}
const unsafe=make({url:'https://sweater.win/?utm_campaign=private%40example.com&utm_medium=two%20words#party-secret-code'});await settle();assert.equal(unsafe.all()[0].mode,'party');assert(!('campaign' in unsafe.all()[0]));assert(!('medium' in unsafe.all()[0]));assert(!JSON.stringify(unsafe.all()).includes('secret-code'));
const retry=make({failures:1});retry.api.hub();await settle();const first=retry.sent[0];assert.equal(retry.sent.length,1);retry.timers.find(t=>t.t===3000).f();await settle();assert.deepEqual(retry.sent[1],first,'Network retries preserve event IDs for server deduplication');
console.log('Enhanced analytics client: anonymous visitors, parent-link attribution, five-event batching/retries, owner opt-out, privacy preferences, progress timing, stale callbacks, restored rounds, performance windows and diagnostic limits passed.');
