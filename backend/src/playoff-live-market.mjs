const ESPN='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/';
const aliases={SJ:'SJS',TB:'TBL',LA:'LAK',NJ:'NJD',UTAH:'UTA',ARI:'UTA'};
const eventId=value=>/^\d{1,12}$/.test(String(value||''))?String(value):null;
const unavailable=at=>({status:'unavailable',source:'ESPN',provider:'DraftKings',observed_at:at});
export function americanPrice(value){
 if(typeof value==='string'){
  value=value.trim().toUpperCase().replace('−','-');
  if(['EVEN','EV','PK'].includes(value))return 100;
  if(!/^[+-]?\d+$/.test(value))return null;
  value=Number(value);
 }
 return Number.isInteger(value)&&Math.abs(value)>=100&&Math.abs(value)<=100000?value:null;
}
export function matchesMarketGame(event,game){
 const competition=event?.competitions?.[0],players=competition?.competitors;
 if(!Array.isArray(players)||players.length!==2)return false;
 const teams=Object.fromEntries(players.map(p=>[p.homeAway,aliases[p.team?.abbreviation]||p.team?.abbreviation]));
 const start=Date.parse(competition.date||event.date),official=Date.parse(game.start);
 return teams.home===game.home&&teams.away===game.away&&Number.isFinite(start)&&Number.isFinite(official)&&Math.abs(start-official)<=1800000;
}
export function parseLiveMarket(summary,game,observedAt){
 const header=summary?.header,id=eventId(header?.id),observed=Date.parse(observedAt);
 if(!id||!matchesMarketGame(header,game)||!Number.isFinite(observed)||observed<Date.parse(game.start))return null;
 const base={...unavailable(observedAt),source_url:'https://www.espn.com/nhl/game/_/gameId/'+id};
 const status=header.competitions[0].status?.type;
 if(status?.state!=='in'||status.completed===true)return base;
 const rows=Array.isArray(summary.pickcenter)?summary.pickcenter:[];
 const candidates=rows.filter(row=>/^draft\s*kings$/i.test(row.provider?.name||''));
 if(candidates.length!==1)return base;
 // ESPN's close/current/top-level prices may still be the pregame line.
 // Only the explicitly identified live moneyline is an in-play quote.
 const line=candidates[0].moneyline,home=line?.home?.live,away=line?.away?.live;
 const stopped=quote=>quote?.suspended===true||quote?.isSuspended===true||['OFF','SUSPENDED','CLOSED','LOCKED'].includes(String(quote?.odds||'').trim().toUpperCase());
 if(stopped(home)||stopped(away))return {...base,status:'suspended'};
 const h=americanPrice(home?.odds),a=americanPrice(away?.odds);
 return h===null||a===null?base:{...base,status:'live',home:h,away:a};
}
export async function collectLiveMarket(game,get,date,at){
 try{
  let id=game.market?.source_url?.match(/^https:\/\/www\.espn\.com\/nhl\/game\/_\/gameId\/(\d{1,12})$/)?.[1];
  if(!id){
   const {data:board}=await get(ESPN+'scoreboard?dates='+date.replaceAll('-',''),30);
   if(!Array.isArray(board.events)||board.events.length>32)return unavailable(at);
   const matches=board.events.filter(event=>eventId(event.id)&&matchesMarketGame(event,game));
   if(matches.length!==1)return unavailable(at);
   id=eventId(matches[0].id);
  }
  const {data,observed_at}=await get(ESPN+'summary?event='+id,30);
  if(String(data.header?.id)!==id)return unavailable(at);
  return parseLiveMarket(data,game,observed_at)||unavailable(at);
 }catch{return unavailable(at);}
}
