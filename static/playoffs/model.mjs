export const PLAYOFF_PICTURE = (()=>{
 const stages=[['playoffs','Make playoffs'],['round2','Reach Round 2'],['conference','Conference final'],['final','Stanley Cup Final'],['cup','Win the Cup']];
 const clubs=new Set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split(' '));
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 function oddsValid(o){return o&&stages.every(([k],i)=>finite(o[k])&&o[k]>=0&&o[k]<=100&&(!i||o[stages[i-1][0]]>=o[k]));}
 function percent(n){if(!finite(n))return '—';if(n===0)return '<0.1%';if(n===100)return '>99.9%';if(n<.1)return '<0.1%';if(n>99.9)return '>99.9%';return n.toFixed(1)+'%';}
 function fair(n,format='percent'){if(format==='percent')return percent(n);if(!finite(n)||n<=0||n>=100)return '—';if(format==='decimal')return (100/n).toFixed(2);const value=n>=50?-100*n/(100-n):100*(100-n)/n;return (value>0?'+':'−')+Math.round(Math.abs(value)).toLocaleString();}
 function validate(d,now=Date.now()){
  if(!d||d.version!==1||d.model!=='sweater-goals-v1'||!Number.isInteger(d.start)||d.start<2024||d.start>new Date(now).getUTCFullYear()+1||d.season!==d.start*10000+d.start+1||![82,84].includes(d.season_games)||!Number.isInteger(d.simulations)||d.simulations<100||d.simulations>200000||!Array.isArray(d.teams)||d.teams.length!==32||!Number.isFinite(Date.parse(d.checked_at))||Date.parse(d.checked_at)>now+300000||!Number.isFinite(Date.parse(d.updated_at))||Date.parse(d.updated_at)>Date.parse(d.checked_at)||d.total_games!==d.season_games*16||!Number.isInteger(d.completed_games)||d.completed_games<0||d.completed_games>d.total_games)return null;
  const ids=new Set();
  for(const t of d.teams){
   if(!clubs.has(t.abbr)||ids.has(t.abbr)||typeof t.name!=='string'||t.name.length>80||!['E','W'].includes(t.conference)||typeof t.division!=='string'||!Number.isInteger(t.gp)||t.gp<0||t.gp>d.season_games||!Number.isInteger(t.points)||t.points<0||t.points>t.gp*2||!oddsValid(t.odds)||!finite(t.projected_points)||t.projected_points<t.points-.051||t.projected_points>t.points+2*(d.season_games-t.gp)+.051||!Array.isArray(t.points_range)||t.points_range.length!==2||!t.points_range.every(Number.isInteger)||t.points_range[0]>t.points_range[1]||!Array.isArray(t.distribution)||!t.distribution.length||t.distribution.length>169||t.distribution.some(r=>!Array.isArray(r)||r.length!==2||!Number.isInteger(r[0])||r[0]<t.points||r[0]>t.points+2*(d.season_games-t.gp)||!finite(r[1])||r[1]<0||r[1]>100)||!Array.isArray(t.opponents)||t.opponents.length>16||t.opponents.some(o=>!clubs.has(o.team)||o.team===t.abbr||!finite(o.chance)||o.chance<0||o.chance>100)||t.change!==null&&t.change!==undefined&&(!finite(t.change)||Math.abs(t.change)>100))return null;
   if(Math.abs(t.distribution.reduce((s,r)=>s+r[1],0)-100)>.03||Math.abs(t.opponents.reduce((s,o)=>s+o.chance,0)-t.odds.playoffs)>.03)return null;
   ids.add(t.abbr);
  }
  if(stages.some(([key],i)=>Math.abs(d.teams.reduce((s,t)=>s+t.odds[key],0)-[1600,800,400,200,100][i])>.03)||!Array.isArray(d.history)||d.history.length>3000)return null;
  let last=0;for(const h of d.history){const at=Date.parse(h.at);if(!Number.isFinite(at)||at<last||at>Date.parse(d.updated_at)||!h.teams)return null;for(const club of clubs){const a=h.teams[club];if(!Array.isArray(a)||a.length!==2||!a.every(n=>finite(n)&&n>=0&&n<=100)||a[0]<a[1])return null;}last=at;}
  return d;
 }
 function snapshot(raw){
  if(!raw||raw.v!==1||!clubs.has(raw.team)||!Number.isInteger(raw.start)||raw.start<2024||raw.start>2100||typeof raw.name!=='string'||!raw.name.length||raw.name.length>80||!Number.isFinite(Date.parse(raw.at))||!oddsValid(raw.odds)||!Number.isInteger(raw.gp)||raw.gp<0||raw.gp>84||!Number.isInteger(raw.points)||raw.points<0||raw.points>raw.gp*2||!finite(raw.projected)||raw.projected<raw.points||raw.projected>168||!Number.isInteger(raw.n)||raw.n<100||raw.n>200000)return null;
  return {v:1,team:raw.team,name:raw.name,start:raw.start,at:new Date(raw.at).toISOString(),gp:raw.gp,points:raw.points,projected:raw.projected,n:raw.n,odds:Object.fromEntries(stages.map(([k])=>[k,raw.odds[k]]))};
 }
 function read(hash){if(typeof hash!=='string'||hash.length>2500)return null;try{const q=hash.split('?')[1]||'',s=new URLSearchParams(q).get('s');return s?snapshot(JSON.parse(s)):null;}catch{return null;}}
 return Object.freeze({stages,clubs,percent,fair,validate,snapshot,read,interval:120000,url:'https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json'});
})();
