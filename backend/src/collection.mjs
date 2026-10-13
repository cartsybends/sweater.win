export const RETENTION_DAYS=365;
export const BATCH_SIZE=5;
export const USAGE_VERSION=2;
export const USAGE_KINDS=new Set(['site_visit','page_view','page_exit','mode_open','round_start','round_step','round_exit','round_complete','engagement','share','interaction','performance','error']);
export const BROWSERS=['chrome','safari','firefox','edge','duckduckgo','opera','samsung','other','unknown'];
export const SYSTEMS=['ios','android','windows','macos','linux','other','unknown'];
export const SOURCES=['direct','google','bing','duckduckgo','yahoo','instagram','tiktok','youtube','facebook','x','reddit','discord','referral','other','unknown'];
export const ACTIONS=['favorite_add','favorite_remove','library_filter','stats_open','leaderboard_open','help_open','profile_open','archive_open','challenge_copy','team_select','party_create','party_join','javascript','promise','resource'];
const UUID=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const OLD_FIELDS=['id','session','mode','variant','kind','round','device','active_ms','won'];
const EXTRA_FIELDS=['version','visitor','visit','from_mode','browser','os','source','campaign','medium','theme','viewport','build','step','correct','score','elapsed_ms','response_ms','action','team','load_ms','ttfb_ms','lcp_ms','cls'];
const fail=message=>Object.assign(new Error(message),{status:400});
const label=/^[a-z0-9][a-z0-9._-]{0,59}$/i;
const teams=new Set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split(' '));
function integer(value,min,max){return Number.isInteger(value)&&value>=min&&value<=max;}
export function validateEvents(raw,modes,variants){
  let rows=[raw];
  if(raw&&typeof raw==='object'&&!Array.isArray(raw)&&Object.hasOwn(raw,'events')){
    if(Object.keys(raw).length!==1||!Array.isArray(raw.events)||raw.events.length<1||raw.events.length>BATCH_SIZE)throw fail('Invalid event batch');
    rows=raw.events;
  }
  for(const b of rows){
    if(!b||typeof b!=='object'||Array.isArray(b))throw fail('Invalid event');
    const enhanced=b.version===USAGE_VERSION,allowed=new Set(enhanced?[...OLD_FIELDS,...EXTRA_FIELDS]:OLD_FIELDS);
    if(Object.keys(b).some(k=>!allowed.has(k)))throw fail('Unexpected event fields');
    if(['id','session','mode','variant','kind','device'].some(k=>typeof b[k]!=='string'))throw fail('Invalid event');
    if(!UUID.test(b.id)||!UUID.test(b.session)||!Object.hasOwn(modes,b.mode)||!variants.has(b.variant)||!USAGE_KINDS.has(b.kind)||!['mobile','tablet','desktop'].includes(b.device))throw fail('Invalid event');
    if(!enhanced&&!['mode_open','round_start','round_complete','engagement'].includes(b.kind))throw fail('Unsupported event version');
    const roundKind=['round_start','round_step','round_exit','round_complete'].includes(b.kind);
    if((roundKind&&!UUID.test(b.round||''))||(b.round!==undefined&&(typeof b.round!=='string'||!UUID.test(b.round))))throw fail('Invalid round');
    if(b.kind==='engagement'&&!integer(b.active_ms,1,60000))throw fail('Invalid active time');
    if(b.active_ms!==undefined&&!integer(b.active_ms,0,60000))throw fail('Invalid active time');
    if(b.kind==='round_complete'&&typeof b.won!=='boolean'&&!(enhanced&&b.won===null))throw fail('Invalid result');
    if(enhanced){
      if(typeof b.visitor!=='string'||!UUID.test(b.visitor)||typeof b.visit!=='string'||!UUID.test(b.visit))throw fail('Invalid anonymous visit');
      for(const [field,choices]of [['browser',BROWSERS],['os',SYSTEMS],['source',SOURCES],['theme',['light','dark','unknown']],['viewport',['small','medium','large','wide','unknown']],['action',ACTIONS]])if(b[field]!==undefined&&!choices.includes(b[field]))throw fail('Invalid '+field);
      if(b.from_mode!==undefined&&(typeof b.from_mode!=='string'||!Object.hasOwn(modes,b.from_mode)))throw fail('Invalid previous mode');
      for(const field of ['campaign','medium'])if(b[field]!==undefined&&(typeof b[field]!=='string'||!label.test(b[field])))throw fail('Invalid traffic label');
      if(b.build!==undefined&&(typeof b.build!=='string'||!/^\d{1,5}$/.test(b.build)))throw fail('Invalid build');
      if(b.team!==undefined&&!teams.has(b.team))throw fail('Invalid team');
      if(b.kind==='round_step'&&!integer(b.step,1,10000))throw fail('Invalid step');
      if(b.step!==undefined&&!integer(b.step,0,10000))throw fail('Invalid step');
      if(b.correct!==undefined&&typeof b.correct!=='boolean')throw fail('Invalid answer outcome');
      if(b.score!==undefined&&(typeof b.score!=='number'||!Number.isFinite(b.score)||Math.abs(b.score)>1000000))throw fail('Invalid score');
      for(const field of ['elapsed_ms','response_ms'])if(b[field]!==undefined&&!integer(b[field],0,604800000))throw fail('Invalid duration');
      for(const field of ['load_ms','ttfb_ms','lcp_ms'])if(b[field]!==undefined&&!integer(b[field],0,120000))throw fail('Invalid performance sample');
      if(b.cls!==undefined&&(typeof b.cls!=='number'||!Number.isFinite(b.cls)||b.cls<0||b.cls>10))throw fail('Invalid layout shift');
      if(b.kind==='error'&&!['javascript','promise','resource'].includes(b.action))throw fail('Invalid error category');
      if(b.kind==='interaction'&&(!b.action||['javascript','promise','resource'].includes(b.action)))throw fail('Invalid interaction');
    }
  }
  return rows;
}
export function schemaStatements(db){
  return [
    'CREATE INDEX IF NOT EXISTS sweater_analytics_round_events ON sweater_analytics_events(session_hash,mode,variant,round_hash,kind)',
    `CREATE TABLE IF NOT EXISTS sweater_analytics_details (
      event_id TEXT PRIMARY KEY, visitor_hash TEXT, visit_hash TEXT, from_mode TEXT,
      browser TEXT, os TEXT, source TEXT, campaign TEXT, medium TEXT, country TEXT,
      theme TEXT, viewport TEXT, build TEXT, step INTEGER, correct INTEGER, score REAL,
      elapsed_ms INTEGER, response_ms INTEGER, action TEXT, team TEXT,
      load_ms INTEGER, ttfb_ms INTEGER, lcp_ms INTEGER, cls REAL
    )`,
    'CREATE INDEX IF NOT EXISTS sweater_analytics_visitor_events ON sweater_analytics_details(visitor_hash,event_id)',
    'CREATE INDEX IF NOT EXISTS sweater_analytics_visit_events ON sweater_analytics_details(visit_hash,event_id)',
    `CREATE TABLE IF NOT EXISTS sweater_analytics_sessions (
      session_hash TEXT PRIMARY KEY, visitor_hash TEXT, first_at INTEGER NOT NULL,last_at INTEGER NOT NULL,
      first_day TEXT NOT NULL,last_day TEXT NOT NULL,entry_mode TEXT NOT NULL,last_mode TEXT NOT NULL,
      device TEXT,browser TEXT,os TEXT,source TEXT,country TEXT
    )`,
    'CREATE INDEX IF NOT EXISTS sweater_analytics_session_recency ON sweater_analytics_sessions(last_at)',
    `CREATE TABLE IF NOT EXISTS sweater_analytics_visitors (
      visitor_hash TEXT PRIMARY KEY,first_at INTEGER NOT NULL,last_at INTEGER NOT NULL,
      first_day TEXT NOT NULL,last_day TEXT NOT NULL
    )`,
    'CREATE INDEX IF NOT EXISTS sweater_analytics_visitor_cohort ON sweater_analytics_visitors(first_day)',
    'CREATE INDEX IF NOT EXISTS sweater_analytics_visitor_recency ON sweater_analytics_visitors(last_at)',
    'CREATE TABLE IF NOT EXISTS sweater_analytics_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)'
  ].map(sql=>db.prepare(sql));
}
export function browserInfo(request){
  const ua=request.headers.get('User-Agent')||'';
  const browser=!ua?'unknown':/DuckDuckGo/i.test(ua)?'duckduckgo':/Edg/i.test(ua)?'edge':/SamsungBrowser/i.test(ua)?'samsung':/OPR|Opera/i.test(ua)?'opera':/Firefox|FxiOS/i.test(ua)?'firefox':/Chrome|CriOS/i.test(ua)?'chrome':/Safari/i.test(ua)?'safari':'other';
  const os=!ua?'unknown':/iPhone|iPad|iPod/i.test(ua)?'ios':/Android/i.test(ua)?'android':/Windows/i.test(ua)?'windows':/Macintosh|Mac OS/i.test(ua)?'macos':/Linux/i.test(ua)?'linux':'other';
  const country=/^[A-Z]{2}$/.test(request.cf?.country||'')?request.cf.country:'unknown';
  return {browser,os,country};
}
export async function eventStatements(db,b,request,hash,session){
  const enhanced=b.version===USAGE_VERSION,info=browserInfo(request),visitor=enhanced?await hash('visitor:'+b.visitor):null,visit=enhanced?await hash('visit:'+b.visit):null;
  const values=[b.id,visitor,visit,b.from_mode??null,b.browser??info.browser,b.os??info.os,b.source??'unknown',b.campaign??null,b.medium??null,info.country,b.theme??'unknown',b.viewport??'unknown',b.build??null,b.step??null,b.correct===undefined?null:Number(b.correct),b.score??null,b.elapsed_ms??null,b.response_ms??null,b.action??null,b.team??null,b.load_ms??null,b.ttfb_ms??null,b.lcp_ms??null,b.cls??null];
  const detail=db.prepare(`INSERT OR IGNORE INTO sweater_analytics_details SELECT ${values.map(()=>'?').join(',')} WHERE EXISTS (SELECT 1 FROM sweater_analytics_events WHERE id=? AND session_hash=?)`).bind(...values,b.id,session);
  const summary=db.prepare(`INSERT INTO sweater_analytics_sessions(session_hash,visitor_hash,first_at,last_at,first_day,last_day,entry_mode,last_mode,device,browser,os,source,country)
    SELECT e.session_hash,d.visitor_hash,e.received_at,e.received_at,e.day,e.day,e.mode,e.mode,e.device,d.browser,d.os,d.source,d.country
    FROM sweater_analytics_events e JOIN sweater_analytics_details d ON d.event_id=e.id WHERE e.id=? AND e.session_hash=?
    ON CONFLICT(session_hash) DO UPDATE SET visitor_hash=COALESCE(visitor_hash,excluded.visitor_hash),last_at=MAX(last_at,excluded.last_at),
      last_day=CASE WHEN excluded.last_at>=last_at THEN excluded.last_day ELSE last_day END,
      last_mode=CASE WHEN excluded.last_at>=last_at THEN excluded.last_mode ELSE last_mode END`).bind(b.id,session);
  const visitorRow=db.prepare(`INSERT INTO sweater_analytics_visitors(visitor_hash,first_at,last_at,first_day,last_day)
    SELECT d.visitor_hash,e.received_at,e.received_at,e.day,e.day FROM sweater_analytics_events e JOIN sweater_analytics_details d ON d.event_id=e.id
    WHERE e.id=? AND e.session_hash=? AND d.visitor_hash IS NOT NULL
    ON CONFLICT(visitor_hash) DO UPDATE SET last_at=MAX(last_at,excluded.last_at),last_day=CASE WHEN excluded.last_at>=last_at THEN excluded.last_day ELSE last_day END`).bind(b.id,session);
  return [detail,summary,visitorRow];
}
export function pruneStatements(db,now,limit=100){
  const cutoff=now-RETENTION_DAYS*86400000,tail=limit?` LIMIT ${limit}`:'';
  return [
    db.prepare(`DELETE FROM sweater_analytics_details WHERE event_id IN (SELECT id FROM sweater_analytics_events WHERE received_at<?${tail})`).bind(cutoff),
    db.prepare(`DELETE FROM sweater_analytics_events WHERE id IN (SELECT id FROM sweater_analytics_events WHERE received_at<?${tail})`).bind(cutoff),
    db.prepare(`DELETE FROM sweater_analytics_sessions WHERE session_hash IN (SELECT session_hash FROM sweater_analytics_sessions WHERE last_at<?${tail})`).bind(cutoff),
    db.prepare(`DELETE FROM sweater_analytics_visitors WHERE visitor_hash IN (SELECT visitor_hash FROM sweater_analytics_visitors WHERE last_at<?${tail})`).bind(cutoff)
  ];
}
