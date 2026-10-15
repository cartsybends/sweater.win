import {COMMUNITY_MODEL as M} from '../../static/community-games/model.mjs';
import {loadSchedule} from './existing-api.mjs';

const initialized=new WeakMap(),encoder=new TextEncoder();
const fail=(status,message)=>Object.assign(new Error(message),{status});
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const configured=env=>!!env.DB&&typeof env.SWEATER_ANALYTICS_PASSWORD==='string'&&env.SWEATER_ANALYTICS_PASSWORD.length>=32;
async function digest(env,value){const key=await crypto.subtle.importKey('raw',encoder.encode(env.SWEATER_ANALYTICS_PASSWORD),{name:'HMAC',hash:'SHA-256'},false,['sign']);return [...new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(value)))].map(v=>v.toString(16).padStart(2,'0')).join('');}
async function schema(env){
  if(!initialized.has(env.DB))initialized.set(env.DB,env.DB.batch([
    env.DB.prepare('CREATE TABLE IF NOT EXISTS sweater_grid_answers (visitor_hash TEXT NOT NULL,criterion TEXT NOT NULL,puzzle TEXT NOT NULL,player_id INTEGER NOT NULL,received_at INTEGER NOT NULL,PRIMARY KEY(visitor_hash,criterion))'),
    env.DB.prepare('CREATE INDEX IF NOT EXISTS sweater_grid_answer_age ON sweater_grid_answers(received_at)'),
    env.DB.prepare('CREATE TABLE IF NOT EXISTS sweater_analytics_limits (key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL)'),
  ]).catch(e=>{initialized.delete(env.DB);throw e;}));
  await initialized.get(env.DB);
}
export async function pruneGridPopularity(env){if(!configured(env))return;await schema(env);await env.DB.prepare('DELETE FROM sweater_grid_answers WHERE received_at < ?').bind(Date.now()-365*86400000).run();}
export function gridVotes(body,schedule){
  if(!body||Object.keys(body).some(k=>!['visitor','puzzle','guesses','variant','day'].includes(k))||!uuid.test(body.visitor||'')||!['daily','unlimited'].includes(body.variant)||!/^\d{4}-\d{2}-\d{2}$/.test(body.day||''))throw fail(400,'Invalid Grid run');
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const yesterday=new Date(Date.parse(today+'T12:00:00Z')-86400000).toISOString().slice(0,10);
  if(body.day!==today&&body.day!==yesterday)throw fail(400,'Only recent runs can contribute answers');
  const data=schedule.community,target=data?.grid?.find(t=>t.id===body.puzzle);
  if(!target)throw fail(400,'Unknown Grid puzzle');
  if(body.variant==='daily'&&schedule.grid_days?.[body.day]?.id!==target.id)throw fail(400,'That is not the scheduled Grid');
  if(!Array.isArray(body.guesses)||body.guesses.length>13)throw fail(400,'Invalid Grid actions');
  let state;try{state=M.grid(target,body.guesses,data);}catch(e){throw fail(400,e.message);}
  if(!state.over)throw fail(400,'Finish the Grid first');
  return state.cells.flatMap((id,cell)=>id===null?[]:[{criterion:M.criterion(target,cell),player:id,puzzle:target.id}]);
}
export async function handleGridPopularity(request,env){
  const url=new URL(request.url);if(!['/api/grid/answers','/api/grid/popularity'].includes(url.pathname))return null;
  let cors={};const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store',...cors}});
  try{
    const origin=request.headers.get('Origin'),allowed=['https://sweater.win','https://www.sweater.win',...String(env.ALLOWED_ORIGINS||'').split(',').map(s=>s.trim()).filter(Boolean)];
    if(origin&&!allowed.includes(origin)||request.method!=='GET'&&!origin)throw fail(403,'Origin not allowed');
    cors={'Access-Control-Allow-Origin':origin||'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type','Vary':'Origin'};
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:cors});
    if(!configured(env))return json({collecting:false,criteria:{}},request.method==='GET'?200:503);
    await schema(env);
    if(url.pathname==='/api/grid/popularity'&&request.method==='GET'){
      const rows=(await env.DB.prepare('SELECT criterion,player_id,COUNT(*) AS n FROM sweater_grid_answers WHERE received_at>=? GROUP BY criterion,player_id').bind(Date.now()-365*86400000).all()).results;
      const criteria={};for(const r of rows){const record=criteria[r.criterion]||={total:0,counts:{}};record.total+=r.n;record.counts[r.player_id]=r.n;}
      return json({collecting:true,minimum:100,criteria});
    }
    if(url.pathname!=='/api/grid/answers'||request.method!=='POST')throw fail(405,'Method not allowed');
    if(Number(request.headers.get('Content-Length')||0)>8192)throw fail(413,'Request too large');
    const text=await request.text();if(text.length>8192)throw fail(413,'Request too large');let body;try{body=JSON.parse(text);}catch{throw fail(400,'Invalid JSON');}
    const votes=gridVotes(body,await loadSchedule(env)),now=Date.now(),bucket=Math.floor(now/60000),key='grid:'+bucket+':'+await digest(env,'grid-rate:'+(request.headers.get('CF-Connecting-IP')||'unknown'));
    await env.DB.prepare('INSERT INTO sweater_analytics_limits(key,count,expires) VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1').bind(key,(bucket+1)*60000).run();
    if((await env.DB.prepare('SELECT count FROM sweater_analytics_limits WHERE key=?').bind(key).first()).count>30)throw fail(429,'Too many requests');
    const visitor=await digest(env,'grid-visitor:'+body.visitor);
    if(votes.length)await env.DB.batch(votes.map(v=>env.DB.prepare('INSERT OR IGNORE INTO sweater_grid_answers(visitor_hash,criterion,puzzle,player_id,received_at) VALUES (?,?,?,?,?)').bind(visitor,v.criterion,v.puzzle,v.player,now)));
    return json({ok:true});
  }catch(e){if(!e.status)console.error('Grid popularity is temporarily unavailable');return json({error:e.status?e.message:'Grid popularity is temporarily unavailable'},e.status||503);}
}
