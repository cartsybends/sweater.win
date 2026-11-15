import {eventTime} from './nhl-clock.mjs';
const copyPenalty=p=>({...p,legs:p.legs.map(l=>({...l}))});
export const copyPenaltyState=s=>({home:s.home.map(copyPenalty),away:s.away.map(copyPenalty),quality:s.quality,reason:s.reason||null});
const sides=['home','away'],opposite=side=>side==='home'?'away':'home';
function promote(state){for(const side of sides){const list=state[side];let active=list.filter(p=>p.running).length;for(const p of list)if(!p.running&&active<2){p.running=true;active++;}}}
export function advancePenalties(state,seconds){promote(state);let left=Math.max(0,seconds);while(left>1e-8){const running=sides.flatMap(side=>state[side].filter(p=>p.running));if(!running.length)break;const step=Math.min(left,...running.map(p=>p.legs[0].seconds));for(const p of running)p.legs[0].seconds-=step;left-=step;for(const side of sides){for(const p of state[side])if(p.running&&p.legs[0].seconds<=1e-8)p.legs.shift();state[side]=state[side].filter(p=>p.legs.length);}promote(state);}return state;}
export function penaltyStrength(state,periodType='REG',gameType=2){const h=state.home.filter(p=>p.running).length,a=state.away.filter(p=>p.running).length;if(periodType==='OT'&&gameType===2){const d=a-h;return d>=0?{home:Math.min(5,3+d),away:3}:{home:3,away:Math.min(5,3-d)};}return {home:5-h,away:5-a};}
export function releaseMinor(state,scorer,periodType='REG',gameType=2,observed=false){const strength=penaltyStrength(state,periodType,gameType),other=opposite(scorer);if(strength[scorer]<=strength[other])return false;const candidates=state[other].filter(p=>p.running&&p.legs[0].cancel);if(!candidates.length)return false;candidates.sort((a,b)=>a.legs[0].seconds-b.legs[0].seconds||a.legs.length-b.legs.length||a.id-b.id);const tied=candidates.filter(p=>Math.abs(p.legs[0].seconds-candidates[0].legs[0].seconds)<1e-8);if(observed&&new Set(tied.map(p=>p.legs.length)).size>1){state.quality='unavailable';state.reason='ambiguous_minor_release';}const p=candidates[0];p.legs.shift();state[other]=state[other].filter(p=>p.legs.length);promote(state);return true;}
function leg(seconds,cancel){return {seconds,cancel};}
function assessed(play,raw){const d=play.details||{},side=d.eventOwnerTeamId===raw.homeTeam.id?'home':d.eventOwnerTeamId===raw.awayTeam.id?'away':null,type=d.typeCode,duration=d.duration;if(!side||!Number.isInteger(play.eventId)||play.eventId<1)return {unsupported:true};if(['MIS','GAM','GM','PS'].includes(type))return null;let legs;if(['MIN','BEN'].includes(type)&&duration===2)legs=[leg(120,true)];else if(['MIN','DBL','BEN'].includes(type)&&duration===4)legs=[leg(120,true),leg(120,true)];else if(type==='MAJ'&&duration===5||type==='MAT'&&[5,25].includes(duration))legs=[leg(300,false)];else return {unsupported:true};return {id:play.eventId,side,player:d.committedByPlayerId||null,legs,running:false};}
function batchPenalties(state,plays,t,periodType,gameType,raw){
 const plans=[];for(const play of plays){const p=assessed(play,raw);if(p?.unsupported){state.quality='unavailable';state.reason='unsupported_penalty';}else if(p)plans.push(p);}
 const home=plans.filter(p=>p.side==='home'),away=plans.filter(p=>p.side==='away');
 // One minor each at otherwise full strength is 4-on-4 in regulation.
 const pairedFour=periodType==='REG'&&!state.home.length&&!state.away.length&&home.length===1&&away.length===1&&plans.every(p=>p.legs.length===1&&p.legs[0].seconds===120);
 if(!pairedFour){
  for(const cancel of [false,true])for(const h of home){while(h.legs.some(l=>l.cancel===cancel)){const a=away.find(p=>p.legs.some(l=>l.cancel===cancel));if(!a)break;const hi=h.legs.findIndex(l=>l.cancel===cancel),ai=a.legs.findIndex(l=>l.cancel===cancel);h.legs.splice(hi,1);a.legs.splice(ai,1);}}
  const remain=plans.filter(p=>p.legs.length);
  // Rule 19.4: final five minutes / OT, minor versus major -> major differential.
  if((t>=3300||periodType==='OT')&&remain.length===2&&remain[0].side!==remain[1].side){const major=remain.find(p=>p.legs.length===1&&!p.legs[0].cancel),minor=remain.find(p=>p.legs.every(l=>l.cancel));if(major&&minor&&[1,2].includes(minor.legs.length)){major.legs[0].seconds-=minor.legs.reduce((n,l)=>n+l.seconds,0);minor.legs=[];}}
 }
 for(const p of plans.filter(p=>p.legs.length)){
  const same=p.player&&state[p.side].find(x=>x.player===p.player);
  if(same){const existing=same;existing.legs.push(...p.legs);if(plans.some(plan=>plan.id===existing.id))existing.legs.sort((a,b)=>Number(a.cancel)-Number(b.cancel));if(existing.legs.length>4){state.quality='unavailable';state.reason='unsupported_penalty_combination';}}
  else state[p.side].push(p);
 }
 if(state.home.length>6||state.away.length>6){state.quality='unavailable';state.reason='excess_penalty_queue';}promote(state);
}
export function penaltyTimeline(raw){
 if(!Array.isArray(raw.plays)||raw.plays.length>3000)throw Error('Invalid penalty play log');
 const rows=raw.plays.map((p,index)=>({p,index,t:eventTime(p,raw.gameType)})).filter(r=>r.t!==null).sort((a,b)=>a.t-b.t||(a.p.sortOrder??a.index)-(b.p.sortOrder??b.index)),state={home:[],away:[],quality:'available',reason:null},snapshots=[{t:0,order:-1,state:copyPenaltyState(state)}],before=new Map(),after=new Map();let last=0,penaltyShot=null;
 const snapshot=(r,s)=>({t:r.t,order:r.p.sortOrder??r.index,state:copyPenaltyState(s)});
 for(let i=0;i<rows.length;i++){
  const r=rows[i],p=r.p;advancePenalties(state,r.t-last);last=r.t;if(penaltyShot&&penaltyShot.t!==r.t)penaltyShot=null;
  if(p.typeDescKey==='penalty'){
   const batch=[r];while(i+1<rows.length&&rows[i+1].t===r.t&&rows[i+1].p.periodDescriptor.number===p.periodDescriptor.number&&['penalty','stoppage','period-end'].includes(rows[i+1].p.typeDescKey)){const next=rows[++i];if(next.p.typeDescKey==='penalty')batch.push(next);}
   for(const b of batch){before.set(b.p.eventId,copyPenaltyState(state));if(b.p.details?.typeCode==='PS')penaltyShot={t:r.t};}
   batchPenalties(state,batch.map(b=>b.p),r.t,p.periodDescriptor.periodType,raw.gameType,raw);
   for(const b of batch)after.set(b.p.eventId,copyPenaltyState(state));snapshots.push(snapshot(batch.at(-1),state));continue;
  }
  const oldQuality=state.quality,oldReason=state.reason;
  // Compare only known in-net on-ice counts. Extra attackers never create a PP.
  const situation=p.situationCode;
  if(typeof situation==='string'&&/^1[3-6][3-6]1$/.test(situation)){
   const strength=penaltyStrength(state,p.periodDescriptor.periodType,raw.gameType),actual={home:Number(situation[2]),away:Number(situation[1])},ot=p.periodDescriptor.periodType==='OT'&&raw.gameType===2;
   const differs=ot?strength.home-strength.away!==actual.home-actual.away:strength.home!==actual.home||strength.away!==actual.away;if(differs&&state.quality==='available'){state.quality='unavailable';state.reason='manpower_mismatch';}else if(!differs&&state.reason==='ambiguous_minor_release'){state.quality='available';state.reason=null;}
  }
  if(p.typeDescKey==='goal')before.set(p.eventId,copyPenaltyState(state));
  if(p.typeDescKey==='goal'&&!penaltyShot){const side=p.details?.eventOwnerTeamId===raw.homeTeam.id?'home':p.details?.eventOwnerTeamId===raw.awayTeam.id?'away':null;if(side)releaseMinor(state,side,p.periodDescriptor.periodType,raw.gameType,true);}
  if(p.typeDescKey==='faceoff')penaltyShot=null;
  if(!state.home.length&&!state.away.length&&state.quality==='unavailable'&&situation==='1551'){state.quality='available';state.reason=null;}
  if(p.typeDescKey==='goal')after.set(p.eventId,copyPenaltyState(state));if(p.typeDescKey==='goal'||oldQuality!==state.quality||oldReason!==state.reason)snapshots.push(snapshot(r,state));
 }
 const at=t=>{let lo=0,hi=snapshots.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(snapshots[mid].t<=t)lo=mid;else hi=mid-1;}return advancePenalties(copyPenaltyState(snapshots[lo].state),t-snapshots[lo].t);};
 return {at,before:id=>before.has(id)?copyPenaltyState(before.get(id)):null,after:id=>after.has(id)?copyPenaltyState(after.get(id)):null};
}
export function penaltyContext(state,periodType='REG',gameType=2){const strength=penaltyStrength(state,periodType,gameType),side=strength.home>strength.away?'home':strength.away>strength.home?'away':null;let remaining=0;if(side){const future=copyPenaltyState(state);for(let n=0;n<30;n++){const running=future.home.concat(future.away).filter(p=>p.running);if(!running.length)break;const dt=Math.min(...running.map(p=>p.legs[0].seconds));remaining+=dt;advancePenalties(future,dt);const next=penaltyStrength(future,periodType,gameType);if(next[side]<=next[opposite(side)])break;}}return {status:state.quality,reason:state.reason,home_skaters:strength.home,away_skaters:strength.away,power_play:side,remaining};}
export function penaltyScoreMatches(raw){if(!Array.isArray(raw.plays)||!Number.isInteger(raw.homeTeam?.score)||!Number.isInteger(raw.awayTeam?.score))return false;let home=0,away=0;for(const p of raw.plays)if(p.typeDescKey==='goal'&&p.periodDescriptor?.periodType!=='SO'){if(p.details?.eventOwnerTeamId===raw.homeTeam.id)home++;else if(p.details?.eventOwnerTeamId===raw.awayTeam.id)away++;else return false;}const shootout=['OFF','FINAL'].includes(raw.gameState)&&(raw.periodDescriptor?.periodType==='SO'||raw.gameOutcome?.lastPeriodType==='SO');return home===raw.homeTeam.score-Number(shootout&&raw.homeTeam.score>raw.awayTeam.score)&&away===raw.awayTeam.score-Number(shootout&&raw.awayTeam.score>raw.homeTeam.score);}
