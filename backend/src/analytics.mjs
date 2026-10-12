import { dashboard, loginPage } from './dashboard.mjs';

export const MODES = {
  classic:'Classic', statline:'Stat Line', team:'Guess the Team', journey:'Journey', blur:'Blur',
  number:'Sweater #', roster:'Roster Recall', draft:'Draft Day', map:'Birthplace', conn:'Connections',
  rank:"Rank ’Em", puck:'Puck Drop', shoot:'Shootout', overtime:'Overtime', truths:'Two Truths',
  hlt:'Team Higher or Lower', season:'Mystery Season', playoff:'Playoff Run', trophy:'Trophy Case',
  mroster:'Mystery Roster', cups:'Playoff History', whoscored:'Who Scored?', edgespeed:'Speed Trap',
  edgeshot:'Hardest Shot', edgemap:'Shot Map', edgebuild:'Build a Player', edgerush:'The Rush',
  party:'Party Mode', teams:'Teams', team_best:'Teams · Best Lineup', team_guess:'Teams · Guess the Player',
  team_higher:'Teams · Higher or Lower', team_mystery:'Teams · Mystery Season', hl:'Higher or Lower', hl_goals:'Higher or Lower · Goals',
  hl_assists:'Higher or Lower · Assists', hl_points:'Higher or Lower · Points', hl_pim:'Higher or Lower · PIM',
  hl_gp:'Higher or Lower · Games', hl_height:'Higher or Lower · Height', hl_weight:'Higher or Lower · Weight', hl_age:'Higher or Lower · Age'
};
const VARIANTS = new Set(['daily','unlimited','archive','party']);
const KINDS = new Set(['mode_open','round_start','round_complete','engagement']);
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const COOKIE = '__Host-sweater-analytics';
const TTL = 6 * 3600;
const initialized = new WeakMap();
const encoder = new TextEncoder();
const fail = (status, message) => Object.assign(new Error(message), {status});
const configured = env => !!env.DB && typeof env.SWEATER_ANALYTICS_PASSWORD === 'string' && env.SWEATER_ANALYTICS_PASSWORD.length >= 32;
const security = {
  'Cache-Control':'no-store, private','X-Content-Type-Options':'nosniff',
  'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
  'Permissions-Policy':'camera=(), microphone=(), geolocation=()'
};
const json = (value, status=200, extra={}) => new Response(JSON.stringify(value), {status,headers:{...security,'Content-Type':'application/json',...extra}});

async function key(env) {
  return crypto.subtle.importKey('raw', encoder.encode(env.SWEATER_ANALYTICS_PASSWORD), {name:'HMAC',hash:'SHA-256'}, false, ['sign','verify']);
}
async function hmac(env, value) {
  const bytes = new Uint8Array(await crypto.subtle.sign('HMAC',await key(env),encoder.encode(value)));
  return [...bytes].map(v=>v.toString(16).padStart(2,'0')).join('');
}
function clock(now=Date.now()) {
  const p=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'America/Vancouver',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hourCycle:'h23'}).formatToParts(new Date(now)).map(p=>[p.type,p.value]));
  return {day:`${p.year}-${p.month}-${p.day}`,hour:Number(p.hour)};
}
function shift(day,n) {return new Date(Date.parse(day+'T12:00:00Z')+n*86400000).toISOString().slice(0,10);}
async function ensureSchema(env) {
  if (!initialized.has(env.DB)) {
    const promise=env.DB.batch([
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS sweater_analytics_events (
        id TEXT PRIMARY KEY, received_at INTEGER NOT NULL, day TEXT NOT NULL, hour INTEGER NOT NULL,
        mode TEXT NOT NULL, variant TEXT NOT NULL, kind TEXT NOT NULL, session_hash TEXT NOT NULL,
        round_hash TEXT, device TEXT NOT NULL, active_ms INTEGER NOT NULL DEFAULT 0, won INTEGER
      )`),
      env.DB.prepare('CREATE INDEX IF NOT EXISTS sweater_analytics_date ON sweater_analytics_events(day,mode)'),
      env.DB.prepare('CREATE INDEX IF NOT EXISTS sweater_analytics_expiry ON sweater_analytics_events(received_at)'),
      env.DB.prepare(`CREATE UNIQUE INDEX IF NOT EXISTS sweater_analytics_round ON sweater_analytics_events(session_hash,mode,variant,round_hash,kind) WHERE kind IN ('round_start','round_complete')`),
      env.DB.prepare('CREATE TABLE IF NOT EXISTS sweater_analytics_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL)')
    ]).catch(error=>{initialized.delete(env.DB);throw error;});
    initialized.set(env.DB,promise);
  }
  await initialized.get(env.DB);
}
async function readBody(request, max=8192) {
  if (Number(request.headers.get('Content-Length')||0)>max) throw fail(413,'Request too large');
  const reader=request.body?.getReader(); if (!reader) throw fail(400,'Missing body');
  let size=0;const chunks=[];
  try {for (;;) {const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>max){await reader.cancel();throw fail(413,'Request too large');}chunks.push(value);}}
  finally {reader.releaseLock();}
  const result=new Uint8Array(size);let pos=0;for(const part of chunks){result.set(part,pos);pos+=part.length;}
  return new TextDecoder().decode(result);
}
function allowedOrigin(request,env) {
  const allowed=['https://sweater.win','https://www.sweater.win',...String(env.ALLOWED_ORIGINS||'').split(',').map(x=>x.trim()).filter(Boolean)];
  const origin=request.headers.get('Origin');
  if (!origin || !allowed.includes(origin)) throw fail(403,'Origin not allowed');
  return {'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type','Access-Control-Max-Age':'86400','Vary':'Origin'};
}
async function rate(request,env,scope,limit,seconds) {
  const now=Date.now(), bucket=Math.floor(now/(seconds*1000));
  const ip=request.headers.get('CF-Connecting-IP')||'unknown';
  const k=`${scope}:${bucket}:${await hmac(env,'rate:'+ip)}`;
  await env.DB.prepare('INSERT INTO sweater_analytics_limits(key,count,expires) VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1').bind(k,(bucket+1)*seconds*1000).run();
  const row=await env.DB.prepare('SELECT count FROM sweater_analytics_limits WHERE key=?').bind(k).first();
  await env.DB.prepare('DELETE FROM sweater_analytics_limits WHERE key IN (SELECT key FROM sweater_analytics_limits WHERE expires<? LIMIT 100)').bind(now).run();
  if(row.count>limit)throw fail(429,'Too many requests; try again shortly');
}
async function collect(request,env) {
  let body;try{body=JSON.parse(await readBody(request));}catch(e){if(e.status)throw e;throw fail(400,'Invalid JSON');}
  if(!body||typeof body!=='object'||Array.isArray(body))throw fail(400,'Invalid event');
  const allowed=new Set(['id','session','mode','variant','kind','round','device','active_ms','won']);
  if(Object.keys(body).some(k=>!allowed.has(k)))throw fail(400,'Unexpected event fields');
  if(['id','session','mode','variant','kind','device'].some(k=>typeof body[k]!=='string'))throw fail(400,'Invalid event');
  if(!UUID.test(body.id||'')||!UUID.test(body.session||'')||!Object.hasOwn(MODES,body.mode)||!VARIANTS.has(body.variant)||!KINDS.has(body.kind)||!['mobile','tablet','desktop'].includes(body.device))throw fail(400,'Invalid event');
  const isRound=body.kind==='round_start'||body.kind==='round_complete';
  if(isRound&&(typeof body.round!=='string'||!UUID.test(body.round)))throw fail(400,'Invalid round');
  const ms=body.kind==='engagement'?body.active_ms:0;
  if(!Number.isInteger(ms)||ms<0||ms>60000||body.kind==='engagement'&&ms===0)throw fail(400,'Invalid active time');
  if(body.kind==='round_complete'&&typeof body.won!=='boolean')throw fail(400,'Invalid result');
  await ensureSchema(env);await rate(request,env,'collect',120,60);
  const now=Date.now(),{day,hour}=clock(now),session=await hmac(env,'session:'+body.session);
  const round=isRound?await hmac(env,'round:'+body.session+':'+body.round):null;
  await env.DB.batch([
    env.DB.prepare('INSERT OR IGNORE INTO sweater_analytics_events(id,received_at,day,hour,mode,variant,kind,session_hash,round_hash,device,active_ms,won) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)').bind(body.id,now,day,hour,body.mode,body.variant,body.kind,session,round,body.device,ms,body.kind==='round_complete'?Number(body.won):null),
    env.DB.prepare('DELETE FROM sweater_analytics_events WHERE id IN (SELECT id FROM sweater_analytics_events WHERE received_at<? LIMIT 100)').bind(now-90*86400000)
  ]);
  return {ok:true};
}
async function authorized(request,env) {
  if(!configured(env))return false;
  const value=request.headers.get('Cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith(COOKIE+'='))?.slice(COOKIE.length+1);
  if(!value)return false;const parts=value.split('.');if(parts.length!==3)return false;
  const [expiry,nonce,signature]=parts;
  if(!/^\d{10}$/.test(expiry)||!UUID.test(nonce)||!/^[a-f0-9]{64}$/.test(signature))return false;
  const expires=Number(expiry),now=Math.floor(Date.now()/1000);if(expires<=now||expires>now+TTL)return false;
  const bytes=new Uint8Array(signature.match(/../g).map(x=>parseInt(x,16)));
  return crypto.subtle.verify('HMAC',await key(env),bytes,encoder.encode('cookie:'+expiry+'.'+nonce));
}
function sameOrigin(request) {
  if(request.headers.get('Origin')!==new URL(request.url).origin)throw fail(403,'Origin not allowed');
}
async function login(request,env) {
  sameOrigin(request);if(!configured(env))throw fail(503,'Analytics needs its private password configured');
  await ensureSchema(env);await rate(request,env,'login',10,900);
  const form=new URLSearchParams(await readBody(request,1024)),password=form.get('password')||'';
  const a=new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(password))),b=new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(env.SWEATER_ANALYTICS_PASSWORD)));
  let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];
  if(diff) return html(loginPage('That password did not match.'),401);
  const content=`${Math.floor(Date.now()/1000)+TTL}.${crypto.randomUUID()}`,token=content+'.'+await hmac(env,'cookie:'+content);
  return new Response(null,{status:303,headers:{...security,Location:'/analytics','Set-Cookie':`${COOKIE}=${token}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=${TTL}`}});
}
function html(content,status=200) {
  const nonce=crypto.randomUUID().replaceAll('-','');
  // Native form POSTs use a null Origin with no-referrer, which fails our CSRF check.
  // Keep the origin for this host's forms while suppressing cross-origin referrers.
  return new Response(content.replaceAll('__NONCE__',nonce),{status,headers:{...security,'Referrer-Policy':'same-origin','Content-Type':'text/html; charset=utf-8','Content-Security-Policy':`default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`}});
}
async function report(url,env) {
  const days=Number(url.searchParams.get('days')||7);if(![1,7,30,90].includes(days))throw fail(400,'Invalid date range');
  const to=clock().day,from=shift(to,1-days),variant=url.searchParams.get('variant')||'all';
  if(variant!=='all'&&!VARIANTS.has(variant))throw fail(400,'Invalid variant');
  await ensureSchema(env);
  const filter='day BETWEEN ? AND ?'+(variant==='all'?'':' AND variant=?'),args=variant==='all'?[from,to]:[from,to,variant];
  const queries=[
    `SELECT mode, SUM(kind='mode_open') opens, SUM(kind='round_start') starts, SUM(kind='round_complete') finishes, COUNT(DISTINCT session_hash) sessions, SUM(active_ms) active_ms FROM sweater_analytics_events WHERE ${filter} GROUP BY mode ORDER BY opens DESC`,
    `SELECT day, SUM(kind='mode_open') opens, SUM(kind='round_start') starts, SUM(kind='round_complete') finishes FROM sweater_analytics_events WHERE ${filter} GROUP BY day ORDER BY day`,
    `SELECT variant, SUM(kind='mode_open') opens, SUM(kind='round_start') starts FROM sweater_analytics_events WHERE ${filter} GROUP BY variant`,
    `SELECT device, COUNT(*) opens FROM sweater_analytics_events WHERE ${filter} AND kind='mode_open' GROUP BY device`,
    `SELECT COUNT(DISTINCT session_hash) sessions, MIN(day) first_day FROM sweater_analytics_events WHERE ${filter}`
  ];
  const res=await env.DB.batch(queries.map(q=>env.DB.prepare(q).bind(...args)));
  const cohortArgs=variant==='all'?[from,to,to]:[from,to,variant,to];
  const cohort=(await env.DB.prepare(`SELECT s.mode,COUNT(c.id) completed FROM sweater_analytics_events s LEFT JOIN sweater_analytics_events c ON c.session_hash=s.session_hash AND c.mode=s.mode AND c.variant=s.variant AND c.round_hash=s.round_hash AND c.kind='round_complete' AND c.day<=?${variant==='all'?3:4} WHERE s.kind='round_start' AND s.day BETWEEN ?1 AND ?2 ${variant==='all'?'':'AND s.variant=?3'} GROUP BY s.mode`).bind(...cohortArgs).all()).results;
  const completed=new Map(cohort.map(r=>[r.mode,r.completed]));
  const modes=res[0].results.map(r=>({...r,label:MODES[r.mode]||r.mode,completed_starts:completed.get(r.mode)||0,rounds_supported:r.mode!=='teams'&&!r.mode.startsWith('team_')}));
  return {from,to,days,variant,time_zone:'America/Vancouver',retention_days:90,modes,trend:res[1].results,variants:res[2].results,devices:res[3].results,sessions:res[4].results[0]?.sessions||0};
}
export async function handleAnalytics(request,env) {
  const url=new URL(request.url),path=url.pathname;
  if(path!=='/analytics'&&!path.startsWith('/analytics/')&&!path.startsWith('/api/analytics/'))return null;
  let cors={};
  try {
    if(path==='/api/analytics/status'||path==='/api/analytics/collect') {
      cors=allowedOrigin(request,env);
      if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{...security,...cors}});
      if(path==='/api/analytics/status'&&request.method==='GET') {
        if(!configured(env))return json({enabled:false},200,cors);
        await ensureSchema(env);return json({enabled:true},200,cors);
      }
      if(path==='/api/analytics/collect'&&request.method==='POST') {
        if(!configured(env))return json({enabled:false},503,cors);
        return json(await collect(request,env),200,cors);
      }
      throw fail(405,'Method not allowed');
    }
    if(path==='/analytics/login'&&request.method==='GET')return html(loginPage(configured(env)?'':'Set SWEATER_ANALYTICS_PASSWORD in Cloudflare to enable this dashboard.'));
    if(path==='/analytics/login'&&request.method==='POST')return await login(request,env);
    if(path==='/analytics/logout'&&request.method==='POST') {
      sameOrigin(request);return new Response(null,{status:303,headers:{...security,Location:'/analytics/login','Set-Cookie':`${COOKIE}=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0`}});
    }
    if(!await authorized(request,env)) {
      if(path.startsWith('/api/'))return json({error:'Sign in required'},401);
      return new Response(null,{status:303,headers:{...security,Location:'/analytics/login'}});
    }
    if(path==='/analytics'&&request.method==='GET')return html(dashboard);
    if(path==='/api/analytics/report'&&request.method==='GET')return json(await report(url,env));
    throw fail(404,'Not found');
  } catch(error) {if(!error.status)console.error('Analytics request failed');return json({error:error.status?error.message:'Analytics is temporarily unavailable'},error.status||503,cors);}
}

export async function purgeAnalytics(env) {
  if(!env.DB)return;
  await ensureSchema(env);
  await env.DB.batch([
    env.DB.prepare('DELETE FROM sweater_analytics_events WHERE received_at<?').bind(Date.now()-90*86400000),
    env.DB.prepare('DELETE FROM sweater_analytics_limits WHERE expires<?').bind(Date.now())
  ]);
}
