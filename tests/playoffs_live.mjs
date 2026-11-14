import assert from 'node:assert/strict';
import {liveProbability,liveSnapshot} from '../backend/src/playoff-live-model.mjs';
import {handlePlayoffLive} from '../backend/src/playoff-live.mjs';
import {americanPrice,matchesMarketGame,parseLiveMarket,collectLiveMarket} from '../backend/src/playoff-live-market.mjs';
import {PLAYOFF_PICTURE as M} from '../static/playoffs/model.mjs';

const now=Date.parse('2026-11-14T02:30:00Z'),at=new Date(now).toISOString();
const game={id:2026020310,home:'VAN',away:'NYR',start:'2026-11-14T02:00:00Z',state:'LIVE',prediction:{home_goals:2.6,away_goals:3.4,home_win:38.5,away_win:61.5,basis:'recorded',at:'2026-11-14T01:50:00Z'}};
game.market={source:'ESPN',provider:'DraftKings',source_url:'https://www.espn.com/nhl/game/_/gameId/401892706',home:170,away:-205,observed_at:'2026-11-14T01:50:00Z'};
// Captured ESPN NHL summary structure: live prices differ from close prices.
const summary=()=>({header:{id:'401892706',competitions:[{date:game.start,status:{type:{state:'in',completed:false}},competitors:[{homeAway:'home',team:{abbreviation:'VAN'}},{homeAway:'away',team:{abbreviation:'NYR'}}]}]},pickcenter:[{provider:{id:'100',name:'Draft Kings'},moneyline:{home:{close:{odds:'+170'},live:{odds:'+310'}},away:{close:{odds:'-205'},live:{odds:'-445'}}}}]});
const raw={id:game.id,gameType:2,homeTeam:{abbrev:'VAN',score:2},awayTeam:{abbrev:'NYR',score:1},startTimeUTC:game.start,gameState:'LIVE',periodDescriptor:{number:2,periodType:'REG'},clock:{secondsRemaining:600,inIntermission:false}};
const state=(patch={})=>({homeScore:0,awayScore:0,period:1,periodType:'REG',seconds:1200,...patch});
const predict=patch=>liveProbability(game.prediction,state(patch));
assert.equal(predict().home_win,38.5,'Opening faceoff must preserve the saved pregame probability');
assert(predict({homeScore:1}).home_win>38.5);
assert(predict({awayScore:1}).home_win<38.5);
assert(predict({homeScore:1,period:3,seconds:60}).home_win>predict({homeScore:1}).home_win,'A lead is more valuable late');
assert(predict({awayScore:1,period:3,seconds:60}).home_win<predict({awayScore:1}).home_win);
assert(predict({homeScore:4,period:3,seconds:20}).home_win>99.9);
assert.equal(predict({homeScore:1,period:3,seconds:0}).home_win,100);
assert.equal(predict({awayScore:1,period:3,seconds:0}).home_win,0);
for(let period=1;period<=3;period++)for(const seconds of [0,60,600,1200])for(let margin=-5;margin<=5;margin++){
 const input=state({period,seconds,homeScore:Math.max(margin,0),awayScore:Math.max(-margin,0)}),p=liveProbability(game.prediction,input);
 assert(p.home_win>=0&&p.home_win<=100);assert(Math.abs(p.home_win+p.away_win-100)<.00001);
 const reverse=liveProbability({...game.prediction,home_goals:3.4,away_goals:2.6,home_win:61.5},{...input,homeScore:input.awayScore,awayScore:input.homeScore});
 assert(Math.abs(p.home_win+reverse.home_win-100)<.0002,'Swapping teams preserves complementarity');
}
const ot=predict({period:4,periodType:'OT',seconds:300}),lateOt=predict({period:4,periodType:'OT',seconds:1});
assert(ot.home_win>0&&ot.home_win<100);assert(Math.abs(lateOt.home_win-50)<Math.abs(ot.home_win-50));
assert(liveProbability(game.prediction,state({gameType:3,period:5,periodType:'OT',seconds:1200})));
for(const patch of [{seconds:-1},{seconds:1201},{homeScore:-1},{homeScore:NaN},{periodType:'SO',period:5},{period:0},{period:4,periodType:'OT',seconds:301}])assert.equal(predict(patch),null);

const original=structuredClone(game),snapshot=liveSnapshot(raw,game,at);
assert.equal(snapshot.status,'live');assert(snapshot.home_win>game.prediction.home_win);assert.deepEqual(game,original,'Live estimates never overwrite the recorded prediction');
for(const patch of [{id:123},{homeTeam:{abbrev:'SEA',score:2}},{startTimeUTC:'2026-11-14T03:00:00Z'},{clock:{secondsRemaining:NaN}},{awayTeam:{abbrev:'NYR',score:-1}}])assert.throws(()=>liveSnapshot({...raw,...patch},game,at));
assert.equal(liveSnapshot(raw,{...game,prediction:{...game.prediction,basis:'reconstructed',at:null}},at).reason,'pregame_unavailable');
assert.equal(liveSnapshot({...raw,periodDescriptor:{number:5,periodType:'SO'},clock:{secondsRemaining:0}},game,at).reason,'shootout');
const final=liveSnapshot({...raw,gameState:'OFF',gameOutcome:{lastPeriodType:'REG'}},game,at);assert.equal(final.status,'final');assert.equal(final.home_win,undefined);
assert.throws(()=>liveSnapshot({...raw,gameState:'OFF',homeTeam:{abbrev:'VAN',score:1}},game,at));

const payload={version:1,checked_at:at,refresh_seconds:30,games:[snapshot]};
assert(M.liveFeed(payload,[game],now));
for(const mutate of [d=>d.games[0].home='SEA',d=>d.games[0].home_win=NaN,d=>d.games[0].away_win=99,d=>d.games[0].seconds_remaining=-1,d=>d.games[0].pregame_at=game.start,d=>d.games.push(d.games[0])]){
 const changed=structuredClone(payload);mutate(changed);assert.equal(M.liveFeed(changed,[game],now),null);
}

let calls=[];
const fetcher=async(url,options)=>{new Request(url,options);calls.push(url);return Response.json(url.includes('/v1/score/')?{games:[raw]}:url.includes('/summary?')?summary():{checked_at:at,games:[game]});};
const cacheData=new Map(),cache={match:async key=>cacheData.get(key.url)?.clone(),put:async(key,response)=>{cacheData.set(key.url,response.clone());}};
const request=new Request('https://api.sweater.win/api/playoffs/live?date=2026-11-13',{headers:{Origin:'https://sweater.win'}});
const response=await handlePlayoffLive(request,{},null,{fetcher,cache,now});
assert.equal(response.status,200);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://sweater.win');
const body=await response.json();assert(M.liveFeed(body,[game],now));assert.equal(body.games[0].home_win,snapshot.home_win);assert.equal(calls.length,3);assert.equal(body.games[0].market.home,310);assert.equal(body.games[0].market.away,-445);
assert.equal((await handlePlayoffLive(request,{},null,{fetcher,cache,now:now+10000})).status,200);assert.equal(calls.length,3,'Repeated clients reuse the 30-second edge cache');
assert.equal((await handlePlayoffLive(request,{},null,{fetcher,cache,now:now+31000})).status,200);assert.equal(calls.length,5,'Scoring and live quotes refresh independently of the longer pregame-feed cache');
assert.deepEqual(game,original,'Neither the live model nor the live bookmaker feed overwrites pregame records');
for(const change of [m=>m.home=0,m=>m.source_url='https://untrusted.invalid/odds',m=>m.provider='Other book',m=>m.status='suspended',m=>m.observed_at='2026-11-15T00:00:00Z',m=>m.observed_at='2026-11-14T01:50:00Z']){
 const invalid=structuredClone(body);change(invalid.games[0].market);assert.equal(M.liveFeed(invalid,[game],now),null);
}
const outage=await handlePlayoffLive(request,{},null,{now,cache:null,fetcher:async(url,options)=>{if(url.includes('espn.com'))throw Error('provider unavailable');return fetcher(url,options);}});
assert.equal(outage.status,200);const missing=await outage.json();assert.equal(missing.games[0].status,'live');assert.equal(missing.games[0].market.status,'unavailable');assert(M.liveFeed(missing,[game],now));
const keepAlive=setTimeout(()=>{},6000),started=Date.now();
try{
 const slow=await handlePlayoffLive(request,{},null,{now,cache:null,fetcher:async(url,options)=>{
  if(url.includes('espn.com'))return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}));
  return fetcher(url,options);
 }});
 assert.equal(slow.status,200);const data=await slow.json();assert.equal(data.games[0].status,'live');assert.equal(data.games[0].market.status,'unavailable');assert(Date.now()-started<6000,'Slow odds have a bounded budget inside the model response window');
}finally{clearTimeout(keepAlive);}
const noFetch=()=>{throw Error('must not fetch');};
for(const [url,options,status] of [
 ['https://api.sweater.win/api/playoffs/live?date=2020-01-01',{},400],
 ['https://api.sweater.win/api/playoffs/live',{headers:{Origin:'https://untrusted.invalid'}},403],
 ['https://api.sweater.win/api/playoffs/live',{method:'POST'},405],
 ['https://api.sweater.win/api/playoffs/live',{method:'OPTIONS',headers:{Origin:'https://sweater.win'}},204],
])assert.equal((await handlePlayoffLive(new Request(url,options),{},null,{fetcher:noFetch,cache:null,now})).status,status);
assert.equal(await handlePlayoffLive(new Request('https://api.sweater.win/api/other'),{},null,{fetcher:noFetch,now}),null);
assert.equal((await handlePlayoffLive(request,{},null,{fetcher:async()=>{throw Error('private upstream details');},cache:null,now})).status,503);
const market=parseLiveMarket(summary(),game,at);assert.equal(market.home,310);assert.equal(market.away,-445);assert.equal(market.status,'live');
for(const value of [null,0,99,1.5,NaN,Infinity,true,'+1.5','1000001'])assert.equal(americanPrice(value),null);
assert.equal(americanPrice('EVEN'),100);assert.equal(americanPrice('−445'),-445);
for(const mutate of [s=>s.header.competitions[0].competitors[0].team.abbreviation='SEA',s=>s.header.competitions[0].date='2026-11-15T02:00:00Z']){const s=summary();mutate(s);assert.equal(parseLiveMarket(s,game,at),null);}
assert.equal(parseLiveMarket(summary(),game,game.market.observed_at),null);
for(const mutate of [s=>delete s.pickcenter[0].moneyline.home.live,s=>s.pickcenter[0].moneyline.away.live.odds=null,s=>s.pickcenter[0].provider.name='Other book',s=>s.header.competitions[0].status.type.state='post']){
 const s=summary();mutate(s);const m=parseLiveMarket(s,game,at);assert.equal(m.status,'unavailable');assert.equal(m.home,undefined,'Closing prices must never masquerade as live prices');
}
const suspended=summary();suspended.pickcenter[0].moneyline.home.live.odds='OFF';const off=parseLiveMarket(suspended,game,at);assert.equal(off.status,'suspended');assert.equal(off.home,undefined);assert.equal(off.away,undefined);
const offFeed={...payload,games:[{...snapshot,market:off}]};assert(M.liveFeed(offFeed,[game],now));
const lookup=[];const getter=async url=>{lookup.push(url);return {data:url.includes('scoreboard?')?{events:[{id:'401892706',competitions:summary().header.competitions}]}:summary(),observed_at:at};};
assert.equal((await collectLiveMarket({...game,market:undefined},getter,'2026-11-13',at)).home,310);assert.equal(lookup.length,2);assert(lookup[0].includes('dates=20261113'));
assert(matchesMarketGame(summary().header,game));
console.log('PASS live hockey model and market: saved priors, score/clock, overtime, explicit DraftKings live prices, OFF/missing markets, strict identity/timestamps, cache/CORS and independent provider outages');
