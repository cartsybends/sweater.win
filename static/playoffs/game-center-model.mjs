export const GAME_CENTER=(()=>{
 const finite=(n,a,b)=>Number.isFinite(n)&&n>=a&&n<=b;
 const leaderStats=[['points','Points'],['goals','Goals'],['assists','Assists'],['penaltyMinutes','PIM']];
 function validateLeaders(data,game,season,now=Date.now()){
  if(data?.version!==1||data.season!==season||typeof data.stale!=='boolean'||!finite(Date.parse(data.checked_at),now-86460000,now+300000)||!data.teams)return null;
  const rank=value=>Number.isInteger(value)&&finite(value,1,3);
  const validTeam=team=>team===null||team&&leaderStats.every(([key])=>{
   const rows=team[key];
   return Array.isArray(rows)&&rows.length<=3&&new Set(rows.map(row=>row?.id)).size===rows.length&&rows.every((row,index)=>row&&Number.isInteger(row.id)&&finite(row.id,1,99999999)&&typeof row.name==='string'&&row.name.length>0&&row.name.length<=100&&Number.isInteger(row.value)&&finite(row.value,0,1000)&&rank(row.rank)&&(!index||row.value<=rows[index-1].value));
  });
  const teams=[data.teams[game.away],data.teams[game.home]];
  if(!teams.some(Boolean)||!teams.every(validTeam))return null;
  if(data.league_ranks!==null&&!leaderStats.every(([key])=>{
   const ranks=data.league_ranks?.[key];
   return ranks&&typeof ranks==='object'&&!Array.isArray(ranks)&&Object.keys(ranks).length<=1600&&Object.entries(ranks).every(([id,value])=>/^\d{1,8}$/.test(id)&&rank(value));
  }))return null;
  return data;
 }
 function validate(d,g,now=Date.now()){
  if(!d||d.version!==1||d.id!==g.id||d.home?.abbr!==g.home||d.away?.abbr!==g.away||!finite(Date.parse(d.checked_at),now-86400000,now+300000)||![5,15,60].includes(d.refresh_seconds)||!['scheduled','live','final'].includes(d.status)||!Array.isArray(d.shots)||d.shots.length>2000||!Array.isArray(d.forecast?.points)||d.forecast.points.length>1000)return null;
  if(!['home','away'].every(s=>d.status==='scheduled'?d[s].score===null:Number.isInteger(d[s].score)&&finite(d[s].score,0,30)))return null;
  if(!['home','away'].every(s=>finite(d[s].expected_goals,0,200)&&Number.isInteger(d[s].modeled_shots)&&finite(d[s].modeled_shots,0,2000)))return null;
  if(!['available','unavailable','scheduled','shootout'].includes(d.forecast.status))return null;
  let last=-1;for(const p of d.forecast.points){if(!finite(p.t,0,24000)||p.t<last||!finite(p.home,0,100)||!finite(p.away,0,100)||Math.abs(p.home+p.away-100)>.001)return null;last=p.t;}
  for(const p of d.forecast.points)if(p.period!==undefined&&(!Number.isInteger(p.period)||!finite(p.period,1,20))||p.period_type!==undefined&&!['REG','OT','SO'].includes(p.period_type)||p.remaining!==undefined&&(typeof p.remaining!=='string'||!/^\d{1,2}:[0-5]\d$/.test(p.remaining)||Number(p.remaining.split(':')[0])>20))return null;
  for(const p of d.forecast.points)if(p.penalty){const c=p.penalty;if(!['available','unavailable'].includes(c.status)||!['home','away',null].includes(c.power_play)||![c.home_skaters,c.away_skaters].every(n=>Number.isInteger(n)&&finite(n,3,5))||!finite(c.remaining,0,3600))return null;}
  if(d.forecast.current&&JSON.stringify(d.forecast.current)!==JSON.stringify(d.forecast.points.at(-1)))return null;
  if(d.forecast.status==='shootout'&&d.forecast.current)return null;
  const seen=new Set();for(const s of d.shots){if(!Number.isInteger(s.id)||seen.has(s.id)||![g.home,g.away].includes(s.team)||!['saved','goal','missed','blocked'].includes(s.outcome)||!finite(s.t,0,24000)||!Number.isInteger(s.period)||!finite(s.period,1,20)||typeof s.shot_type!=='string'||s.shot_type.length>30||s.x!==null&&(!finite(s.x,-100,100)||!finite(s.y,-43,43))||s.xg!==null&&!finite(s.xg,0,1))return null;seen.add(s.id);}
  for(const s of d.shots)if(s.location_source&&(s.outcome!=='goal'||s.location_source.provider!=='ESPN'||!/^https:\/\/www\.espn\.com\/nhl\/game\/_\/gameId\/\d{1,12}$/.test(s.location_source.url||'')))return null;
  const person=p=>p===null||p&&Number.isInteger(p.id)&&finite(p.id,1,99999999)&&typeof p.name==='string'&&p.name.length<=100;
  for(const s of d.shots)if(s.assists!==undefined&&(!Array.isArray(s.assists)||s.assists.length>2||!s.assists.every(p=>p&&person(p))))return null;
  if(d.game_type!==undefined&&![2,3].includes(d.game_type))return null;
  if(d.penalties!==undefined){if(!Array.isArray(d.penalties)||d.penalties.length>300)return null;for(const p of d.penalties){if(!Number.isInteger(p.id)||seen.has(p.id)||![g.home,g.away].includes(p.team)||!finite(p.t,0,24000)||!person(p.player)||!person(p.drawn_by)||!person(p.served_by)||typeof p.reason!=='string'||p.reason.length>80||p.minutes!==null&&(!Number.isInteger(p.minutes)||!finite(p.minutes,0,25)))return null;seen.add(p.id);}}
  if(d.shootout!==undefined){const so=d.shootout;if(!so||typeof so.started!=='boolean'||typeof so.complete!=='boolean'||!Array.isArray(so.attempts)||so.attempts.length>200||!Number.isInteger(so.home_goals)||!Number.isInteger(so.away_goals))return null;const rounds={[g.home]:0,[g.away]:0},goals={[g.home]:0,[g.away]:0};for(const a of so.attempts){if(!Number.isInteger(a.id)||seen.has(a.id)||![g.home,g.away].includes(a.team)||!['goal','saved','missed','unsuccessful'].includes(a.outcome)||!person(a.player)||!person(a.goalie)||a.round!==++rounds[a.team])return null;seen.add(a.id);if(a.outcome==='goal')goals[a.team]++;}if(so.home_goals!==goals[g.home]||so.away_goals!==goals[g.away])return null;}
  return d;
 }
 const time=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
 const period=s=>s.period_type==='OT'?(s.period===4?'OT':`${s.period-3}OT`):`P${s.period}`;
 function gameTime(p,gameType=2){if(p.period_type==='SO')return 'Shootout'+(p.kind==='final'?' · Final':'');let number,type,seconds;if(p.t<=3600){number=Math.max(1,Math.ceil(p.t/1200));type='REG';seconds=number*1200-p.t;}else{const length=gameType===3?1200:300;number=3+Math.ceil((p.t-3600)/length);type='OT';seconds=(number-3)*length-(p.t-3600);}const label=period({period:p.period||number,period_type:p.period_type||type}),remaining=typeof p.remaining==='string'&&/^\d{1,2}:[0-5]\d$/.test(p.remaining)?p.remaining.padStart(5,'0'):time(seconds).padStart(5,'0');return `${label} · ${remaining} remaining`;}
 const shotTime=s=>gameTime(s);
 const filter=(shots,{team='',period='',outcome='unblocked'}={})=>shots.filter(s=>(!team||s.team===team)&&(!period||s.period===Number(period))&&(outcome==='all'||outcome==='unblocked'&&s.outcome!=='blocked'||s.outcome===outcome));
 const words=s=>typeof s==='string'?s.replaceAll('-',' ').replace(/^./,c=>c.toUpperCase()):'';
 function lineStyle(away,home){const rgb=hex=>/^#[0-9a-f]{6}$/i.test(hex||'')?[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)):null,a=rgb(away),h=rgb(home);return {away:a?away:'#d48533',home:h?home:'#497fc7',dashed:!!a&&!!h&&Math.hypot(...a.map((n,i)=>n-h[i]))<100};}
 // Use each club's own secondary colour when primary colours would collide.
 // Sorting by club makes the choice independent of home/away assignment.
 const secondaryColors={ANA:'#C6AE7D',BOS:'#A9B0BC',BUF:'#E0B53B',CAR:'#AFB6C0',CBJ:'#CF4357',CGY:'#E4B83D',CHI:'#ACB4C1',COL:'#468EB5',DAL:'#ADB7C3',DET:'#B8C2CE',EDM:'#FA862C',FLA:'#416FAE',LAK:'#CFD5DE',MIN:'#C74C52',MTL:'#416FBA',NJD:'#B7C1CE',NSH:'#466CAA',NYI:'#3C6DB4',NYR:'#D54960',OTT:'#BEA477',PHI:'#ADB7C5',PIT:'#A5B1C0',SEA:'#CE5264',SJS:'#E68B42',STL:'#DFB63A',TBL:'#B8C5D7',TOR:'#BDC7D4',UTA:'#B5BBC4',VAN:'#3D72B8',VGK:'#C94A54',WPG:'#CB4C5D',WSH:'#446DAE'};
 function matchupStyle(away,home,palette={}){
  const primary=team=>team==='EDM'?'#4276C5':palette[team],original=lineStyle(primary(away),primary(home));
  if(!original.dashed)return original;
  const [first,second]=[away,home].sort(),options=team=>[primary(team),secondaryColors[team]].filter(c=>/^#[0-9a-f]{6}$/i.test(c||'')),distance=(a,b)=>Math.hypot(...[1,3,5].map(i=>parseInt(a.slice(i,i+2),16)-parseInt(b.slice(i,i+2),16)));
  let best=null;
  options(first).forEach((a,i)=>options(second).forEach((b,j)=>{const changes=i+j,gap=distance(a,b);if(gap>=100&&(!best||changes<best.changes||changes===best.changes&&gap>best.gap))best={a,b,changes,gap};}));
  return best?lineStyle(away===first?best.a:best.b,home===first?best.a:best.b):original;
 }
 function periods(elapsed=0,gameType=2){const result=[{label:'P1',start:0,end:1200},{label:'P2',start:1200,end:2400},{label:'P3',start:2400,end:3600}];if(elapsed>3600){const length=gameType===3?1200:300;for(let n=0;n<Math.min(17,Math.ceil((elapsed-3600)/length));n++)result.push({label:n===0?'OT':`${n+1}OT`,start:3600+n*length,end:3600+(n+1)*length});}return result;}
 function axisTicks(segments){const ticks=[{t:0,label:String((segments[0].end-segments[0].start)/60)}];for(const p of segments){for(let t=p.start+300;t<p.end;t+=300)ticks.push({t,label:String((p.end-t)/60)});ticks.push({t:p.end,label:'0'});}return ticks;}
 function plotEvents(events,points,home,geometry){
  const {left,right,top,bottom,max}=geometry,x=t=>left+t/max*(right-left),y=p=>bottom-p/100*(bottom-top),groups=[];
  for(const event of [...events].sort((a,b)=>a.t-b.t||a.id-b.id)){const point=points.find(p=>p.event_id===event.id&&p.kind===event.kind)||points.reduce((a,p)=>!a||Math.abs(p.t-event.t)<=Math.abs(a.t-event.t)?p:a,null);if(!point)continue;const anchor={x:x(event.t),y:y(point[event.team===home?'home':'away'])},last=groups.find(g=>g.kind===event.kind&&Math.hypot(g.anchor.x-anchor.x,g.anchor.y-anchor.y)<25);if(last)last.events.push(event);else groups.push({kind:event.kind,events:[event],anchor});}
  const placed=[];for(const group of groups){let best=null,bestScore=Infinity;const preferred=group.kind==='goal'?-20:20;for(const dx of [0,-28,28,-56,56])for(const dy of [preferred,-preferred,-45,45,-70,70]){const cx=Math.max(left+13,Math.min(right-13,group.anchor.x+dx)),cy=Math.max(top+14,Math.min(bottom-14,group.anchor.y+dy)),collisions=placed.filter(p=>Math.abs(p.x-cx)<29&&Math.abs(p.y-cy)<29).length,score=collisions*10000+Math.hypot(cx-group.anchor.x,cy-group.anchor.y);if(score<bestScore){bestScore=score;best={x:cx,y:cy};}}placed.push({...group,...best});}return placed;
 }
 function eventGroups(events,max,width){const groups=[];for(const event of [...events].sort((a,b)=>a.t-b.t||a.id-b.id)){const last=groups.at(-1);if(last&&(event.t-last.reduce((n,e)=>n+e.t,0)/last.length)/max*width<30)last.push(event);else groups.push([event]);}return groups;}
 return {validate,validateLeaders,leaderStats,time,period,gameTime,shotTime,filter,words,lineStyle,matchupStyle,periods,eventGroups,axisTicks,plotEvents};
})();
