import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from '../backend/node_modules/miniflare/dist/src/index.js';
const model=await readFile(new URL('../backend/src/playoff-live-model.mjs',import.meta.url),'utf8');
const market=await readFile(new URL('../backend/src/playoff-live-market.mjs',import.meta.url),'utf8');
const handler=(await readFile(new URL('../backend/src/playoff-live.mjs',import.meta.url),'utf8')).replace(/^import .*\n/gm,'');
const runtime=new Miniflare(convertV4MiniflareOptions({modules:true,compatibilityDate:'2026-10-12',cf:false,script:model+'\n'+market+'\n'+handler+`
 let fetchCalls=0;
 export default {async fetch(request){
 const start='2026-11-14T02:00:00Z',now=Date.parse('2026-11-14T02:30:00Z');
 const g={id:2026020310,home:'VAN',away:'NYR',start,state:'LIVE',market:{source_url:'https://www.espn.com/nhl/game/_/gameId/401892706'},prediction:{home_goals:2.6,away_goals:3.4,home_win:38.5,basis:'recorded',at:'2026-11-14T01:50:00Z'}};
 const raw={id:g.id,startTimeUTC:start,gameType:2,gameState:'LIVE',homeTeam:{abbrev:'VAN',score:2},awayTeam:{abbrev:'NYR',score:1},periodDescriptor:{number:3,periodType:'REG'},clock:{secondsRemaining:60}};
 const summary={header:{id:'401892706',competitions:[{date:start,status:{type:{state:'in'}},competitors:[{homeAway:'home',team:{abbreviation:'VAN'}},{homeAway:'away',team:{abbreviation:'NYR'}}]}]},pickcenter:[{provider:{name:'Draft Kings'},moneyline:{home:{live:{odds:'+310'}},away:{live:{odds:'-445'}}}}]};
 const response=await handlePlayoffLive(request,{},null,{now,fetcher:async(url,options)=>{fetchCalls++;new Request(url,options);return Response.json(url.includes('/score/')?{games:[raw]}:url.includes('/summary?')?summary:{checked_at:new Date(now).toISOString(),games:[g]});}});
 return Response.json({...await response.json(),upstream_requests:fetchCalls},{status:response.status});
 }}
 `}));
try{
 const response=await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/live?date=2026-11-13',{headers:{Origin:'https://sweater.win'}});
 assert.equal(response.status,200);const data=await response.json();assert.equal(data.games[0].status,'live');assert(data.games[0].home_win>95);assert.equal(data.games[0].home_win+data.games[0].away_win,100);
 assert.equal(data.games[0].market.home,310);assert.equal(data.games[0].market.away,-445);assert.equal(data.upstream_requests,3);
 const cached=await (await runtime.dispatchFetch('https://api.sweater.win/api/playoffs/live?date=2026-11-13')).json();assert.equal(cached.upstream_requests,3,'Real workerd Cache API avoids refetching for the next browser');
 console.log('PASS Cloudflare workerd runtime: live model and DraftKings route, fetch options and real edge Cache API');
}finally{await runtime.dispose();}
