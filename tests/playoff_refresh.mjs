import assert from 'node:assert/strict';
import {refreshPlayoffs} from '../backend/src/playoff-refresh.mjs';
import worker from '../backend/src/index.mjs';
const now=Date.parse('2026-11-13T23:50:00Z'),env={GITHUB_REFRESH_TOKEN:'test-only-never-a-real-token'};
const feed=minutes=>new Response(JSON.stringify({checked_at:new Date(now-minutes*60000).toISOString()}));
let calls=[];
const mock=responses=>async(url,options={})=>{calls.push({url,options});const next=responses.shift();if(next instanceof Error)throw next;return next;};
assert.equal((await refreshPlayoffs({}, {now,fetcher:()=>{throw Error('must not fetch');}})).status,'not_configured');
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(3)])})).status,'fresh');assert.equal(calls.length,1);assert(!calls[0].options.headers?.Authorization);
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[]})),new Response(null,{status:204})])})).status,'dispatched');assert.equal(calls.length,3);assert.equal(calls[2].options.method,'POST');assert.deepEqual(JSON.parse(calls[2].options.body),{ref:'main'});assert(calls[2].url.endsWith('/refresh-playoffs.yml/dispatches'));
for(const status of ['queued','in_progress','waiting']){calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[{status}]}))])})).status,'running');assert.equal(calls.length,2);}
calls=[];assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response(JSON.stringify({workflow_runs:[{status:'completed',created_at:new Date(now-60000).toISOString()}]}))])})).status,'cooldown');assert.equal(calls.length,2);
calls=[];const failure=await refreshPlayoffs(env,{now,fetcher:mock([feed(39),new Response('private response omitted',{status:403})])});assert.deepEqual(failure,{status:'github_error',code:403});assert(!JSON.stringify(failure).includes(env.GITHUB_REFRESH_TOKEN));
assert.equal((await refreshPlayoffs(env,{now,fetcher:mock([new Error('network unavailable')])})).status,'unavailable');
const tasks=[];await worker.scheduled({cron:'* * * * *'},{},{waitUntil:p=>tasks.push(p)});await Promise.all(tasks);assert.equal(tasks.length,1,'Minute clock must not run daily database cleanup');
console.log('PASS playoff watchdog: fresh/stale feeds, no duplicate jobs, cooldown, errors, secret isolation and separate daily cleanup');
