import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import worker from '../backend/src/index.mjs';
import {purgeAnalytics} from '../backend/src/analytics.mjs';
import {dashboard,loginPage} from '../backend/src/dashboard.mjs';
import vm from 'node:vm';
class DB {
  constructor(){this.sql=new DatabaseSync(':memory:');this.queries=0;}
  prepare(query){const db=this;return {bind(...values){return db.statement(query,values)},...this.statement(query,[])};}
  statement(query,values){const db=this;const execute=all=>{db.queries++;let sql=query,args=values;if(/\?\d/.test(sql)){args=[];sql=sql.replace(/\?(\d+)/g,(_,n)=>{args.push(values[Number(n)-1]);return '?';});}const s=db.sql.prepare(sql);if(all||/^\s*(SELECT|WITH)/i.test(sql))return {results:s.all(...args),meta:{changes:0},success:true};const r=s.run(...args);return {results:[],meta:{changes:Number(r.changes)},success:true};};return {run:async()=>execute(false),all:async()=>execute(true),first:async()=>execute(true).results[0]||null,execute};}
  async batch(statements){this.sql.exec('BEGIN');try{const out=statements.map(s=>s.execute(false));this.sql.exec('COMMIT');return out;}catch(e){this.sql.exec('ROLLBACK');throw e;}}
}
const env={DB:new DB(),ALLOWED_ORIGINS:'https://sweater.win',SWEATER_ANALYTICS_PASSWORD:'owner-password-for-testing-only-000000000000'};
const req=(path,body,opts={})=>new Request('https://api.sweater.win'+path,{method:body===undefined?'GET':'POST',headers:{Origin:opts.origin||'https://sweater.win','CF-Connecting-IP':opts.ip||'203.0.113.1',...(opts.cookie?{Cookie:opts.cookie}:{}),...(opts.accept?{Accept:opts.accept}:{}),'Content-Type':'application/json'},...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});
const call=(path,body,opts)=>worker.fetch(req(path,body,opts),env,{});
const session=crypto.randomUUID(),round=crypto.randomUUID();
const event=(kind,more={})=>({id:crypto.randomUUID(),session,mode:'whoscored',variant:'unlimited',kind,device:'desktop',...(kind.startsWith('round')?{round}:{}),...more});
let r=await worker.fetch(req('/api/analytics/status'),{DB:env.DB},{});assert.deepEqual(await r.json(),{enabled:false});
r=await call('/api/analytics/report');assert.equal(r.status,401);assert.equal(env.DB.queries,0,'No data query before authentication');
r=await call('/analytics');assert.equal(r.status,303);assert.equal(r.headers.get('Location'),'/analytics/login');
r=await call('/api/analytics/status');assert.deepEqual(await r.json(),{enabled:true,version:2,diagnostics:1,retention_days:365});
const opened=event('mode_open');assert.equal((await call('/api/analytics/collect',opened)).status,200);assert.equal((await call('/api/analytics/collect',opened)).status,200);
assert.equal((await call('/api/analytics/collect',event('round_start'))).status,200);assert.equal((await call('/api/analytics/collect',event('round_start'))).status,200);
assert.equal((await call('/api/analytics/collect',event('engagement',{active_ms:12000}))).status,200);
assert.equal((await call('/api/analytics/collect',event('round_complete',{won:true}))).status,200);
assert.equal((await call('/api/analytics/collect',event('round_complete',{won:true}))).status,200);
assert.equal(env.DB.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n,4,'Events and round retries deduplicate');
assert.notEqual(env.DB.sql.prepare('SELECT session_hash FROM sweater_analytics_events LIMIT 1').get().session_hash,session,'Raw browser ID not stored');
for(const invalid of [event('mode_open',{mode:'not-a-mode'}),event('engagement',{active_ms:60001}),event('mode_open',{id:[crypto.randomUUID()]}),event('mode_open',{name:'private-name'}),event('round_complete',{won:'yes'})])assert.equal((await call('/api/analytics/collect',invalid)).status,400);
assert.equal((await call('/api/analytics/collect',event('mode_open'),{origin:'https://elsewhere.example'})).status,403);
assert.equal((await call('/api/analytics/collect','x'.repeat(8200))).status,413);
r=await call('/analytics/login');assert.equal(r.status,200);
assert.equal(r.headers.get('Referrer-Policy'),'same-origin','Native login form POSTs must preserve their same-origin Origin header');
assert.equal((await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:'https://elsewhere.example'})).status,403);
assert.equal((await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:'null'})).status,403,'Opaque origins still cannot sign in');
const authOrigin='https://api.sweater.win';
r=await call('/analytics/login','password=wrong',{origin:authOrigin});assert.equal(r.status,401);
r=await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:authOrigin});assert.equal(r.status,303);
const cookie=r.headers.get('Set-Cookie');assert(cookie.includes('Secure')&&cookie.includes('HttpOnly')&&cookie.includes('SameSite=Strict'));const sessionCookie=cookie.split(';')[0];
assert.equal((await call('/api/analytics/session')).status,401,'Session checks cannot succeed without the sign-in cookie');
r=await call('/analytics/login','password=wrong',{origin:authOrigin,accept:'application/json'});assert.equal(r.status,401);assert.deepEqual(await r.json(),{error:'That password did not match.'});
r=await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:authOrigin,accept:'application/json'});assert.equal(r.status,200);assert.deepEqual(await r.json(),{ok:true});assert.equal(r.headers.get('Location'),null,'Mobile fetch login has no navigation redirect');
const fetchCookie=r.headers.get('Set-Cookie');assert(fetchCookie.includes('Secure')&&fetchCookie.includes('HttpOnly')&&fetchCookie.includes('SameSite=Strict'));
r=await call('/api/analytics/session',undefined,{cookie:fetchCookie.split(';')[0]});assert.equal(r.status,200);assert.deepEqual(await r.json(),{authenticated:true});assert(r.headers.get('Cache-Control').includes('no-store'));
assert.equal((await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:'https://elsewhere.example',accept:'application/json'})).status,403,'Fetch login retains origin protection');
r=await call('/api/analytics/report?days=7',undefined,{cookie:sessionCookie});assert.equal(r.status,200);const report=await r.json();assert.equal(report.sessions,1);assert.equal(report.modes[0].opens,1);assert.equal(report.modes[0].starts,1);assert.equal(report.modes[0].finishes,1);assert.equal(report.modes[0].completed_starts,1);assert.equal(report.modes[0].active_ms,12000);
r=await call('/api/analytics/report?days=7&variant=daily',undefined,{cookie:sessionCookie});assert.deepEqual((await r.json()).modes,[]);
r=await call('/api/analytics/report?days=30&variant=unlimited',undefined,{cookie:sessionCookie});assert.equal((await r.json()).modes[0].opens,1);
assert.equal((await call('/api/analytics/report?days=999',undefined,{cookie:sessionCookie})).status,400);
assert.equal((await call('/api/analytics/report',undefined,{cookie:sessionCookie.slice(0,-1)+'x'})).status,401);
r=await call('/analytics',undefined,{cookie:sessionCookie});assert.equal(r.status,200);assert(r.headers.get('Content-Security-Policy').includes("default-src 'none'"));assert(r.headers.get('Cache-Control').includes('no-store'));assert(!(await r.text()).includes(env.SWEATER_ANALYTICS_PASSWORD));
assert.equal(r.headers.get('Referrer-Policy'),'same-origin','The native sign-out form must also preserve its origin');
assert.equal((await call('/analytics/logout','',{origin:'https://elsewhere.example',cookie:sessionCookie})).status,403);
assert.equal((await call('/analytics/logout','',{origin:'null',cookie:sessionCookie})).status,403);
r=await call('/analytics/logout','',{origin:authOrigin,cookie:sessionCookie});assert.equal(r.status,303);assert(r.headers.get('Set-Cookie').includes('Max-Age=0'));
for(let i=0;i<10;i++)assert.equal((await call('/analytics/login','password=wrong',{origin:authOrigin,ip:'203.0.113.2'})).status,401);
assert.equal((await call('/analytics/login','password=wrong',{origin:authOrigin,ip:'203.0.113.2'})).status,429);
// Completion cohorts don't count a finish whose start was outside the selected window.
const row=env.DB.sql.prepare('SELECT * FROM sweater_analytics_events LIMIT 1').get();
env.DB.sql.prepare('INSERT INTO sweater_analytics_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)').run(crypto.randomUUID(),Date.now()-86400000,'2000-01-01',10,'whoscored','unlimited','round_start',row.session_hash,'previous-round','desktop',0,null);
env.DB.sql.prepare('INSERT INTO sweater_analytics_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)').run(crypto.randomUUID(),Date.now(),row.day,10,'whoscored','unlimited','round_complete',row.session_hash,'previous-round','desktop',0,1);
r=await call('/api/analytics/report?days=1',undefined,{cookie:sessionCookie});const cohort=(await r.json()).modes[0];assert.equal(cohort.finishes,2);assert.equal(cohort.completed_starts,1);
env.DB.sql.prepare('UPDATE sweater_analytics_events SET received_at=? WHERE day=?').run(Date.now()-366*86400000,'2000-01-01');await purgeAnalytics(env);assert.equal(env.DB.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events WHERE day=?').get('2000-01-01').n,0);
r=await call('/api/health');assert.equal(r.status,200);assert.equal((await r.json()).ok,true,'Existing health handler preserved');
r=await call('/api/leaderboard?game=unsupported');assert.equal(r.status,400,'Existing endpoint behavior preserved');
new vm.Script(dashboard.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1]);
new vm.Script(loginPage('').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1]);
for(const mode of ['grid','benchboss','teammatetrail'])assert.equal((await call('/api/analytics/collect',event('mode_open',{mode}))).status,200,'New game events are accepted');
r=await call('/api/analytics/report?days=1',undefined,{cookie:sessionCookie});const newModes=(await r.json()).modes;
for(const [id,label] of [['grid','Sweater Grid'],['benchboss','Bench Boss'],['teammatetrail','Teammate Trail']])assert(newModes.some(m=>m.mode===id&&m.label===label),'New game has its own analytics label');
console.log('Analytics backend: real SQLite queries, protected reports, login, tamper rejection, CSRF/origin checks, deduplication, ranges/cohorts, rate limits, retention, existing API routing and dashboard JS passed.');
