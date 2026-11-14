import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from '../backend/node_modules/miniflare/dist/src/index.js';

// Use Workers' Request implementation: Node accepts redirect:"error", but
// workerd rejects it before sending a request. No external traffic or real token.
const source=await readFile(new URL('../backend/src/playoff-refresh.mjs',import.meta.url),'utf8');
const config=JSON.parse((await readFile(new URL('../backend/wrangler.jsonc',import.meta.url),'utf8')).replace(/^\s*\/\/.*$/gm,''));
const runtime=new Miniflare(convertV4MiniflareOptions({
 modules:true,compatibilityDate:config.compatibility_date,cf:false,
 script:source+`
 export default {async fetch(request){
  const scenario=new URL(request.url).pathname.slice(1),calls=[];
  const now=Date.parse('2026-11-13T23:50:00Z');
  const result=await refreshPlayoffs({GITHUB_REFRESH_TOKEN:'test-only-runtime-token'},{now,fetcher:async(url,options)=>{
   const outgoing=new Request(url,options);
   calls.push({url:outgoing.url,redirect:outgoing.redirect,authorization:outgoing.headers.has('Authorization'),method:outgoing.method});
   if(calls.length===1)return Response.json({checked_at:new Date(now-(scenario==='fresh'?3:39)*60000).toISOString()});
   if(calls.length===2){
    if(scenario==='redirect')return new Response(null,{status:302,headers:{Location:'https://untrusted.invalid/'}});
    return Response.json({workflow_runs:scenario==='running'?[{status:'in_progress'}]:[]});
   }
   if(calls.length===3 && outgoing.method==='POST' && (await outgoing.json()).ref==='main')return new Response(null,{status:204});
   throw new Error('Unexpected outgoing request');
  }});
  return Response.json({result,calls});
 }}
 `
}));
try{
 const run=async scenario=>(await runtime.dispatchFetch('http://localhost/'+scenario)).json();
 const stale=await run('stale');
 assert.equal(stale.result.status,'dispatched','Stale feeds must dispatch using Request options supported by workerd');
 assert.equal(stale.calls.length,3);
 assert.equal(stale.calls[0].authorization,false);
 assert(stale.calls.slice(1).every(call=>call.redirect==='manual'&&call.authorization));
 const fresh=await run('fresh');assert.equal(fresh.result.status,'fresh');assert.equal(fresh.calls.length,1);
 const running=await run('running');assert.equal(running.result.status,'running');assert.equal(running.calls.length,2);
 const redirect=await run('redirect');assert.equal(redirect.result.status,'github_error');assert.equal(redirect.result.code,302);assert.equal(redirect.calls.length,2,'Never forward the token to a redirect destination');
 console.log('PASS playoff watchdog in workerd: supported requests, authenticated dispatch, fresh/running guards and redirect isolation');
}finally{await runtime.dispose();}
