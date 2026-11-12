// This public feed updates independently of the game bundle.
export const POINT_PROJECTIONS_FEED=(()=>{
 const clubs=new Set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split(' '));
 const interval=5*60*1000,url='https://raw.githubusercontent.com/cartsybends/sweater.win/main/projections_cache.json';
 const integer=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
 function validate(data,now=Date.now()){
  try{
   const date=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'numeric'}).formatToParts(new Date(now)),year=Number(date.find(p=>p.type==='year').value),month=Number(date.find(p=>p.type==='month').value),start=month>=7?year:year-1;
   if(!data||data.version!==1||data.start!==start||data.season!==start*10000+start+1||data.season_games!==84||!/^\d{4}-\d{2}-\d{2}$/.test(data.asof)||new Date(data.asof).toISOString().slice(0,10)!==data.asof)return null;
   const checked=Date.parse(data.collected_at);
   if(typeof data.collected_at!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(data.collected_at)||!Number.isFinite(checked)||new Date(checked).toISOString().slice(0,19)!==data.collected_at.slice(0,19)||checked>now+300000)return null;
   const checkedParts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(checked)),checkedDay=['year','month','day'].map(type=>checkedParts.find(p=>p.type===type).value).join('-');
   if(data.asof!==checkedDay||checked<Date.UTC(start,6,1))return null;
   if(!data.team_games||Object.keys(data.team_games).length!==32||[...clubs].some(t=>!integer(data.team_games[t],0,100))||!Array.isArray(data.players)||data.players.length<500||data.players.length>5000)return null;
   const ids=new Set();
   for(const p of data.players){
    if(!integer(p.id,1000000,9999999)||ids.has(p.id)||typeof p.name!=='string'||!p.name.trim()||p.name.length>80||/[\x00-\x1f]/.test(p.name)||!['C','L','R','D'].includes(p.pos)||!integer(p.gp,0,100)||!['goals','assists','points'].every(k=>integer(p[k],0,1000))||p.points!==p.goals+p.assists||!p.gp&&p.points)return null;
    if(p.team!==null&&!clubs.has(p.team)||p.teamGP!==(p.team?data.team_games[p.team]:null)||!Array.isArray(p.clubs)||p.clubs.some(t=>!clubs.has(t)))return null;
    if(p.headshot&&!(typeof p.headshot==='string'&&p.headshot.startsWith('https://assets.nhle.com/mugs/nhl/')&&p.headshot.endsWith('/'+p.id+'.png')))return null;
    ids.add(p.id);
   }
   return data;
  }catch{return null;}
 }
 const newer=(data,previous)=>Date.parse(data.collected_at)>(Date.parse(previous?.collected_at)||0);
 return Object.freeze({url,interval,validate,newer});
})();
