import {GAME_PREVIEW} from '../../static/playoffs/preview-model.mjs';
const FEED='https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json';
const PREVIEWS='https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_lines/matchups/';
const pending=new Map();
export async function handleGamePreview(request,env,ctx,{fetcher=fetch,cache=globalThis.caches?.default,now=Date.now()}={}){
 const url=new URL(request.url);if(url.pathname!=='/api/playoffs/preview')return null;
 const origin=request.headers.get('Origin'),allowed=['https://sweater.win','https://www.sweater.win',...String(env.ALLOWED_ORIGINS||'').split(',').map(s=>s.trim()).filter(Boolean)];
 if(origin&&!allowed.includes(origin))return Response.json({error:'Origin not allowed'},{status:403});
 const headers={'Access-Control-Allow-Origin':origin||'*','Access-Control-Allow-Methods':'GET,OPTIONS','Vary':'Origin','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},json=(body,status=200)=>Response.json(body,{status,headers});
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers});if(request.method!=='GET')return json({error:'Method not allowed'},405);
 const id=url.searchParams.get('id');if(!/^20\d{2}0[23]\d{4}$/.test(id||''))return json({error:'Invalid NHL game'},400);
 const key=new Request('https://api.sweater.win/api/playoffs/preview?id='+id),lastKey=new Request('https://api.sweater.win/api/playoffs/preview-last?id='+id);
 try{
  const cached=await cache?.match(key);if(cached){const data=await cached.json();if(now-Number(cached.headers.get('X-Sweater-Cached-At'))<120000)return json(data);}
  const load=async()=>{
   const get=async(address,ttl,max)=>{const k=new Request(address),saved=await cache?.match(k);if(saved&&now-Number(saved.headers.get('X-Sweater-Cached-At'))<ttl*1000)return saved.json();const response=await fetcher(address,{redirect:'manual',cache:'no-store',signal:AbortSignal.timeout(6500)});if(!response.ok)throw Error('Preview source unavailable');const text=await response.text();if(text.length>max)throw Error('Oversized preview');const value=JSON.parse(text);if(cache)await cache.put(k,Response.json(value,{headers:{'Cache-Control':'public,max-age='+ttl,'X-Sweater-Cached-At':String(now)}}));return value;};
   const feed=await get(FEED,60,2500000);if(!Array.isArray(feed.games)||feed.games.length>400)throw Error('Invalid game window');const g=feed.games.find(g=>String(g.id)===id);if(!g)return {error:'Game is outside the published window',status:404};
   const raw=await get(PREVIEWS+id+'.json',120,250000),data=GAME_PREVIEW.validate(raw,g,now);if(!data)throw Error('Invalid preview');
   if(cache){const response=()=>Response.json(data,{headers:{'Cache-Control':'public,max-age=86400','X-Sweater-Cached-At':String(now)}});await cache.put(key,response());await cache.put(lastKey,response());}
   return data;
  };
  if(!pending.has(id))pending.set(id,load().finally(()=>pending.delete(id)));const data=await pending.get(id);return data.error?json({error:data.error},data.status):json(data);
 }catch{try{const saved=await cache?.match(lastKey);if(saved&&now-Number(saved.headers.get('X-Sweater-Cached-At'))<86400000)return json({...await saved.json(),stale:true});}catch{}return json({error:'Lineups and matchup context are temporarily unavailable'},503);}
}
