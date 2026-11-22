import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import vm from 'node:vm';
import {GAME_PREVIEW} from '../static/playoffs/preview-model.mjs';
import {handleGamePreview} from '../backend/src/game-preview.mjs';
import {handleTeamSchedule} from '../backend/src/team-schedule.mjs';
const root=new URL('../',import.meta.url),feed=JSON.parse(await readFile(new URL('playoffs_cache.json',root))),games=new Map(feed.games.map(g=>[g.id,g]));
const paths=await readdir(new URL('playoffs_lines/matchups/',root));let checks=0;
async function test(name,fn){await fn();checks++;console.log('PASS '+name);}
const id=2026020331,raw=JSON.parse(await readFile(new URL(`playoffs_lines/matchups/${id}.json`,root))),g=games.get(id)||{id,start:raw.start,home:raw.home,away:raw.away,date:raw.start.slice(0,10)},now=Math.max(Date.now(),Date.parse(raw.as_of));
await test('Every published in-window preview validates and preserves original team goal allocations',async()=>{
 let n=0;
 for(const file of paths){
  const d=JSON.parse(await readFile(new URL('playoffs_lines/matchups/'+file,root))),game=games.get(d.id);
  if(!game)continue;
  const states=d.matchups?.season?.map(m=>`${m.id}=${m.state}`).join(', ');
  assert(GAME_PREVIEW.validate(d,game,Math.max(now,Date.parse(d.as_of))),`${file} (season meeting states: ${states})`);
  n++;
 }
 assert(n>0);
});
await test('Corrupt identity, future features, invented players, duplicate units and false final scores are rejected',()=>{
 const team=raw.teams[raw.away],club=raw.away;assert(team.status!=='unavailable');
 for(const mutate of [d=>d.id++,d=>d.start='2026-01-01T00:00:00Z',d=>d.teams[club].source_game.date=g.date,
  d=>d.teams[club].stats_through=g.date,d=>d.teams[club].players[0].expected_goals+=1,
  d=>d.teams[club].units.f[0].players[0]=999999,d=>d.teams[club].units.f.push(d.teams[club].units.f[0]),
  d=>d.matchups.recent[0].ag=d.matchups.recent[0].hg,d=>d.matchups.wins[club]++,
  d=>d.matchups.recent.reverse(),d=>d.matchups.recent[0].type=1,d=>d.teams[club].players[0].stats.fo=101,d=>d.teams[club].special_teams.ranks={pp:0},d=>d.teams[club].special_teams.ranks={foo:1}]){
  const d=structuredClone(raw);mutate(d);assert.equal(GAME_PREVIEW.validate(d,g,now),null);
 }
});
const js=await readFile(new URL('static/playoffs/game-center.js',root),'utf8');
function functionSource(name){const start=js.indexOf('function '+name+'(');assert(start>=0);const end=js.indexOf('\nfunction ',start+1);return js.slice(start,end<0?js.length:end);}
await test('Goal details use the probability immediately after that goal rather than the latest state',()=>{
 const c=vm.createContext({poGCData:{forecast:{points:[{event_id:1,kind:'before_goal',home:40,away:60},{event_id:1,kind:'goal',home:65,away:35},{event_id:2,kind:'goal',home:95,away:5}]}},poGCGame:{home:'NYR',away:'MTL'},esc:s=>s,poGCPercent:n=>n+'%'});
 vm.runInContext(functionSource('poGCGoalPoint')+'\n'+functionSource('poGCGoalWin'),c);
 assert.equal(vm.runInContext('poGCGoalPoint({id:1,outcome:"goal"}).home',c),65);
 const html=vm.runInContext('poGCGoalWin({id:1,outcome:"goal"})',c);assert.match(html,/65%/);assert.match(html,/35%/);assert.doesNotMatch(html,/95%/);
 assert.equal(vm.runInContext('poGCGoalWin({id:3,outcome:"goal"})',c),'');
});
await test('Regulation rink includes neutral dots, both sets of circle markings and goalie trapezoids',()=>{
 const c=vm.createContext({});vm.runInContext(functionSource('poGCRinkMarks'),c);const html=vm.runInContext('poGCRinkMarks()',c);
 for(const [mark,count] of [['neutral-dot',4],['hashmark',16],['faceoff-mark',16],['trapezoid',4]])assert.equal((html.match(new RegExp('data-gc-'+mark,'g'))||[]).length,count);
});
await test('An official selected-game correction also updates the head-to-head win summary',()=>{
 const c=vm.createContext({poGCGame:{id:1},poGCData:{status:'final',state:'OFF',home:{score:2},away:{score:3},clock:{type:'OT'}}});vm.runInContext(functionSource('poGCEffectiveMeeting'),c);
 assert.equal(vm.runInContext('poGCEffectiveMeeting({id:1,hg:4,ag:1}).ag',c),3);
 assert.equal(vm.runInContext('poGCEffectiveMeeting({id:2,hg:4,ag:1}).ag',c),1);
});
const entries=new Map(),cache={async match(k){return entries.get(k.url)?.clone();},async put(k,r){entries.set(k.url,r.clone());}},req=(idValue=id,options={})=>new Request('https://api.sweater.win/api/playoffs/preview?id='+idValue,options);let calls=0,fail=false;
const options={cache,now,fetcher:async(url,init)=>{calls++;assert.equal(init.redirect,'manual');assert(init.signal);if(fail)throw Error('offline');return Response.json(url.endsWith('/playoffs_cache.json')?{games:[g]}:raw);}};
await test('Endpoint checks CORS, methods and NHL game identifiers before source requests',async()=>{
 assert.equal(await handleGamePreview(new Request('https://api.sweater.win/other'),{},null,options),null);
 assert.equal((await handleGamePreview(req('wat'),{},null,options)).status,400);
 assert.equal((await handleGamePreview(req(id,{headers:{Origin:'https://evil.example'}}),{},null,options)).status,403);
 assert.equal((await handleGamePreview(req(id,{method:'POST'}),{},null,options)).status,405);
 assert.equal((await handleGamePreview(req(id,{method:'OPTIONS'}),{},null,options)).status,204);assert.equal(calls,0);
});
await test('Coalesced requests share a compact cache and published-window gate',async()=>{
 const rs=await Promise.all(Array.from({length:5},()=>handleGamePreview(req(id,{headers:{Origin:'https://sweater.win'}}),{},null,options)));
 for(const r of rs){assert.equal(r.status,200);assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://sweater.win');assert.equal((await r.json()).id,id);}assert.equal(calls,2);
 assert.equal((await handleGamePreview(req(),{},null,options)).status,200);assert.equal(calls,2);
 assert.equal((await handleGamePreview(req(2026029999),{},null,options)).status,404);assert.equal(calls,2);
});
await test('An outage shows the last verified report with original timestamps and a delayed flag',async()=>{
 fail=true;const r=await handleGamePreview(req(),{},null,{...options,now:now+121000});assert.equal(r.status,200);const d=await r.json();assert.equal(d.stale,true);assert.equal(d.as_of,raw.as_of);
 assert.equal((await handleGamePreview(req(),{},null,{...options,cache:undefined,now:now+121000})).status,503);
 assert.equal((await handleGamePreview(req(),{},null,{...options,now:now+86401000})).status,503);
});
await test('Team schedule includes the full season and keeps complete scores through an NHL outage',async()=>{
 const season=20262027,at=Date.parse('2026-11-22T18:00:00Z');
 const base={season,gameType:2,startTimeUTC:'2026-11-23T00:00:00Z',gameState:'FUT',gameScheduleState:'OK',
  homeTeam:{abbrev:'EDM'},awayTeam:{abbrev:'VAN'}};
 const regular=Array.from({length:84},(_,i)=>({...base,id:2026020001+i}));
 regular[0]={...regular[0],gameState:'OFF',homeTeam:{abbrev:'EDM',score:2},awayTeam:{abbrev:'VAN',score:3},gameOutcome:{lastPeriodType:'SO'}};
 regular[1]={...regular[1],gameState:'OVER',homeTeam:{abbrev:'EDM',score:3},awayTeam:{abbrev:'VAN',score:2}};
 const doc={games:[...regular,{...base,gameType:1,id:2026010001},{...base,gameType:3,id:2026030111}]};
 const cacheRows=new Map(),cache={match:async key=>cacheRows.get(key.url)?.clone(),put:async (key,value)=>cacheRows.set(key.url,value.clone())};
 const request=new Request('https://api.sweater.win/api/playoffs/team-schedule?season=20262027&team=EDM',{headers:{Origin:'https://sweater.win'}});
 let calls=0;
 const fetcher=async url=>{
  calls++;assert.equal(url,'https://api-web.nhle.com/v1/club-schedule-season/EDM/20262027');return Response.json(doc);
 };
 const options={cache,fetcher,now:at};
 assert.equal((await handleTeamSchedule(new Request(request.url.replace('EDM','XXX')),{},options)).status,400);
 assert.equal(calls,0);
 const replies=await Promise.all([handleTeamSchedule(request,{},options),handleTeamSchedule(request,{},options)]);
 assert.equal(calls,1);
 assert.equal(replies[0].headers.get('Access-Control-Allow-Origin'),'https://sweater.win');
 const saved=await replies[0].json();
 assert.equal(saved.games.length,85);
 assert.deepEqual(saved.games.slice(0,3).map(g=>[g.status,g.hg,g.ag,g.end]),[['final',2,3,'SO'],['pending',3,2,null],['scheduled',null,null,null]]);
 assert.equal((await handleTeamSchedule(request,{},{...options,now:at+1000})).status,200);
 assert.equal(calls,1);
 const partial=async()=>Response.json({games:regular.slice(0,83)});
 const stale=await (await handleTeamSchedule(request,{},{cache,fetcher:partial,now:at+121000})).json();
 assert.deepEqual(stale,{...saved,stale:true});
 assert.equal((await handleTeamSchedule(request,{},{cache:null,fetcher:partial,now:at+121000})).status,503);
});
console.log(checks+' preview checks passed');
