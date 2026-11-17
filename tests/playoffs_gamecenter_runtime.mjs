import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from '../backend/node_modules/miniflare/dist/src/index.js';
import {fixture} from './fixtures/gamecenter.mjs';
const {g,raw,at}=fixture();let source='';
for(const name of ['nhl-clock','penalty-rates','penalty-state','penalty-forecast','playoff-live-model','shot-model','shot-quality','game-center-model','game-center'])source+=(await readFile(new URL('../backend/src/'+name+'.mjs',import.meta.url),'utf8')).replace(/^import .*\n/gm,'')+'\n';
source+=`let requests=0;const baseline=${JSON.stringify(g)},raw=${JSON.stringify(raw)},at=${JSON.stringify(at)};
export default {async fetch(request){const scenario=new URL(request.url).searchParams.get('scenario'),input=structuredClone(raw);if(scenario==='intermission')input.clock={secondsRemaining:1080,timeRemaining:'18:00',inIntermission:true};if(scenario==='lagging')input.clock={secondsRemaining:1200,timeRemaining:'20:00',inIntermission:false};const response=await handleGameCenter(request,{},null,{now:Date.parse(at),cache:scenario?null:caches.default,fetcher:async(url,options)=>{new Request(url,options);requests++;return Response.json(url.includes('raw.githubusercontent')?{checked_at:at,games:[baseline]}:input);}});return Response.json({data:await response.json(),upstream_requests:requests},{status:response.status,headers:{'Access-Control-Allow-Origin':response.headers.get('Access-Control-Allow-Origin')||''}});}};`;
const runtime=new Miniflare(convertV4MiniflareOptions({modules:true,compatibilityDate:'2026-10-12',cf:false,script:source}));
try{
 const r=await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/game?id='+g.id,{headers:{Origin:'https://sweater.win'}}),d=await r.json();assert.equal(r.status,200);assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://sweater.win');assert.equal(d.data.shots.length,6);assert.equal(d.data.forecast.status,'available');assert.equal(d.upstream_requests,2);
 const cached=await(await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/game?id='+g.id)).json();assert.equal(cached.upstream_requests,2);assert.equal(cached.data.checked_at,d.data.checked_at);assert.equal((await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/game?id=2026029999')).status,404);
 for(const [scenario,time] of [['intermission',2400],['lagging',1800]]){const r=await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/game?id='+g.id+'&refresh=5&scenario='+scenario),body=await r.json();assert.equal(r.status,200);assert.equal(body.data.forecast.status,'available');assert.equal(body.data.elapsed,time);assert.equal(body.data.shots.length,6);assert.equal(body.data.refresh_seconds,5);}
 console.log('PASS Cloudflare workerd: Game Center model inference, upstream fetch options, identity gate, CORS and shared Cache API');
}finally{await runtime.dispose();}
