import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from '../backend/node_modules/miniflare/dist/src/index.js';
const root=new URL('../',import.meta.url),raw=JSON.parse(await readFile(new URL('playoffs_lines/matchups/2026020331.json',root))),g={id:raw.id,start:raw.start,date:raw.start.slice(0,10),home:raw.home,away:raw.away};
let source=(await readFile(new URL('static/playoffs/preview-model.mjs',root),'utf8')).replace('export const','const')+'\n'+(await readFile(new URL('backend/src/game-preview.mjs',root),'utf8')).replace(/^import .*\n/gm,'');
source+=`\nlet requests=0;const baseline=${JSON.stringify(g)},raw=${JSON.stringify(raw)};
export default {async fetch(request){const response=await handleGamePreview(request,{},null,{now:${Math.max(Date.now(),Date.parse(raw.as_of))},fetcher:async(url,options)=>{new Request(url,options);requests++;return Response.json(url.endsWith('/playoffs_cache.json')?{games:[baseline]}:raw);}});return Response.json({data:await response.json(),upstream_requests:requests},{status:response.status,headers:{'Access-Control-Allow-Origin':response.headers.get('Access-Control-Allow-Origin')||''}});}};`;
const runtime=new Miniflare(convertV4MiniflareOptions({modules:true,compatibilityDate:'2026-10-12',cf:false,script:source}));
try{
 const response=await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/preview?id='+raw.id,{headers:{Origin:'https://sweater.win'}}),d=await response.json();
 assert.equal(response.status,200);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://sweater.win');assert.equal(d.data.id,raw.id);assert.equal(d.upstream_requests,2);
 const cached=await(await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/preview?id='+raw.id)).json();assert.equal(cached.upstream_requests,2);
 assert.equal((await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/preview?id=2026029999')).status,404);
 console.log('PASS workerd preview validation, native Cache API, request options, CORS and published-window gate');
}finally{await runtime.dispose();}
