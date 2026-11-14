export const PLAYOFF_PICTURE = (()=>{
 const stages=[['playoffs','Make playoffs'],['round2','Reach Round 2'],['conference','Conference final'],['final','Stanley Cup Final'],['cup','Win the Cup']];
 const clubs=new Set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split(' '));
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 function localDay(value,zone){try{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zone||undefined,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value)),p=Object.fromEntries(parts.map(v=>[v.type,v.value]));return `${p.year}-${p.month}-${p.day}`;}catch{return '';}}
 const teamColors={ANA:'#F47A38',BOS:'#F5BE24',BUF:'#3156A0',CAR:'#CF324B',CBJ:'#4478AC',CGY:'#E94B3C',CHI:'#BD3345',COL:'#965976',DAL:'#249E7B',DET:'#E34A59',EDM:'#FA862C',FLA:'#C68D73',LAK:'#9BA7B4',MIN:'#418477',MTL:'#BF4364',NJD:'#D63A4A',NSH:'#E5B72D',NYI:'#F09A47',NYR:'#3875D7',OTT:'#C76A67',PHI:'#E88838',PIT:'#E5CB61',SEA:'#5BBEC6',SJS:'#329BA4',STL:'#517BD1',TBL:'#567CDF',TOR:'#587CA8',UTA:'#79B9D3',VAN:'#47AB8B',VGK:'#BCA46D',WPG:'#647FAD',WSH:'#E66A75'};
 function record(t){const ot=t.points-2*t.wins;return {wins:t.wins,ot,losses:t.gp-t.wins-ot,winPct:t.gp?t.wins/t.gp*100:null,pointPct:t.gp?t.points/(2*t.gp)*100:null,diff:t.gf-t.ga};}
 function sortValue(t,key){const r=record(t);return stages.some(([s])=>s===key)?t.odds[key]:key==='winPct'?r.winPct??-1:key==='pointPct'?r.pointPct??-1:key==='diff'?r.diff:key==='form'?t.form?.points??-1:key==='projected'?t.projected_points:key==='change'?t.change??-1000:t[key]??0;}
 function circle(teams,stage){const total=teams.reduce((sum,t)=>sum+t.odds[stage],0);let angle=-Math.PI/2;return teams.filter(t=>t.odds[stage]>0).map(t=>{const start=angle;angle+=t.odds[stage]/total*Math.PI*2;return {team:t.abbr,probability:t.odds[stage],share:t.odds[stage]/total*100,start,end:angle};});}
 function circleRings(mode='all'){return (mode==='all'?stages:stages.filter(([key])=>key===mode)).map(([stage],i)=>{const outer=mode==='all'?348-i*55:310;return {stage,outer,inner:mode==='all'?outer-52:135};});}
 function circleCallouts(slices,outer){
  const placed=new Map(),lanes=[outer+34,outer+88],gap=36;
  const callout=(s,r,angle)=>({...s,anchorX:420+outer*Math.cos((s.start+s.end)/2),anchorY:420+outer*Math.sin((s.start+s.end)/2),x:420+r*Math.cos(angle),y:420+r*Math.sin(angle),logoSize:30});
  for(const s of [...slices].sort((a,b)=>b.probability-a.probability||a.start-b.start)){
   const angle=(s.start+s.end)/2;let found=null;
   // Prefer the slice's exact angle, then spread only crowded logos around the perimeter.
   for(let step=0;step<=128&&!found;step++)for(const offset of step?[-step,step]:[0]){for(const radius of lanes){const c=callout(s,radius,angle+offset*Math.PI/128);if([...placed.values()].every(p=>Math.abs(p.x-c.x)>=gap||Math.abs(p.y-c.y)>=gap)){found=c;break;}}if(found)break;}
   // A fully packed ring is a bounded fallback even for an extreme cluster of tiny slices.
   if(!found)return slices.map((item,i)=>callout(item,lanes[1],(slices[0].start+slices[0].end)/2+i*Math.PI*2/slices.length));
   placed.set(s.team,found);
  }
  return slices.map(s=>placed.get(s.team));
 }
 function circleLabels(slices,outer,inner,required=false){
  const placed=[],middle=(outer+inner)/2;
  const overlaps=(a,b)=>{for(const box of [a,b])for(let i=0;i<2;i++){const p=box[i],q=box[i+1],axis=[p.y-q.y,q.x-p.x],project=points=>points.map(v=>v.x*axis[0]+v.y*axis[1]),aa=project(a),bb=project(b);if(Math.max(...aa)<=Math.min(...bb)||Math.max(...bb)<=Math.min(...aa))return false;}return true;};
  for(const s of [...slices].sort((a,b)=>b.probability-a.probability)){
   const text=percent(s.probability),angle=(s.start+s.end)/2,arc=(s.end-s.start)*middle,narrow=arc<text.length*7.2+8;
   if(!required&&(s.probability<1||narrow))continue;
   const fontSize=narrow?10:12,width=text.length*fontSize*.6,height=fontSize+2,rotation=narrow?Math.atan2(Math.sin(angle),Math.cos(angle)):0,readable=rotation>Math.PI/2?rotation-Math.PI:rotation<-Math.PI/2?rotation+Math.PI:rotation;
   const radii=narrow?[inner+width/2+1,outer-width/2-1,middle]:[middle];let best=null,bestCount=Infinity;
   for(const radius of radii){const x=420+radius*Math.cos(angle),y=420+radius*Math.sin(angle),corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([dx,dy])=>({x:x+dx*width/2*Math.cos(readable)-dy*height/2*Math.sin(readable),y:y+dx*width/2*Math.sin(readable)+dy*height/2*Math.cos(readable)})),count=placed.filter(p=>overlaps(corners,p.corners)).length;
    if(count<bestCount){best={team:s.team,probability:s.probability,text,x,y,fontSize,rotation:readable*180/Math.PI,corners};bestCount=count;}if(!count)break;
   }
   if(required||bestCount===0)placed.push(best);
  }
  return placed;
 }
 function shooting(g,side){const shots=g[side==='home'?'home_shots':'away_shots'];if(!finite(shots)||shots<=0)return null;const goals=g[side==='home'?'hg':'ag'],other=g[side==='home'?'ag':'hg'];return (goals-(g.end==='SO'&&goals>other?1:0))/shots*100;}
 function goalieStatsValid(p,g){
  const s=p.stats;if(s===undefined)return true;
  const year=Number(String(g.id).slice(0,4));
  return s&&Number.isInteger(s.gp)&&Number.isInteger(s.gs)&&s.gs>=0&&s.gs<=s.gp&&s.gp<=100&&s.season===year*10000+year+1&&['reported','cached'].includes(s.status)&&Number.isFinite(Date.parse(s.as_of))&&Date.parse(s.as_of)<Date.parse(g.start)&&(s.sv===null||finite(s.sv)&&s.sv>=0&&s.sv<=1)&&(s.gaa===null||finite(s.gaa)&&s.gaa>=0&&s.gaa<=3600);
 }
 function contextValid(g){
  if(!g.context)return true;
  return ['home','away'].every(side=>{const c=g.context[side],q=c?.goalie;if(!q||!['reported','cached','stale','unavailable','not_reconstructed'].includes(c.injury_status)||!Number.isInteger(c.rest_days)||c.rest_days<1||c.rest_days>7||!['projected','confirmed','unknown'].includes(q.status)||!finite(q.gsax)||Math.abs(q.gsax)>2||!Array.isArray(q.players)||q.players.length>10||q.players.some(p=>!Number.isInteger(p.id)||p.id<0||typeof p.name!=='string'||!p.name.length||p.name.length>100||!finite(p.probability)||p.probability<0||p.probability>100)||new Set(q.players.map(p=>p.id)).size!==q.players.length||q.players.length&&Math.abs(q.players.reduce((n,p)=>n+p.probability,0)-100)>.002||!Array.isArray(c.injuries)||c.injuries.length>100||c.injuries.some(i=>typeof i.name!=='string'||i.name.length>100||typeof i.status!=='string'||i.status.length>50))return false;
   if(!q.players.every(p=>goalieStatsValid(p,g)))return false;
   const r=q.report;if(r&&(!['confirmed','likely','conflicting','not_starting'].includes(r.status)||r.game_id!==g.id||r.team!==g[side]||r.game_start&&r.game_start!==g.start||!Number.isInteger(r.player_id)||typeof r.author!=='string'||r.author.length>100||!/^https:\/\/(?:(?:x|twitter)\.com\/[A-Za-z0-9_]+\/status\/\d+|www\.rotowire\.com\/hockey\/player\/[a-z0-9-]+-\d+)$/.test(r.source_url)||!Number.isFinite(Date.parse(r.reported_at))||Date.parse(r.reported_at)>=Date.parse(g.start)||r.via_url&&!/^https:\/\/(?:www\.dailyfaceoff\.com\/|www\.rotowire\.com\/rss\/$)/.test(r.via_url)))return false;
   return q.status!=='confirmed'||r?.status==='confirmed'&&q.players.filter(p=>p.probability===100&&p.id===r.player_id).length===1;
  });
 }
 function analyticsValid(d){
  if(d.analytics_version===undefined)return true;
  if(d.analytics_version!==1||!Array.isArray(d.games)||d.games.length>400||!/^\d{4}-\d{2}-\d{2}$/.test(d.games_today)||!/^\d{4}-\d{2}-\d{2}$/.test(d.games_from)||!/^\d{4}-\d{2}-\d{2}$/.test(d.games_through))return false;
  const ids=new Set();for(const g of d.games){const p=g.prediction;if(!Number.isInteger(g.id)||ids.has(g.id)||!clubs.has(g.home)||!clubs.has(g.away)||g.home===g.away||!Number.isFinite(Date.parse(g.start))||!/^\d{4}-\d{2}-\d{2}$/.test(g.date)||!p||!finite(p.home_win)||!finite(p.away_win)||p.home_win<0||p.home_win>100||p.away_win<0||p.away_win>100||Math.abs(p.home_win+p.away_win-100)>.001||!['pregame','recorded','reconstructed'].includes(p.basis)||!finite(p.home_goals)||!finite(p.away_goals)||p.home_goals<=0||p.away_goals<=0)return false;
   if(p.basis!=='reconstructed'&&(!Number.isFinite(Date.parse(p.at))||Date.parse(p.at)>=Date.parse(g.start)))return false;
   if(g.market){const m=g.market;if(m.source!=='ESPN'||typeof m.provider!=='string'||!m.provider.length||m.provider.length>50||typeof m.source_url!=='string'||!/^https:\/\/www\.espn\.com\/nhl\/game\/_\/gameId\/\d+$/.test(m.source_url)||!['home','away'].every(k=>Number.isInteger(m[k])&&Math.abs(m[k])>=100&&Math.abs(m[k])<=100000)||!Number.isFinite(Date.parse(m.observed_at))||Date.parse(m.observed_at)>=Date.parse(g.start)||Date.parse(m.observed_at)>Date.parse(d.checked_at)+300000)return false;}
   if(!contextValid(g))return false;
   if(['OFF','FINAL'].includes(g.state)&&(!Number.isInteger(g.hg)||!Number.isInteger(g.ag)||g.hg<0||g.ag<0||g.hg===g.ag||!['REG','OT','SO'].includes(g.end)))return false;
   for(const field of ['home_shots','away_shots'])if(g[field]!==undefined&&(!Number.isInteger(g[field])||g[field]<0||g[field]>200))return false;
   ids.add(g.id);
  }
  return d.teams.every(t=>t.form&&Number.isInteger(t.form.gp)&&t.form.gp>=0&&t.form.gp<=10&&Number.isInteger(t.form.points)&&t.form.points>=0&&t.form.points<=t.form.gp*2&&Number.isInteger(t.form.wins)&&t.form.wins>=0&&t.form.wins<=t.form.gp);
 }
 function oddsValid(o){return o&&stages.every(([k],i)=>finite(o[k])&&o[k]>=0&&o[k]<=100&&(!i||o[stages[i-1][0]]>=o[k]));}
 function percent(n){if(!finite(n))return '—';if(n===0)return '<0.1%';if(n===100)return '>99.9%';if(n<.1)return '<0.1%';if(n>99.9)return '>99.9%';return n.toFixed(1)+'%';}
 function fair(n,format='percent'){if(format==='percent')return percent(n);if(!finite(n)||n<=0||n>=100)return '—';if(format==='decimal')return (100/n).toFixed(2);const value=n>=50?-100*n/(100-n):100*(100-n)/n;return (value>0?'+':'−')+Math.round(Math.abs(value)).toLocaleString();}
 function validate(d,now=Date.now()){
  if(!d||d.version!==1||!['sweater-goals-v1','sweater-xg-v2'].includes(d.model)||!Number.isInteger(d.start)||d.start<2024||d.start>new Date(now).getUTCFullYear()+1||d.season!==d.start*10000+d.start+1||![82,84].includes(d.season_games)||!Number.isInteger(d.simulations)||d.simulations<100||d.simulations>200000||!Array.isArray(d.teams)||d.teams.length!==32||!Number.isFinite(Date.parse(d.checked_at))||Date.parse(d.checked_at)>now+300000||!Number.isFinite(Date.parse(d.updated_at))||Date.parse(d.updated_at)>Date.parse(d.checked_at)||d.total_games!==d.season_games*16||!Number.isInteger(d.completed_games)||d.completed_games<0||d.completed_games>d.total_games)return null;
  if(d.model==='sweater-xg-v2'&&(d.advanced?.version!==2||d.advanced.source!=='MoneyPuck.com'||!/^\d{4}-\d{2}-\d{2}$/.test(d.advanced.data_through)))return null;
  const ids=new Set();
  for(const t of d.teams){
   if(!clubs.has(t.abbr)||ids.has(t.abbr)||typeof t.name!=='string'||t.name.length>80||!['E','W'].includes(t.conference)||typeof t.division!=='string'||!Number.isInteger(t.gp)||t.gp<0||t.gp>d.season_games||!Number.isInteger(t.points)||t.points<0||t.points>t.gp*2||!oddsValid(t.odds)||!finite(t.projected_points)||t.projected_points<t.points-.051||t.projected_points>t.points+2*(d.season_games-t.gp)+.051||!Array.isArray(t.points_range)||t.points_range.length!==2||!t.points_range.every(Number.isInteger)||t.points_range[0]>t.points_range[1]||!Array.isArray(t.distribution)||!t.distribution.length||t.distribution.length>169||t.distribution.some(r=>!Array.isArray(r)||r.length!==2||!Number.isInteger(r[0])||r[0]<t.points||r[0]>t.points+2*(d.season_games-t.gp)||!finite(r[1])||r[1]<0||r[1]>100)||!Array.isArray(t.opponents)||t.opponents.length>16||t.opponents.some(o=>!clubs.has(o.team)||o.team===t.abbr||!finite(o.chance)||o.chance<0||o.chance>100)||t.change!==null&&t.change!==undefined&&(!finite(t.change)||Math.abs(t.change)>100))return null;
   if(Math.abs(t.distribution.reduce((s,r)=>s+r[1],0)-100)>.03||Math.abs(t.opponents.reduce((s,o)=>s+o.chance,0)-t.odds.playoffs)>.03)return null;
   ids.add(t.abbr);
   if(!['wins','rw','row','gf','ga'].every(k=>Number.isInteger(t[k])&&t[k]>=0)||t.rw>t.row||t.row>t.wins||t.wins>t.gp||t.points<t.wins*2||t.points-t.wins*2>t.gp-t.wins)return null;
  }
  if(stages.some(([key],i)=>Math.abs(d.teams.reduce((s,t)=>s+t.odds[key],0)-[1600,800,400,200,100][i])>.03)||!Array.isArray(d.history)||d.history.length>3000)return null;
  let last=0;for(const h of d.history){const at=Date.parse(h.at);if(!Number.isFinite(at)||at<last||at>Date.parse(d.updated_at)||!h.teams)return null;for(const club of clubs){const a=h.teams[club];if(!Array.isArray(a)||a.length!==2||!a.every(n=>finite(n)&&n>=0&&n<=100)||a[0]<a[1])return null;}last=at;}
  return analyticsValid(d)?d:null;
 }
 function snapshot(raw){
  if(!raw||raw.v!==1||!clubs.has(raw.team)||!Number.isInteger(raw.start)||raw.start<2024||raw.start>2100||typeof raw.name!=='string'||!raw.name.length||raw.name.length>80||!Number.isFinite(Date.parse(raw.at))||!oddsValid(raw.odds)||!Number.isInteger(raw.gp)||raw.gp<0||raw.gp>84||!Number.isInteger(raw.points)||raw.points<0||raw.points>raw.gp*2||!finite(raw.projected)||raw.projected<raw.points||raw.projected>168||!Number.isInteger(raw.n)||raw.n<100||raw.n>200000)return null;
  return {v:1,team:raw.team,name:raw.name,start:raw.start,at:new Date(raw.at).toISOString(),gp:raw.gp,points:raw.points,projected:raw.projected,n:raw.n,odds:Object.fromEntries(stages.map(([k])=>[k,raw.odds[k]]))};
 }
 function read(hash){if(typeof hash!=='string'||hash.length>2500)return null;try{const q=hash.split('?')[1]||'',s=new URLSearchParams(q).get('s');return s?snapshot(JSON.parse(s)):null;}catch{return null;}}
 return Object.freeze({stages,clubs,teamColors,record,sortValue,circle,circleRings,circleLabels,circleCallouts,localDay,shooting,percent,fair,validate,snapshot,read,interval:120000,url:'https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json'});
})();
