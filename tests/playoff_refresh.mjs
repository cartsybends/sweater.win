import assert from 'node:assert/strict';
import {refreshPlayoffs,refreshProjections} from '../backend/src/playoff-refresh.mjs';
import worker from '../backend/src/index.mjs';
const now=Date.parse('2026-11-13T23:50:00Z'),env={GITHUB_REFRESH_TOKEN:'test-only-never-a-real-token'};
const feed=minutes=>new Response(JSON.stringify({checked_at:new Date(now-minutes*60000).toISOString()}));
let calls=[];
const mock=responses=>async(url,options={})=>{calls.push({url,options});const next=responses.shift();if(next instanceof Error)throw next;return next;};
assert.equal((await refreshPlayoffs({}, {now,fetcher:()=>{throw Error('must not fetch');}})).status,'not_configured');
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(3)])})).status,'fresh');assert.equal(calls.length,1);assert(!calls[0].options.headers?.Authorization);
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(12)])})).status,'fresh');assert.equal(calls.length,1,'Full forecasts target fifteen minutes, independently of live game checks');
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[]})),new Response(null,{status:204})])})).status,'dispatched');assert.equal(calls.length,3);assert.equal(calls[2].options.method,'POST');assert.deepEqual(JSON.parse(calls[2].options.body),{ref:'main'});assert(calls[2].url.endsWith('/refresh-playoffs.yml/dispatches'));
for(const status of ['queued','in_progress','waiting']){calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[{status}]}))])})).status,'running');assert.equal(calls.length,2);}
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[{status:'completed',created_at:new Date(now-60000).toISOString()}]}))])})).status,'cooldown');assert.equal(calls.length,2);
calls=[];const failure=await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response('private response omitted',{status:403})])});assert.deepEqual(failure,{status:'github_error',stage:'github_runs_fetch',code:403});assert(!JSON.stringify(failure).includes(env.GITHUB_REFRESH_TOKEN));
assert.deepEqual(await refreshPlayoffs(env,{now,fetcher:mock([new Error('network unavailable')])}),{status:'unavailable',stage:'feed_fetch',code:'Error'});
for(const [responses,stage,code] of [
 [[new Response('private malformed feed')],'feed_parse','SyntaxError'],
 [[feed(39),new TypeError(env.GITHUB_REFRESH_TOKEN)],'github_runs_fetch','TypeError'],
 [[feed(39),new Response('private malformed runs')],'github_runs_parse','SyntaxError'],
 [[feed(39),new Response(JSON.stringify({workflow_runs:[]})),new DOMException(env.GITHUB_REFRESH_TOKEN,'TimeoutError')],'github_dispatch','TimeoutError']
]){
 const result=await refreshPlayoffs(env,{now,fetcher:mock(responses)});
 assert.deepEqual(result,{status:'unavailable',stage,code});
 assert(!JSON.stringify(result).includes(env.GITHUB_REFRESH_TOKEN));
}
const projectionsFeed=minutes=>Response.json({collected_at:new Date(now-minutes*60000).toISOString()});
calls=[];
assert.equal((await refreshProjections(env,{now,fetcher:mock([projectionsFeed(5)])})).status,'fresh');
assert.equal(calls.length,1);
assert(calls[0].url.includes('/projections_cache.json?'));
calls=[];
assert.equal((await refreshProjections(env,{now,fetcher:mock([projectionsFeed(35),Response.json({workflow_runs:[]}),new Response(null,{status:204})])})).status,'dispatched');
assert(calls[1].url.endsWith('/refresh-projections.yml/runs?per_page=5'));
assert(calls[2].url.endsWith('/refresh-projections.yml/dispatches'));
for(const [offset,expected] of [[0,2],[60000,1]]){
 const tasks=[];await worker.scheduled({cron:'* * * * *',scheduledTime:now+offset},{},{waitUntil:p=>tasks.push(p)});
 await Promise.all(tasks);
 assert.equal(tasks.length,expected,'Check playoff freshness each minute and projection freshness every five minutes');
}
console.log('PASS NHL watchdogs: refresh cadence, duplicate-job guards, cooldown, errors, and secret isolation');
