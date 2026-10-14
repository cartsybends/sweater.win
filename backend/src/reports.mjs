import {RETENTION_DAYS,BROWSERS,SYSTEMS,SOURCES} from './collection.mjs';
const fail=message=>Object.assign(new Error(message),{status:400});
const validDay=day=>/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(Date.parse(day+'T12:00:00Z'))&&new Date(Date.parse(day+'T12:00:00Z')).toISOString().slice(0,10)===day;
const detailColumns='visitor_hash,visit_hash,from_mode,browser,os,source,campaign,medium,country,theme,viewport,build,step,correct,score,elapsed_ms,response_ms,action,team,load_ms,ttfb_ms,lcp_ms,cls'.split(',');
const projection='e.*,'+detailColumns.map(k=>'d.'+k).join(',');
const join='FROM sweater_analytics_events e LEFT JOIN sweater_analytics_details d ON d.event_id=e.id';
const ratio=(a,b)=>b?100*a/b:null;
export async function usageReport(url,env,labels,variants,clock,shift){
  const today=clock().day,p=url.searchParams,custom=p.has('from')||p.has('to');
  let days=Number(p.get('days')||7),to=today,from;
  if(custom){
    from=p.get('from')||'';to=p.get('to')||'';
    if(!validDay(from)||!validDay(to)||from>to||to>today)throw fail('Invalid date range');
    days=Math.round((Date.parse(to+'T12:00:00Z')-Date.parse(from+'T12:00:00Z'))/86400000)+1;
    if(days<1||days>RETENTION_DAYS||from<shift(today,1-RETENTION_DAYS))throw fail('Select a range within the last year');
  }else{
    if(![1,7,30,90,365].includes(days))throw fail('Invalid date range');
    from=shift(to,1-days);
  }
  const filters={variant:p.get('variant')||'all',mode:p.get('mode')||'all',device:p.get('device')||'all',browser:p.get('browser')||'all',source:p.get('source')||'all',country:p.get('country')||'all'};
  if(filters.variant!=='all'&&!variants.has(filters.variant)||filters.mode!=='all'&&!Object.hasOwn(labels,filters.mode)||filters.device!=='all'&&!['mobile','tablet','desktop'].includes(filters.device)||filters.browser!=='all'&&!BROWSERS.includes(filters.browser)||filters.source!=='all'&&!SOURCES.includes(filters.source)||filters.country!=='all'&&filters.country!=='unknown'&&!/^[A-Z]{2}$/.test(filters.country))throw fail('Invalid filter');
  function scope(a=from,b=to){
    const args=[a,b],parts=['e.day BETWEEN ?1 AND ?2'];
    for(const key of ['variant','mode','device','browser','source','country'])if(filters[key]!=='all'){
      args.push(filters[key]);const field=['variant','mode','device'].includes(key)?'e.'+key:`COALESCE(d.${key},'unknown')`;
      parts.push(field+'=?'+args.length);
    }
    return {args,where:parts.join(' AND '),cte:`WITH scoped AS (SELECT ${projection} ${join} WHERE ${parts.join(' AND ')})`};
  }
  const selected=scope(),previous={from:shift(from,-days),to:shift(from,-1)},prior=scope(previous.from,previous.to),queries=[],names=[];
  function query(name,sql,args=selected.args){names.push(name);queries.push(env.DB.prepare(sql).bind(...args));}
  const summarySQL=`SELECT COUNT(DISTINCT session_hash) sessions,COUNT(DISTINCT visitor_hash) visitors,COUNT(DISTINCT visit_hash) visits,
    COUNT(DISTINCT CASE WHEN visitor_hash IS NOT NULL THEN session_hash END) recognized_sessions,
    SUM(kind='site_visit') page_loads,SUM(kind IN ('mode_open','page_view')) page_views,SUM(kind='mode_open') opens,SUM(kind='page_view' AND mode='hub') hub_views,
    SUM(kind='round_start') starts,SUM(kind='round_complete') finishes,SUM(kind='round_complete' AND won=1 AND mode NOT IN ('party','team_higher','team_best')) wins,
    SUM(kind='round_complete' AND won=0 AND mode NOT IN ('party','team_higher','team_best')) losses,SUM(kind='share') shares,SUM(active_ms) active_ms,
    SUM(kind='error') errors,SUM(kind='round_step') steps,SUM(correct=1) correct_answers,SUM(correct IS NOT NULL) answered,
    MIN(day) first_day,COUNT(*) events FROM scoped`;
  query('summary',selected.cte+' '+summarySQL);
  query('previous',prior.cte+' '+summarySQL,prior.args);
  query('modes',selected.cte+` SELECT mode,SUM(kind='mode_open') opens,SUM(kind='round_start') starts,SUM(kind='round_complete') finishes,
    SUM(kind='round_complete' AND won=1) wins,SUM(kind='round_complete' AND won=0) losses,COUNT(DISTINCT session_hash) sessions,
    COUNT(DISTINCT visitor_hash) visitors,SUM(active_ms) active_ms,SUM(kind='share') shares,SUM(correct=1) correct_answers,SUM(correct IS NOT NULL) answered,
    AVG(CASE WHEN kind='round_complete' THEN step END) avg_attempts,AVG(CASE WHEN kind='round_complete' THEN score END) avg_score,
    AVG(CASE WHEN kind='round_complete' THEN elapsed_ms END) avg_round_ms,
    COUNT(DISTINCT CASE WHEN kind='mode_open' THEN session_hash END) open_sessions,
    COUNT(DISTINCT CASE WHEN kind='round_start' THEN session_hash END) start_sessions,
    COUNT(DISTINCT CASE WHEN kind='round_complete' THEN session_hash END) finish_sessions,
    COUNT(DISTINCT CASE WHEN kind='share' THEN session_hash END) share_sessions
    FROM scoped WHERE mode<>'hub' GROUP BY mode ORDER BY opens DESC,active_ms DESC,mode`);
  query('cohort',selected.cte+` SELECT s.mode,COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN s.id END) completed,
    COUNT(DISTINCT CASE WHEN c.won=1 THEN s.id END) won,
    COUNT(DISTINCT CASE WHEN x.id IS NOT NULL AND c.id IS NULL THEN s.id END) left_unfinished
    FROM scoped s LEFT JOIN sweater_analytics_events c ON c.session_hash=s.session_hash AND c.mode=s.mode AND c.variant=s.variant AND c.round_hash=s.round_hash AND c.kind='round_complete' AND c.day<=?2
    LEFT JOIN sweater_analytics_events x ON x.session_hash=s.session_hash AND x.mode=s.mode AND x.variant=s.variant AND x.round_hash=s.round_hash AND x.kind='round_exit' AND x.day<=?2
    WHERE s.kind='round_start' GROUP BY s.mode`);
  query('trend',selected.cte+` SELECT day,SUM(kind='mode_open') opens,SUM(kind='round_start') starts,SUM(kind='round_complete') finishes,
    COUNT(DISTINCT session_hash) sessions,COUNT(DISTINCT visitor_hash) visitors,COUNT(DISTINCT visit_hash) visits,SUM(active_ms) active_ms,SUM(kind='share') shares FROM scoped GROUP BY day ORDER BY day`);
  query('variants',selected.cte+` SELECT variant,SUM(kind='mode_open') opens,SUM(kind='round_start') starts,SUM(kind='round_complete') finishes,COUNT(DISTINCT session_hash) sessions,SUM(active_ms) active_ms FROM scoped GROUP BY variant ORDER BY opens DESC`);
  for(const field of ['device','browser','os','source','country','theme','viewport'])query(field,selected.cte+` SELECT COALESCE(${field},'unknown') ${field},COUNT(DISTINCT session_hash) sessions,COUNT(DISTINCT visitor_hash) visitors,SUM(kind='mode_open') opens,SUM(kind='round_start') starts,SUM(active_ms) active_ms FROM scoped GROUP BY COALESCE(${field},'unknown') ORDER BY sessions DESC LIMIT ${field==='country'?250:40}`);
  query('campaigns',selected.cte+` SELECT campaign,COALESCE(source,'unknown') source,COALESCE(medium,'—') medium,COUNT(DISTINCT visit_hash) visits,COUNT(DISTINCT visitor_hash) visitors,SUM(kind='round_start') starts,SUM(kind='round_complete') finishes FROM scoped WHERE campaign IS NOT NULL GROUP BY campaign,source,medium ORDER BY visits DESC LIMIT 30`);
  query('heatmap',selected.cte+` SELECT CAST(strftime('%w',day) AS INTEGER) weekday,hour,COUNT(DISTINCT session_hash) sessions,SUM(kind='mode_open') opens,SUM(kind='round_start') starts,SUM(active_ms) active_ms FROM scoped GROUP BY weekday,hour ORDER BY weekday,hour`);
  query('flows',selected.cte+` SELECT from_mode,mode,SUM(kind IN ('mode_open','page_view')) transitions,COUNT(DISTINCT session_hash) sessions FROM scoped WHERE from_mode IS NOT NULL AND from_mode<>mode AND kind IN ('mode_open','page_view') GROUP BY from_mode,mode ORDER BY transitions DESC LIMIT 25`);
  query('features',selected.cte+` SELECT action,COUNT(*) uses,COUNT(DISTINCT session_hash) sessions FROM scoped WHERE kind='interaction' GROUP BY action ORDER BY uses DESC`);
  query('pages',selected.cte+` SELECT mode,SUM(kind='site_visit') landings,SUM(kind='page_exit') exits FROM scoped WHERE kind IN ('site_visit','page_exit') GROUP BY mode ORDER BY landings DESC,exits DESC`);
  query('teams',selected.cte+` SELECT team,COUNT(*) selections,COUNT(DISTINCT session_hash) sessions FROM scoped WHERE kind='interaction' AND action='team_select' AND team IS NOT NULL GROUP BY team ORDER BY selections DESC`);
  query('progress',selected.cte+` SELECT mode,step,COUNT(DISTINCT CASE WHEN kind='round_step' THEN round_hash END) reached,
    SUM(kind='round_step' AND correct=1) correct,SUM(kind='round_step' AND correct IS NOT NULL) answered,
    COUNT(DISTINCT CASE WHEN kind='round_exit' THEN round_hash END) exits,AVG(CASE WHEN kind='round_step' THEN response_ms END) response_ms
    FROM scoped WHERE kind IN ('round_step','round_exit') AND step IS NOT NULL GROUP BY mode,step ORDER BY mode,step LIMIT 300`);
  query('performance',selected.cte+` SELECT COALESCE(browser,'unknown') browser,device,COUNT(*) samples,COUNT(load_ms) load_samples,COUNT(ttfb_ms) ttfb_samples,AVG(load_ms) load_ms,AVG(ttfb_ms) ttfb_ms,AVG(lcp_ms) lcp_ms,AVG(cls) cls,
    SUM(lcp_ms>2500) slow_paints,SUM(lcp_ms IS NOT NULL) paint_samples,SUM(cls>0.25) high_shifts,SUM(cls IS NOT NULL) shift_samples FROM scoped WHERE kind='performance' GROUP BY browser,device ORDER BY samples DESC LIMIT 30`);
  query('errors',selected.cte+` SELECT e.mode,COALESCE(e.browser,'unknown') browser,COALESCE(e.build,'unknown') build,e.action,
    d.release,d.error_type,d.error_file,d.error_line,d.error_column,d.resource,d.asset,d.online,
    COUNT(*) errors,COUNT(DISTINCT e.session_hash) sessions
    FROM scoped e LEFT JOIN sweater_analytics_errors d ON d.event_id=e.id WHERE e.kind='error'
    GROUP BY e.mode,e.browser,e.build,e.action,d.release,d.error_type,d.error_file,d.error_line,d.error_column,d.resource,d.asset,d.online
    ORDER BY sessions DESC,errors DESC LIMIT 30`);
  query('visits',selected.cte+`, visit_groups AS (SELECT visit_hash,SUM(active_ms) active_ms,SUM(kind='round_start') starts,SUM(kind IN ('mode_open','page_view')) views,MAX(kind='page_exit') ended FROM scoped WHERE visit_hash IS NOT NULL GROUP BY visit_hash)
    SELECT COUNT(*) visits,SUM(active_ms>=10000 OR starts>0 OR views>=2) engaged,AVG(active_ms) avg_active_ms,SUM(ended) exits FROM visit_groups`);
  query('audience',selected.cte+`, seen AS (SELECT visitor_hash,COUNT(DISTINCT visit_hash) visits,COUNT(DISTINCT day) days_active FROM scoped WHERE visitor_hash IS NOT NULL GROUP BY visitor_hash)
    SELECT COUNT(*) visitors,SUM(v.first_day>=?1) new_visitors,SUM(v.first_day<?1) returning_visitors,SUM(s.visits>=2 OR s.days_active>=2) repeat_visitors FROM seen s JOIN sweater_analytics_visitors v ON v.visitor_hash=s.visitor_hash`);
  const retentionArgs=[...selected.args,today],todayParam='?'+retentionArgs.length;
  query('retention',selected.cte+`, new_visitors AS (SELECT DISTINCT v.visitor_hash,v.first_day FROM sweater_analytics_visitors v JOIN scoped s ON s.visitor_hash=v.visitor_hash WHERE v.first_day BETWEEN ?1 AND ?2),
    return_activity AS (SELECT DISTINCT d.visitor_hash,e.day ${join} WHERE e.day BETWEEN ?1 AND ${todayParam} AND d.visitor_hash IS NOT NULL)
    SELECT n.first_day day,COUNT(DISTINCT n.visitor_hash) visitors,
    COUNT(DISTINCT CASE WHEN date(n.first_day,'+1 day')<=${todayParam} THEN n.visitor_hash END) eligible_day1,
    COUNT(DISTINCT CASE WHEN s.day=date(n.first_day,'+1 day') THEN n.visitor_hash END) returned_day1,
    COUNT(DISTINCT CASE WHEN date(n.first_day,'+7 day')<=${todayParam} THEN n.visitor_hash END) eligible_day7,
    COUNT(DISTINCT CASE WHEN s.day=date(n.first_day,'+7 day') THEN n.visitor_hash END) returned_day7
    FROM new_visitors n LEFT JOIN return_activity s ON s.visitor_hash=n.visitor_hash GROUP BY n.first_day ORDER BY n.first_day`,retentionArgs);
  const recent=scope(shift(today,-1),today),recentArgs=[...recent.args,Date.now()-120000];
  query('realtime',recent.cte+` SELECT COUNT(DISTINCT session_hash) sessions,COUNT(DISTINCT visitor_hash) visitors,mode,COUNT(*) signals FROM scoped WHERE received_at>?${recentArgs.length} AND kind IN ('site_visit','page_view','mode_open','engagement','round_start','round_step') GROUP BY mode
    UNION ALL SELECT COUNT(DISTINCT session_hash),COUNT(DISTINCT visitor_hash),NULL,COUNT(*) FROM scoped WHERE received_at>?${recentArgs.length} AND kind IN ('site_visit','page_view','mode_open','engagement','round_start','round_step')`,recentArgs);
  query('coverage',"SELECT key,value FROM sweater_analytics_meta",[]);
  const result=await env.DB.batch(queries),data=Object.fromEntries(names.map((name,i)=>[name,result[i].results||[]]));
  const summary=data.summary[0]||{},cohorts=new Map(data.cohort.map(r=>[r.mode,r]));
  for(const key of ['sessions','visitors','visits','recognized_sessions','page_loads','page_views','hub_views','opens','starts','finishes','wins','losses','shares','active_ms','errors','steps','correct_answers','answered','events'])summary[key]=Number(summary[key]||0);
  const modes=data.modes.map(r=>({...r,label:labels[r.mode],completed_starts:cohorts.get(r.mode)?.completed||0,left_unfinished:cohorts.get(r.mode)?.left_unfinished||0,rounds_supported:r.mode!=='teams',outcomes_supported:!['party','team_higher','team_best'].includes(r.mode),finish_rate:ratio(cohorts.get(r.mode)?.completed||0,r.starts),win_rate:ratio(r.wins,r.wins+r.losses),answer_accuracy:ratio(r.correct_answers,r.answered)}));
  summary.completed_starts=modes.reduce((sum,r)=>sum+r.completed_starts,0);summary.finish_rate=ratio(summary.completed_starts,summary.starts);summary.win_rate=ratio(summary.wins,summary.wins+summary.losses);summary.avg_session_ms=summary.sessions?summary.active_ms/summary.sessions:null;
  const visits=data.visits[0]||{};summary.engaged_visits=Number(visits.engaged||0);summary.engagement_rate=ratio(visits.engaged,visits.visits);summary.bounce_rate=visits.visits?100-summary.engagement_rate:null;
  const audience=data.audience[0]||{};audience.repeat_rate=ratio(audience.repeat_visitors,audience.visitors);
  const retention={rows:data.retention,day1_eligible:0,day1_returned:0,day7_eligible:0,day7_returned:0};
  for(const r of retention.rows){retention.day1_eligible+=r.eligible_day1;retention.day1_returned+=r.returned_day1;retention.day7_eligible+=r.eligible_day7;retention.day7_returned+=r.returned_day7;}
  retention.day1_rate=ratio(retention.day1_returned,retention.day1_eligible);retention.day7_rate=ratio(retention.day7_returned,retention.day7_eligible);
  const flowLabels=data.flows.map(r=>({...r,from_label:labels[r.from_mode],to_label:labels[r.mode]}));
  const enhancedSince=Number(data.coverage.find(r=>r.key==='enhanced_since')?.value||0)||null;
  return {version:2,today,from,to,days,variant:filters.variant,filters,time_zone:'America/Vancouver',retention_days:RETENTION_DAYS,
    modes,trend:data.trend,variants:data.variants,devices:data.device,sessions:summary.sessions,summary,
    comparison:{...previous,summary:data.previous[0]||{}},audience,retention,visits,
    browsers:data.browser,systems:data.os,sources:data.source,countries:data.country,themes:data.theme,viewports:data.viewport,
    campaigns:data.campaigns,heatmap:data.heatmap,flows:flowLabels,pages:data.pages.map(r=>({...r,label:labels[r.mode]})),features:data.features,teams:data.teams,progress:data.progress,
    performance:data.performance,errors:data.errors,realtime:{modes:data.realtime.filter(r=>r.mode!==null),sessions:data.realtime.find(r=>r.mode===null)?.sessions||0,visitors:data.realtime.find(r=>r.mode===null)?.visitors||0},
    coverage:{enhanced_since:enhancedSince,recognized_sessions:summary.recognized_sessions,total_sessions:summary.sessions,rate:ratio(summary.recognized_sessions,summary.sessions)},
    choices:{modes:Object.entries(labels).map(([id,label])=>({id,label})),browsers:BROWSERS,systems:SYSTEMS,sources:SOURCES},generated_at:Date.now()};
}
