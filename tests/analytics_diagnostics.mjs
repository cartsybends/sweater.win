import assert from 'node:assert/strict';
import worker from '../backend/src/index.mjs';
import {purgeAnalytics} from '../backend/src/analytics.mjs';
import {AnalyticsDB} from './helpers/analytics_runtime.mjs';

const db=new AnalyticsDB(),env={DB:db,ALLOWED_ORIGINS:'https://sweater.win',SWEATER_ANALYTICS_PASSWORD:'test-only-diagnostics-password-000000000000'};
const actors=Array.from({length:2},()=>({visitor:crypto.randomUUID(),visit:crypto.randomUUID(),session:crypto.randomUUID()}));
const error=(extra={},actor=actors[0])=>({version:2,id:crypto.randomUUID(),...actor,mode:'whoscored',variant:'daily',kind:'error',device:'mobile',browser:'safari',os:'ios',build:'138',action:'javascript',...extra});
async function call(path,body,cookie){
  const request=new Request('https://api.sweater.win'+path,{method:body===undefined?'GET':'POST',headers:{Origin:path==='/analytics/login'?'https://api.sweater.win':'https://sweater.win','Content-Type':'application/json',...(cookie?{Cookie:cookie}:{})},...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});
  const before=db.queries,response=await worker.fetch(request,env,{});
  assert(db.queries-before<=50,'Cold batches of five errors and reports remain within the free D1 query limit');
  return response;
}
try{
  const detail={release:'0123456789ab',error_type:'TypeError',error_file:'app.html',error_line:4500,error_column:17,online:true};
  const events=[error(detail),error(detail,actors[1]),error({...detail,release:'abcdef012345'}),
    error({release:detail.release,action:'resource',resource:'goal_video',asset:'goal-79-masked-v2.mp4',error_type:'MediaDecodeError',online:false}),error()];
  const collected=await call('/api/analytics/collect',{events});assert.equal(collected.status,200,await collected.clone().text());
  assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_errors').get().n,5);
  assert.equal((await call('/api/analytics/collect',{events})).status,200);
  assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_errors').get().n,5,'Retries deduplicate diagnostic records');
  const status=await call('/api/analytics/status');assert.equal((await status.json()).diagnostics,1);
  assert.equal((await call('/api/analytics/report')).status,401,'Diagnostics retain private report access');
  const auth=await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD)),cookie=auth.headers.get('Set-Cookie').split(';')[0];
  const response=await call('/api/analytics/report?days=1',undefined,cookie);assert.equal(response.status,200);const report=await response.json();
  const recurring=report.errors.find(row=>row.release===detail.release&&row.action==='javascript');
  assert.equal(recurring.errors,2);assert.equal(recurring.sessions,2);assert.equal(recurring.error_line,4500);assert.equal(recurring.error_column,17);assert.equal(recurring.error_type,'TypeError');
  assert.equal(report.errors.filter(row=>row.error_type==='TypeError').length,2,'Releases with the same builder version remain separate');
  assert.equal(report.errors.find(row=>row.action==='resource').asset,'goal-79-masked-v2.mp4');
  assert.equal(report.errors.find(row=>row.action==='resource').online,0);
  assert(report.errors.some(row=>row.release===null&&row.errors===1),'Earlier category-only events remain available');
  // A forged retry belonging to another session cannot replace another event's diagnostics.
  assert.equal((await call('/api/analytics/collect',{events:[{...events[0],...actors[1],release:'aaaaaaaaaaaa'}]})).status,200);
  assert.equal(db.sql.prepare('SELECT release FROM sweater_analytics_errors WHERE event_id=?').get(events[0].id).release,detail.release);
  const count=db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n;
  for(const extra of [
    {message:'private input'}, {stack:'private trace'}, {url:'https://private.example'},
    {release:'private@example.com'}, {error_type:'private-name'}, {error_file:'https://sweater.win/app.html?private=1'},
    {error_line:-1}, {error_column:2.5}, {error_file:'external',error_line:10},
    {resource:'private URL'}, {resource:'headshot',asset:'8476399.png'},
    {resource:'goal_video',asset:'goal-79-masked-v2.mp4?private=1'}, {online:'yes'},
    {kind:'interaction',action:'stats_open',release:detail.release},
  ]) {
    assert.equal((await call('/api/analytics/collect',{events:[error(),error(extra)]})).status,400);
    assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_events').get().n,count,'Invalid batches are rejected before any writes');
  }
  const stored=JSON.stringify(db.sql.prepare('SELECT * FROM sweater_analytics_errors').all());
  for(const value of ['private',...actors.flatMap(actor=>Object.values(actor))])assert(!stored.includes(value));
  db.sql.prepare('UPDATE sweater_analytics_events SET received_at=?').run(Date.now()-366*86400000);
  await purgeAnalytics(env);
  assert.equal(db.sql.prepare('SELECT COUNT(*) n FROM sweater_analytics_errors').get().n,0,'Diagnostic details expire with their events');
  console.log('Browser diagnostics: cold D1 budgets, release grouping, locations/assets, private reports, legacy events, retries, validation, privacy and retention passed.');
}finally{db.sql.close();}
