import {currentTime} from './nhl-clock.mjs';
import {penaltyTimeline,penaltyContext,penaltyScoreMatches} from './penalty-state.mjs';
import {liveSnapshot} from './playoff-live-model.mjs';
import {collectLiveMarket} from './playoff-live-market.mjs';
import {retainMarketQuote} from './market-history.mjs';

const FEED='https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json';
const SCORE='https://api-web.nhle.com/v1/score/';
const pending=new Map();
const day=now=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(now));
export async function handlePlayoffLive(request,env,ctx,{fetcher=fetch,cache=globalThis.caches?.default,now=Date.now()}={}){
 const url=new URL(request.url);if(url.pathname!=='/api/playoffs/live')return null;
 const origin=request.headers.get('Origin'),allowed=['https://sweater.win','https://www.sweater.win',...String(env.ALLOWED_ORIGINS||'').split(',').map(s=>s.trim()).filter(Boolean)];
 if(origin&&!allowed.includes(origin))return Response.json({error:'Origin not allowed'},{status:403});
 const headers={'Access-Control-Allow-Origin':origin||'*','Access-Control-Allow-Methods':'GET,OPTIONS','Vary':'Origin','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
 const json=(body,status=200)=>Response.json(body,{status,headers});
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers});
 if(request.method!=='GET')return json({error:'Method not allowed'},405);
 const includePenalties=url.searchParams.get('penalties')==='1';
 const date=url.searchParams.get('date')||day(now),today=Date.parse(day(now)+'T12:00:00Z');
 const parsed=Date.parse(date+'T12:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(parsed)||new Date(parsed).toISOString().slice(0,10)!==date||Math.abs(parsed-today)>86400000)return json({error:'Choose yesterday, today or tomorrow'},400);
 const key=new Request('https://api.sweater.win/api/playoffs/live?date='+date+(includePenalties?'&penalties=1':''));
 try{
  const saved=await cache?.match(key);
  if(saved){const data=await saved.json();if(now-Date.parse(data.checked_at)<30000)return json(data);}
  const load=async()=>{
   const get=async(address,ttl,timeout=8000)=>{
    const cacheKey=new Request(address),saved=await cache?.match(cacheKey);
    if(saved&&now-Number(saved.headers.get('X-Sweater-Cached-At'))<ttl*1000)return {data:await saved.json(),observed_at:new Date(Number(saved.headers.get('X-Sweater-Cached-At'))).toISOString()};
    const response=await fetcher(address,{signal:AbortSignal.timeout(timeout),redirect:'manual',cache:'no-store'});
    if(!response.ok)throw new Error('Upstream unavailable');
    const data=await response.json();
    if(cache)await cache.put(cacheKey,Response.json(data,{headers:{'Cache-Control':'public,max-age='+ttl,'X-Sweater-Cached-At':String(now)}}));
    return {data,observed_at:new Date(now).toISOString()};
   };
   const [{data:score},{data:feed}]=await Promise.all([get(SCORE+date,30),get(FEED,60)]);
   if(!Array.isArray(score.games)||score.games.length>16||!Array.isArray(feed.games)||feed.games.length>400||!Number.isFinite(Date.parse(feed.checked_at))||Date.parse(feed.checked_at)>now+300000)throw new Error('Invalid upstream feed');
   const baseline=new Map(feed.games.map(g=>[g.id,g])),at=new Date(now).toISOString(),games=[];
   for(const raw of score.games){
    const game=baseline.get(raw.id);if(!game)continue;
    try{games.push(liveSnapshot(raw,game,at));}catch{games.push({id:game.id,home:game.home,away:game.away,start:game.start,state:game.state,at,status:'unavailable',reason:'feed_unavailable'});}
   }
   // Independent NHL and bookmaker checks share a bounded enrichment window.
   const marketDeadline=Date.now()+2500,penaltyDeadline=Date.now()+2800,marketGet=(address,ttl)=>get(address,ttl,Math.max(1,marketDeadline-Date.now()));
   await Promise.all(games.filter(g=>['LIVE','CRIT'].includes(g.state)).map(async g=>{
    const game=baseline.get(g.id),marketPromise=collectLiveMarket(game,marketGet,date,at);
    if(includePenalties)try{
     const {data:pbp}=await get(`https://api-web.nhle.com/v1/gamecenter/${g.id}/play-by-play`,15,Math.max(1,penaltyDeadline-Date.now()));
     const reference=score.games.find(r=>r.id===g.id),pbpTime=currentTime(pbp),scoreTime=currentTime(reference);
     // Never combine a newer score with an older, potentially released penalty.
     if(!penaltyScoreMatches(pbp)||!Number.isFinite(pbpTime)||pbpTime<scoreTime||pbp.homeTeam?.score<g.home_score||pbp.awayTeam?.score<g.away_score)throw Error('Penalty log catching up');
     const state=penaltyTimeline(pbp).at(pbpTime),updated=liveSnapshot(pbp,game,at,state);Object.assign(g,updated,{penalty:penaltyContext(state,pbp.periodDescriptor.periodType,pbp.gameType)});
    }catch{g.penalty_status='unavailable';}
    const market=await marketPromise;if(['LIVE','CRIT'].includes(g.state))g.market=await retainMarketQuote(game,market,env,{cache,now});
   }));
   const data={version:1,checked_at:at,refresh_seconds:30,games};
   if(cache)await cache.put(key,Response.json(data,{headers:{'Cache-Control':'public,max-age=30'}}));
   return data;
  };
  const scope=date+(includePenalties?'|penalties':'');if(!pending.has(scope))pending.set(scope,load().finally(()=>pending.delete(scope)));
  return json(await pending.get(scope));
 }catch{return json({error:'Live estimates temporarily unavailable'},503);}
}
