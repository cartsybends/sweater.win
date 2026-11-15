import {penaltyRegulation,penaltyOvertime} from './penalty-forecast.mjs';
// Regulation is a conditional Poisson scoring model using Sweater's saved
// pregame expected goals. NHL regular-season schedules for 2023-24, 2024-25,
// 2025-26 contain 869 overtime games, of which 278 reached a shootout.
// This estimates the overtime survival rate, not in-game calibration accuracy.
const SHOOTOUT_SHARE=278/869;
const clamp=n=>Math.max(0,Math.min(1,n));
const livePriorCache=new Map();
function regulation(homeRate,awayRate,difference,seconds,tiebreak){
 const poisson=rate=>{const p=[Math.exp(-rate)];for(let n=1;n<64;n++)p.push(p[n-1]*rate/n);return p;};
 const h=poisson(homeRate*seconds/3600),a=poisson(awayRate*seconds/3600),prefix=[];
 a.reduce((sum,p,i)=>(prefix[i]=sum+p),0);
 let win=0,tie=0;
 for(let n=0;n<h.length;n++){
  const tied=n+difference;
  if(tied>0)win+=h[n]*prefix[Math.min(tied-1,a.length-1)];
  if(tied>=0&&tied<a.length)tie+=h[n]*a[tied];
 }
 return clamp(win+tie*tiebreak);
}
export function liveProbability(prediction,{homeScore,awayScore,period,periodType,seconds,gameType=2,penalties=null}){
 const h=prediction?.home_goals,a=prediction?.away_goals,p=prediction?.home_win/100;
 if(![h,a,p].every(Number.isFinite)||h<=0||a<=0||h>12||a>12||p<=0||p>=1||![homeScore,awayScore,period,seconds].every(Number.isInteger)||homeScore<0||awayScore<0||homeScore>30||awayScore>30||![2,3].includes(gameType))return null;
 const strength=h/(h+a),tiebreak=gameType===3?strength:(1-SHOOTOUT_SHARE)*strength+SHOOTOUT_SHARE*.5;
 let current,penaltyStatus=penalties?(penalties.quality==='available'?'available':'unavailable'):null;const activePenalties=penalties?.quality==='available'&&(penalties.home.length||penalties.away.length);
 if(periodType==='REG'&&period>=1&&period<=3&&seconds>=0&&seconds<=1200){
  const remaining=(3-period)*1200+seconds,projection=activePenalties?penaltyRegulation(penalties,h,a,remaining):null;
  if(projection){const ot=projection.states.reduce((n,s)=>n+s.weight*penaltyOvertime(s.state,h,a,gameType===3?1200:300,gameType,SHOOTOUT_SHARE),0);current=regulation(projection.home,projection.away,homeScore-awayScore,3600,ot);penaltyStatus='available';}
  else{current=regulation(h,a,homeScore-awayScore,remaining,tiebreak);if(activePenalties)penaltyStatus='unavailable';}
 }else if(periodType==='OT'&&period>=4&&seconds>=0&&seconds<=(gameType===3?1200:300)){
  if(homeScore!==awayScore)current=Number(homeScore>awayScore);
  else if(activePenalties){const value=penaltyOvertime(penalties,h,a,seconds,gameType,SHOOTOUT_SHARE);if(value!==null){current=value;penaltyStatus='available';}}
  if(current===undefined&&gameType===3)current=strength;
  else if(current===undefined){const noGoal=Math.pow(SHOOTOUT_SHARE,seconds/300);current=(1-noGoal)*strength+noGoal*.5;}
 }else return null; // Shootout attempt data is required for a shootout estimate.
 const priorKey=h+':'+a+':'+gameType;let prior=livePriorCache.get(priorKey);if(prior===undefined){prior=regulation(h,a,0,3600,tiebreak);if(livePriorCache.size>=256)livePriorCache.delete(livePriorCache.keys().next().value);livePriorCache.set(priorKey,prior);}
 // Preserve the saved pregame probability as the prior; update its odds by the
 // score/clock likelihood ratio implied by the scoring model.
 const win=current<=0?0:current>=1?1:1/(1+((1-current)/current)*(prior/(1-prior))*((1-p)/p));
 const home=Number((clamp(win)*100).toFixed(4));
 return {home_win:home,away_win:Number((100-home).toFixed(4)),...(penaltyStatus?{penalty_status:penaltyStatus}:{})};
}

export function liveSnapshot(raw,game,at,penalties=null){
 if(!raw||raw.id!==game.id||raw.homeTeam?.abbrev!==game.home||raw.awayTeam?.abbrev!==game.away||Date.parse(raw.startTimeUTC)!==Date.parse(game.start)||![2,3].includes(raw.gameType))throw new Error('Mismatched NHL game');
 const state=raw.gameState;
 if(!['FUT','PRE','LIVE','CRIT','OFF','FINAL'].includes(state))throw new Error('Unsupported NHL game state');
 const result={id:game.id,home:game.home,away:game.away,start:game.start,state,at,status:['FUT','PRE'].includes(state)?'scheduled':'unavailable'};
 if(result.status==='scheduled')return result;
 const homeScore=raw.homeTeam.score,awayScore=raw.awayTeam.score;
 if(![homeScore,awayScore].every(n=>Number.isInteger(n)&&n>=0&&n<=30))throw new Error('Invalid NHL score');
 Object.assign(result,{home_score:homeScore,away_score:awayScore});
 const type=raw.periodDescriptor?.periodType,period=raw.periodDescriptor?.number;
 if(['OFF','FINAL'].includes(state)){
  const end=raw.gameOutcome?.lastPeriodType||type;
  if(homeScore===awayScore||!['REG','OT','SO'].includes(end))throw new Error('Incomplete NHL final');
  return {...result,status:'final',end};
 }
 const seconds=raw.clock?.secondsRemaining;
 if(!Number.isInteger(period)||!Number.isInteger(seconds)||seconds<0||seconds>1200||!['REG','OT','SO'].includes(type))throw new Error('Invalid NHL game clock');
 Object.assign(result,{period,period_type:type,seconds_remaining:seconds,intermission:raw.clock.inIntermission===true});
 const p=game.prediction;
 if(!['pregame','recorded'].includes(p?.basis)||!Number.isFinite(Date.parse(p.at))||Date.parse(p.at)>=Date.parse(game.start)||Date.parse(p.at)>Date.parse(at))return {...result,reason:'pregame_unavailable'};
 const probabilities=liveProbability(p,{homeScore,awayScore,period,periodType:type,seconds,gameType:raw.gameType,penalties});
 return probabilities?{...result,...probabilities,status:'live',model:probabilities.penalty_status==='available'?'sweater-live-v2':'sweater-live-v1',pregame_at:p.at}:{...result,reason:type==='SO'?'shootout':'model_unavailable'};
}
