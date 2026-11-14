export const GAME_CENTER=(()=>{
 const finite=(n,a,b)=>Number.isFinite(n)&&n>=a&&n<=b;
 function validate(d,g,now=Date.now()){
  if(!d||d.version!==1||d.id!==g.id||d.home?.abbr!==g.home||d.away?.abbr!==g.away||!finite(Date.parse(d.checked_at),now-86400000,now+300000)||![15,60].includes(d.refresh_seconds)||!['scheduled','live','final'].includes(d.status)||!Array.isArray(d.shots)||d.shots.length>2000||!Array.isArray(d.forecast?.points)||d.forecast.points.length>1000)return null;
  if(!['home','away'].every(s=>d.status==='scheduled'?d[s].score===null:Number.isInteger(d[s].score)&&finite(d[s].score,0,30)))return null;
  if(!['home','away'].every(s=>finite(d[s].expected_goals,0,200)&&Number.isInteger(d[s].modeled_shots)&&finite(d[s].modeled_shots,0,2000)))return null;
  if(!['available','unavailable','scheduled','shootout'].includes(d.forecast.status))return null;
  let last=-1;for(const p of d.forecast.points){if(!finite(p.t,0,24000)||p.t<last||!finite(p.home,0,100)||!finite(p.away,0,100)||Math.abs(p.home+p.away-100)>.001)return null;last=p.t;}
  if(d.forecast.current&&JSON.stringify(d.forecast.current)!==JSON.stringify(d.forecast.points.at(-1)))return null;
  if(d.forecast.status==='shootout'&&d.forecast.current)return null;
  const seen=new Set();for(const s of d.shots){if(!Number.isInteger(s.id)||seen.has(s.id)||![g.home,g.away].includes(s.team)||!['saved','goal','missed','blocked'].includes(s.outcome)||!finite(s.t,0,24000)||!Number.isInteger(s.period)||!finite(s.period,1,20)||typeof s.shot_type!=='string'||s.shot_type.length>30||s.x!==null&&(!finite(s.x,-100,100)||!finite(s.y,-43,43))||s.xg!==null&&!finite(s.xg,0,1))return null;seen.add(s.id);}
  return d;
 }
 const time=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
 const period=s=>s.period_type==='OT'?(s.period===4?'OT':`${s.period-3}OT`):`P${s.period}`;
 const shotTime=s=>`${period(s)} · ${typeof s.remaining==='string'&&/^\d{1,2}:[0-5]\d$/.test(s.remaining)?s.remaining+' left':time(s.t)+' elapsed'}`;
 const filter=(shots,{team='',period='',outcome='unblocked'}={})=>shots.filter(s=>(!team||s.team===team)&&(!period||s.period===Number(period))&&(outcome==='all'||outcome==='unblocked'&&s.outcome!=='blocked'||s.outcome===outcome));
 return {validate,time,period,shotTime,filter};
})();
