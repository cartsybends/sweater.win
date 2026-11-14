export const GAME_CENTER=(()=>{
 const finite=(n,a,b)=>Number.isFinite(n)&&n>=a&&n<=b;
 function validate(d,g,now=Date.now()){
  if(!d||d.version!==1||d.id!==g.id||d.home?.abbr!==g.home||d.away?.abbr!==g.away||!finite(Date.parse(d.checked_at),now-86400000,now+300000)||![15,60].includes(d.refresh_seconds)||!['scheduled','live','final'].includes(d.status)||!Array.isArray(d.shots)||d.shots.length>2000||!Array.isArray(d.forecast?.points)||d.forecast.points.length>1000)return null;
  if(!['home','away'].every(s=>d.status==='scheduled'?d[s].score===null:Number.isInteger(d[s].score)&&finite(d[s].score,0,30)))return null;
  if(!['home','away'].every(s=>finite(d[s].expected_goals,0,200)&&Number.isInteger(d[s].modeled_shots)&&finite(d[s].modeled_shots,0,2000)))return null;
  if(!['available','unavailable','scheduled','shootout'].includes(d.forecast.status))return null;
  let last=-1;for(const p of d.forecast.points){if(!finite(p.t,0,24000)||p.t<last||!finite(p.home,0,100)||!finite(p.away,0,100)||Math.abs(p.home+p.away-100)>.001)return null;last=p.t;}
  for(const p of d.forecast.points)if(p.period!==undefined&&(!Number.isInteger(p.period)||!finite(p.period,1,20))||p.period_type!==undefined&&!['REG','OT','SO'].includes(p.period_type)||p.remaining!==undefined&&(typeof p.remaining!=='string'||!/^\d{1,2}:[0-5]\d$/.test(p.remaining)||Number(p.remaining.split(':')[0])>20))return null;
  if(d.forecast.current&&JSON.stringify(d.forecast.current)!==JSON.stringify(d.forecast.points.at(-1)))return null;
  if(d.forecast.status==='shootout'&&d.forecast.current)return null;
  const seen=new Set();for(const s of d.shots){if(!Number.isInteger(s.id)||seen.has(s.id)||![g.home,g.away].includes(s.team)||!['saved','goal','missed','blocked'].includes(s.outcome)||!finite(s.t,0,24000)||!Number.isInteger(s.period)||!finite(s.period,1,20)||typeof s.shot_type!=='string'||s.shot_type.length>30||s.x!==null&&(!finite(s.x,-100,100)||!finite(s.y,-43,43))||s.xg!==null&&!finite(s.xg,0,1))return null;seen.add(s.id);}
  const person=p=>p===null||p&&Number.isInteger(p.id)&&finite(p.id,1,99999999)&&typeof p.name==='string'&&p.name.length<=100;
  for(const s of d.shots)if(s.assists!==undefined&&(!Array.isArray(s.assists)||s.assists.length>2||!s.assists.every(p=>p&&person(p))))return null;
  if(d.game_type!==undefined&&![2,3].includes(d.game_type))return null;
  if(d.penalties!==undefined){if(!Array.isArray(d.penalties)||d.penalties.length>300)return null;for(const p of d.penalties){if(!Number.isInteger(p.id)||seen.has(p.id)||![g.home,g.away].includes(p.team)||!finite(p.t,0,24000)||!person(p.player)||!person(p.drawn_by)||!person(p.served_by)||typeof p.reason!=='string'||p.reason.length>80||p.minutes!==null&&(!Number.isInteger(p.minutes)||!finite(p.minutes,0,20)))return null;seen.add(p.id);}}
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
 function periods(elapsed=0,gameType=2){const result=[{label:'P1',start:0,end:1200},{label:'P2',start:1200,end:2400},{label:'P3',start:2400,end:3600}];if(elapsed>3600){const length=gameType===3?1200:300;for(let n=0;n<Math.min(17,Math.ceil((elapsed-3600)/length));n++)result.push({label:n===0?'OT':`${n+1}OT`,start:3600+n*length,end:3600+(n+1)*length});}return result;}
 function eventGroups(events,max,width){const groups=[];for(const event of [...events].sort((a,b)=>a.t-b.t||a.id-b.id)){const last=groups.at(-1);if(last&&(event.t-last.reduce((n,e)=>n+e.t,0)/last.length)/max*width<30)last.push(event);else groups.push([event]);}return groups;}
 return {validate,time,period,gameTime,shotTime,filter,words,lineStyle,periods,eventGroups};
})();
