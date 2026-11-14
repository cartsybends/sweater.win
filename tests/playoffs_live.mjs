import assert from 'node:assert/strict';
import {liveProbability,liveSnapshot} from '../backend/src/playoff-live-model.mjs';
import {handlePlayoffLive} from '../backend/src/playoff-live.mjs';
import {PLAYOFF_PICTURE as M} from '../static/playoffs/model.mjs';

const now=Date.parse('2026-11-14T02:30:00Z'),at=new Date(now).toISOString();
const game={id:2026020310,home:'VAN',away:'NYR',start:'2026-11-14T02:00:00Z',state:'LIVE',prediction:{home_goals:2.6,away_goals:3.4,home_win:38.5,away_win:61.5,basis:'recorded',at:'2026-11-14T01:50:00Z'}};
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
const fetcher=async(url,options)=>{new Request(url,options);calls.push(url);return Response.json(url.includes('/v1/score/')?{games:[raw]}:{checked_at:at,games:[game]});};
const cacheData=new Map(),cache={match:async key=>cacheData.get(key.url)?.clone(),put:async(key,response)=>{cacheData.set(key.url,response.clone());}};
const request=new Request('https://api.sweater.win/api/playoffs/live?date=2026-11-13',{headers:{Origin:'https://sweater.win'}});
const response=await handlePlayoffLive(request,{},null,{fetcher,cache,now});
assert.equal(response.status,200);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://sweater.win');
const body=await response.json();assert(M.liveFeed(body,[game],now));assert.equal(body.games[0].home_win,snapshot.home_win);assert.equal(calls.length,2);
assert.equal((await handlePlayoffLive(request,{},null,{fetcher,cache,now:now+10000})).status,200);assert.equal(calls.length,2,'Repeated clients reuse the 30-second edge cache');
assert.equal((await handlePlayoffLive(request,{},null,{fetcher,cache,now:now+31000})).status,200);assert.equal(calls.length,3,'Scoring refreshes independently of the longer pregame-feed cache');
const noFetch=()=>{throw Error('must not fetch');};
for(const [url,options,status] of [
 ['https://api.sweater.win/api/playoffs/live?date=2020-01-01',{},400],
 ['https://api.sweater.win/api/playoffs/live',{headers:{Origin:'https://untrusted.invalid'}},403],
 ['https://api.sweater.win/api/playoffs/live',{method:'POST'},405],
 ['https://api.sweater.win/api/playoffs/live',{method:'OPTIONS',headers:{Origin:'https://sweater.win'}},204],
])assert.equal((await handlePlayoffLive(new Request(url,options),{},null,{fetcher:noFetch,cache:null,now})).status,status);
assert.equal(await handlePlayoffLive(new Request('https://api.sweater.win/api/other'),{},null,{fetcher:noFetch,now}),null);
assert.equal((await handlePlayoffLive(request,{},null,{fetcher:async()=>{throw Error('private upstream details');},cache:null,now})).status,503);
console.log('PASS live hockey model: prior preservation, score/clock effects, symmetry, overtime, bounds, final/scheduled states, strict joins, unavailable data, client validation and edge cache/CORS');
