import assert from 'node:assert/strict';
import worker from '../backend/src/index.mjs';
import {purgeAnalytics} from '../backend/src/analytics.mjs';
import {AnalyticsDB} from './helpers/analytics_runtime.mjs';
const db=new AnalyticsDB(),env={DB:db,ALLOWED_ORIGINS:'https://sweater.win',SWEATER_ANALYTICS_PASSWORD:'test-only-insights-password-000000000000000'};
const actualNow=Date.now,fixed=Date.parse('2026-10-13T19:00:00Z');let now=fixed;
Date.now=()=>now;
const uuid=()=>crypto.randomUUID(),a={visitor:uuid(),session:uuid(),visit:uuid()},b={visitor:uuid(),session:uuid(),visit:uuid()},c={visitor:uuid(),session:uuid(),visit:uuid()},roundA=uuid(),roundC=uuid();
function event(actor,kind,extra={}){return {version:2,id:uuid(),...actor,mode:'hub',variant:'hub',kind,device:'desktop',browser:'chrome',os:'windows',source:'instagram',campaign:'hockey-launch',medium:'social',theme:'dark',viewport:'wide',build:'138',...extra};}
function request(path,body,options={}){const req=new Request('https://api.sweater.win'+path,{method:body===undefined?'GET':'POST',headers:{Origin:options.origin||'https://sweater.win','CF-Connecting-IP':options.ip||'203.0.113.20','Content-Type':'application/json','User-Agent':'Mozilla/5.0 Chrome/130.0 Windows NT 10.0',...(options.cookie?{Cookie:options.cookie}:{})},...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});Object.defineProperty(req,'cf',{value:{country:options.country||'CA'}});return req;}
async function call(path,body,options={}){const before=db.queries,r=await worker.fetch(request(path,body,options),env,{});assert(db.queries-before<=50,'Every request stays within the free-plan D1 statement budget, even when cold');return r;}
async function collect(events,options){const r=await call('/api/analytics/collect',{events},options);assert.equal(r.status,200,await r.clone().text());}
let cookie;
async function report(query='days=30'){const r=await call('/api/analytics/report?'+query,undefined,{cookie});assert.equal(r.status,200,await r.clone().text());return r.json();}
try{
  now=fixed-10*86400000;
  const first=[event(a,'site_visit'),event(a,'page_view'),event(a,'mode_open',{mode:'whoscored',variant:'daily',from_mode:'hub'}),event(a,'round_start',{mode:'whoscored',variant:'daily',round:roundA}),event(a,'round_step',{mode:'whoscored',variant:'daily',round:roundA,step:1,correct:true,response_ms:4000})];
  await collect(first);await collect(first);
  assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n,5,'A retried batch does not duplicate events or visitor/visit records');
  await collect([event(a,'engagement',{mode:'whoscored',variant:'daily',round:roundA,active_ms:15000}),event(a,'round_complete',{mode:'whoscored',variant:'daily',round:roundA,won:true,step:2,elapsed_ms:18000,score:2}),event(a,'share',{mode:'whoscored',variant:'daily'}),event(a,'performance',{mode:'whoscored',variant:'daily',load_ms:1000,ttfb_ms:120,lcp_ms:1800,cls:.04}),event(a,'error',{mode:'whoscored',variant:'daily',action:'javascript'})]);
  await collect([event(b,'site_visit',{source:'google',device:'mobile',browser:'duckduckgo',os:'ios'}),event(b,'page_view',{source:'google',device:'mobile',browser:'duckduckgo',os:'ios'}),event(b,'performance',{source:'google',device:'mobile',browser:'duckduckgo',os:'ios',lcp_ms:7000,cls:.4}),event(b,'page_exit',{source:'google',device:'mobile',browser:'duckduckgo',os:'ios'})],{country:'US'});
  now=fixed-9*86400000;
  a.session=uuid();a.visit=uuid();await collect([event(a,'site_visit',{source:'direct'}),event(a,'page_view',{source:'direct'})]);
  now=fixed-3*86400000;
  a.session=uuid();a.visit=uuid();await collect([event(a,'site_visit',{source:'google'}),event(a,'page_view',{source:'google'})]);
  now=fixed;
  await collect([event(c,'site_visit',{source:'direct',browser:'firefox',os:'linux'}),event(c,'mode_open',{mode:'shoot',variant:'unlimited',source:'direct',browser:'firefox',os:'linux',from_mode:'hub'}),event(c,'round_start',{mode:'shoot',variant:'unlimited',round:roundC,source:'direct',browser:'firefox',os:'linux'}),event(c,'round_step',{mode:'shoot',variant:'unlimited',round:roundC,step:1,correct:false,response_ms:3000,source:'direct',browser:'firefox',os:'linux'}),event(c,'round_exit',{mode:'shoot',variant:'unlimited',round:roundC,step:1,elapsed_ms:5000,source:'direct',browser:'firefox',os:'linux'})],{country:'DE'});
  await collect([event(c,'page_view',{source:'direct',browser:'firefox',os:'linux',from_mode:'shoot'}),event(c,'interaction',{action:'team_select',team:'CGY',source:'direct'}),event(c,'interaction',{action:'favorite_add',source:'direct'})],{country:'DE'});
  const legacy={id:uuid(),session:uuid(),mode:'classic',variant:'daily',kind:'mode_open',device:'desktop'};
  assert.equal((await call('/api/analytics/collect',legacy,{country:'AU'})).status,200,'Already-open older clients remain supported');
  const auth=await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD),{origin:'https://api.sweater.win'});assert.equal(auth.status,303);cookie=auth.headers.get('Set-Cookie').split(';')[0];
  const d=await report();assert.equal(d.version,2);assert.equal(d.summary.visitors,3);assert.equal(d.summary.sessions,6);assert.equal(d.summary.visits,5);assert.equal(d.summary.page_loads,5);assert.equal(d.summary.starts,2);assert.equal(d.summary.finishes,1);assert.equal(d.summary.wins,1);assert.equal(d.summary.shares,1);assert.equal(d.summary.active_ms,15000);
  assert.equal(d.audience.repeat_visitors,1);assert.equal(d.audience.new_visitors,3);assert.equal(d.retention.day1_eligible,2);assert.equal(d.retention.day1_returned,1);assert.equal(d.retention.day7_eligible,2);assert.equal(d.retention.day7_returned,1);assert.equal(d.retention.day7_rate,50);
  const who=d.modes.find(r=>r.mode==='whoscored'),shoot=d.modes.find(r=>r.mode==='shoot');assert.equal(who.completed_starts,1);assert.equal(who.finish_rate,100);assert.equal(who.win_rate,100);assert.equal(who.avg_attempts,2);assert.equal(who.avg_round_ms,18000);assert.equal(who.avg_score,2);assert.equal(shoot.left_unfinished,1);assert.equal(shoot.finish_rate,0);
  assert(d.flows.some(r=>r.from_mode==='shoot'&&r.mode==='hub'));assert.equal(d.teams[0].team,'CGY');assert.equal(d.progress.find(r=>r.mode==='shoot').exits,1);assert.equal(d.coverage.recognized_sessions,5);assert(d.heatmap.some(r=>r.hour===12));assert.equal(d.realtime.sessions,2,'Real-time totals count sessions once across several modes');
  assert.equal(d.performance.find(r=>r.browser==='duckduckgo').load_ms,null);assert.equal(d.performance.find(r=>r.browser==='chrome').load_samples,1);assert.equal(d.errors[0].action,'javascript');assert(d.countries.some(r=>r.country==='DE'));assert(d.pages.some(r=>r.mode==='hub'&&r.exits===1));
  const tagged=await report('days=30&source=instagram');assert.equal(tagged.summary.visitors,1);assert.equal(tagged.retention.day7_returned,1,'Acquired visitors can return through another source');
  const daily=await report('days=30&variant=daily');assert.equal(daily.summary.starts,1);assert.equal(daily.modes.find(r=>r.mode==='whoscored').avg_score,2);
  const german=await report('days=30&country=DE&mode=shoot&variant=unlimited&device=desktop&browser=firefox&source=direct');assert.equal(german.summary.visitors,1);assert.equal(german.modes.length,1);assert.equal(german.modes[0].mode,'shoot');
  const custom=await report('from=2026-10-03&to=2026-10-04');assert.equal(custom.days,2);assert.equal(custom.summary.visits,3);
  const young=await report('days=1');assert.equal(young.retention.day1_rate,null);assert.equal(young.retention.day7_rate,null,'New cohorts wait until their return windows mature');
  for(const query of ['days=999','from=2026-02-31&to=2026-10-13','from=2026-10-14&to=2026-10-15','mode=bad','country=%27OR%201=1','browser=madeup','source=raw-url'])assert.equal((await call('/api/analytics/report?'+query,undefined,{cookie})).status,400);
  const count=db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n;
  for(const extra of [{name:'private-name'},{visitor:'not-a-uuid'},{browser:'arbitrary user agent'},{campaign:'someone@example.com'},{correct:'yes'},{score:1e50},{cls:-1},{action:'private stack trace'}])assert.equal((await call('/api/analytics/collect',{events:[event(c,'mode_open',{mode:'classic',variant:'daily'}),event(c,'round_step',{mode:'shoot',variant:'daily',round:uuid(),step:1,...extra})]})).status,400);
  assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n,count,'Malformed batches leave no partial writes');
  assert.equal((await call('/api/analytics/collect',{events:Array.from({length:6},()=>event(c,'site_visit'))})).status,400);
  const rows=JSON.stringify(db.sql.prepare('SELECT * FROM sweater_analytics_details').all());for(const raw of [a.visitor,a.visit,b.visitor,c.visitor])assert(!rows.includes(raw),'Stored identities are keyed hashes');assert(!JSON.stringify(d).includes(a.visitor));assert(!JSON.stringify(d).includes(roundA));assert(!rows.includes('203.0.113.20'));
  const partyRound=uuid();await collect([event(c,'round_start',{mode:'party',variant:'party',round:partyRound}),event(c,'round_complete',{mode:'party',variant:'party',round:partyRound,won:null,step:3,elapsed_ms:30000})]);const withParty=await report();assert.equal(withParty.summary.win_rate,100,'Noncompetitive completions do not lower win rate');
  const oldID=db.sql.prepare('SELECT id FROM sweater_analytics_events LIMIT 1').get().id;db.sql.prepare('UPDATE sweater_analytics_events SET received_at=? WHERE id=?').run(fixed-366*86400000,oldID);await purgeAnalytics(env);assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_details WHERE event_id=?').get(oldID).n,0,'Event details are pruned with the old event');
  assert(db.maxBindings<=100);console.log('Extended analytics: cold D1 budgets, atomic batches, privacy, visitors/visits, returning cohorts, source changes, filters, results, progression, performance, traffic, real-time, legacy clients and cleanup passed.');
}finally{Date.now=actualNow;db.sql.close();}
