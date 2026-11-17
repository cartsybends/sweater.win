import {goalLocationCandidates,goalLocationCorrections} from './game-center-locations.mjs';
import {gameCenter} from './game-center-model.mjs';
const feedURL='https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json',pending=new Map();
export async function handleGameCenter(request,env,ctx,{fetcher=fetch,cache=globalThis.caches?.default,now=Date.now()}={}){
 const url=new URL(request.url);if(url.pathname!=='/api/playoffs/game')return null;
 const origin=request.headers.get('Origin'),allowed=['https://sweater.win','https://www.sweater.win',...String(env.ALLOWED_ORIGINS||'').split(',').filter(Boolean)];
 if(origin&&!allowed.includes(origin))return Response.json({error:'Origin not allowed'},{status:403});
 const headers={'Access-Control-Allow-Origin':origin||'*','Access-Control-Allow-Methods':'GET,OPTIONS','Vary':'Origin','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},json=(body,status=200)=>Response.json(body?.status==='live'?{...body,refresh_seconds:url.searchParams.get('refresh')==='5'?5:15}:body,{status,headers});
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers});if(request.method!=='GET')return json({error:'Method not allowed'},405);
 const id=url.searchParams.get('id');if(!/^20\d{2}0[23]\d{4}$/.test(id||''))return json({error:'Invalid NHL game'},400);
 const key=new Request('https://api.sweater.win/api/playoffs/game?id='+id),lastKey=new Request('https://api.sweater.win/api/playoffs/game-last?id='+id);
 try{
  const saved=await cache?.match(key);if(saved){const d=await saved.json();if(now-Date.parse(d.checked_at)<d.refresh_seconds*1000)return json(d);}
  const load=async()=>{
   const get=async(address,ttl,timeout=8000,staleSeconds=0)=>{
    const k=new Request(address),c=await cache?.match(k),age=c?now-Number(c.headers.get('X-Sweater-Cached-At')):Infinity;if(c&&age>=0&&age<ttl*1000)return c.json();
    try{const r=await fetcher(address,{redirect:'manual',cache:'no-store',signal:AbortSignal.timeout(timeout)});if(!r.ok)throw Error('Source unavailable');const text=await r.text();if(text.length>2500000)throw Error('Oversized feed');const d=JSON.parse(text);if(cache)await cache.put(k,Response.json(d,{headers:{'Cache-Control':'public,max-age='+Math.max(ttl,staleSeconds),'X-Sweater-Cached-At':String(now)}}));return d;}
    catch(error){if(c&&staleSeconds&&age>=0&&age<staleSeconds*1000)return c.json();throw error;}
   };
   const feed=await get(feedURL,60);if(!Array.isArray(feed.games)||feed.games.length>400||!Number.isFinite(Date.parse(feed.checked_at))||Date.parse(feed.checked_at)>now+300000)throw Error('Invalid baseline');
   const baseline=feed.games.find(g=>String(g.id)===id);if(!baseline)return {error:'Game is outside the published game window',status:404};
   const raw=await get(`https://api-web.nhle.com/v1/gamecenter/${id}/play-by-play`,5),at=new Date(now).toISOString();let data=gameCenter(raw,baseline,at);
   // Optional event-level corroboration must never interrupt the NHL clock/feed.
   const espnID=baseline.market?.source_url?.match(/^https:\/\/www\.espn\.com\/nhl\/game\/_\/gameId\/(\d{1,12})$/)?.[1];
   if(espnID&&goalLocationCandidates(data,baseline).length)try{
    const summary=await get('https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event='+espnID,30,2000,86400),corrections=goalLocationCorrections(raw,baseline,data,summary,espnID);
    if(corrections.size)data=gameCenter(raw,baseline,at,corrections);
   }catch{}
   if(cache){await cache.put(key,Response.json(data,{headers:{'Cache-Control':'public,max-age='+data.refresh_seconds}}));await cache.put(lastKey,Response.json(data,{headers:{'Cache-Control':'public,max-age=86400'}}));}return data;
  };
  if(!pending.has(id))pending.set(id,load().finally(()=>pending.delete(id)));const data=await pending.get(id);return data.error?json({error:data.error},data.status):json(data);
 }catch{
  try{const saved=await cache?.match(lastKey);if(saved){const data=await saved.json();if(now-Date.parse(data.checked_at)<86400000)return json({...data,stale:true});}}catch{}
  return json({error:'NHL game feed temporarily unavailable'},503);
 }
}
