import {matchesMarketGame} from './playoff-live-market.mjs';
const locationClock=value=>{if(typeof value!=='string'||!/^\d{1,2}:[0-5]\d$/.test(value))return null;const [m,s]=value.split(':').map(Number);return m*60+s;};
const locationName=value=>typeof value==='string'?value.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,''):'';
export function goalLocationCandidates(data,game){return data.shots.filter(s=>s.outcome==='goal'&&s.x!==null&&(s.team===game.home?s.x<0:s.x>0));}
export function goalLocationCorrections(raw,game,data,summary,id){
 const corrections=new Map(),header=summary?.header,competition=header?.competitions?.[0];
 if(String(header?.id)!==id||!matchesMarketGame(header,game)||Date.parse(competition.date)!==Date.parse(game.start)||!Array.isArray(summary.plays)||summary.plays.length>3000)return corrections;
 if(!competition.competitors.every(c=>/^\d{1,12}$/.test(String(c.team?.id||'')))||String(competition.competitors[0].team.id)===String(competition.competitors[1].team.id))return corrections;
 const teams=Object.fromEntries(competition.competitors.map(c=>[c.homeAway,String(c.team.id)]));
 for(const shot of goalLocationCandidates(data,game)){
  const original=raw.plays.find(p=>p.eventId===shot.id),sign=original?.homeTeamDefendingSide==='left'?(shot.team===game.home?1:-1):original?.homeTeamDefendingSide==='right'?(shot.team===game.home?-1:1):null;
  if(sign===null)continue;
  const team=teams[shot.team===game.home?'home':'away'],time=locationClock(original.timeInPeriod);
  const matches=summary.plays.filter(play=>play.scoringPlay===true&&String(play.type?.id)==='505'&&play.period?.number===shot.period&&locationClock(play.clock?.displayValue)===time&&String(play.team?.id)===team&&play.homeScore===shot.home_score&&play.awayScore===shot.away_score);
  if(matches.length!==1)continue;
  const play=matches[0],scorer=play.participants?.find(p=>p.type==='scorer')?.athlete?.displayName,point=play.coordinate;
  if(!locationName(scorer)||locationName(scorer)!==locationName(shot.player?.name)||![point?.x,point?.y].every(Number.isFinite)||Math.abs(point.x)>100||Math.abs(point.y)>43||point.x*sign<25)continue;
  corrections.set(shot.id,{x:point.x,y:point.y,url:'https://www.espn.com/nhl/game/_/gameId/'+id});
 }
 return corrections;
}
