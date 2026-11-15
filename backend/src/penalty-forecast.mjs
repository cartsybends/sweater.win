import {PENALTY_RATES} from './penalty-rates.mjs';
import {copyPenaltyState,advancePenalties,penaltyStrength,releaseMinor} from './penalty-state.mjs';
const penaltyOpposite=s=>s==='home'?'away':'home';
function stateRates(state,h,a,baseHome,baseAway,periodType,gameType){const strength=penaltyStrength(state,periodType,gameType);if(strength.home===strength.away)return {home:baseHome,away:baseAway,side:null};const home=PENALTY_RATES.rates[`${strength.home}v${strength.away}`],away=PENALTY_RATES.rates[`${strength.away}v${strength.home}`];if(!home||!away)return null;return {home:home.per_second*h/PENALTY_RATES.baseline_goals_per_team_game,away:away.per_second*a/PENALTY_RATES.baseline_goals_per_team_game,side:strength.home>strength.away?'home':'away'};}
const hasTime=s=>s.home.length||s.away.length;
const nextChange=s=>Math.min(...s.home.concat(s.away).filter(p=>p.running).map(p=>p.legs[0].seconds));
function penaltyStateKey(s){return ['home','away'].map(side=>s[side].map(p=>`${p.id}:${p.running?1:0}:${p.legs.map(l=>Math.round(l.seconds*10)+(l.cancel?'c':'m')).join('.')}`).join(',')).join('|');}
export function penaltyRegulation(state,h,a,seconds){
 if(state.quality!=='available')return null;
 const baseHome=h/3600,baseAway=a/3600;if(!hasTime(state))return {home:baseHome*seconds,away:baseAway*seconds,states:[{state:copyPenaltyState(state),weight:1}]};
 const all=state.home.concat(state.away);
 // Exact expected exposure for a single minor or major; goals can end a minor.
 if(all.length===1&&all[0].legs.length===1){const rates=stateRates(state,h,a,baseHome,baseAway,'REG',2);if(!rates)return null;const p=all[0],span=Math.min(seconds,p.legs[0].seconds),lambda=rates[rates.side],cancel=p.legs[0].cancel,exposure=cancel?-Math.expm1(-lambda*span)/lambda:span,advanced=advancePenalties(copyPenaltyState(state),seconds),survival=cancel&&hasTime(advanced)?Math.exp(-lambda*span):1,states=[{state:advanced,weight:survival}];if(cancel&&hasTime(advanced)){const released=copyPenaltyState(state);releaseMinor(released,rates.side);advancePenalties(released,seconds);states.push({state:released,weight:1-survival});}return {home:baseHome*seconds+(rates.home-baseHome)*exposure,away:baseAway*seconds+(rates.away-baseAway)*exposure,states};}
 if(all.length===1&&all[0].legs.length===2&&all[0].legs.every(l=>l.cancel)){
  const rates=stateRates(state,h,a,baseHome,baseAway,'REG',2);if(!rates)return null;const p=all[0],owner=state.home.length?'home':'away',r1=p.legs[0].seconds,r2=p.legs[1].seconds,lambda=rates[rates.side],f=t=>-Math.expm1(-lambda*Math.max(0,t))/lambda,upper=Math.min(r1,seconds),lower=Math.max(0,seconds-r2),flat=Math.min(upper,lower);
  let exposure=f(Math.min(seconds,r1))+f(r2)*(-Math.expm1(-lambda*flat));if(upper>lower)exposure+=(Math.exp(-lambda*lower)-Math.exp(-lambda*upper))/lambda-Math.exp(-lambda*seconds)*(upper-lower);if(seconds>=r1)exposure+=Math.exp(-lambda*r1)*f(Math.min(r2,seconds-r1));
  const states=[],survival=Math.exp(-lambda*seconds);if(seconds<r1)states.push({state:advancePenalties(copyPenaltyState(state),seconds),weight:survival});else if(seconds<r1+r2)states.push({state:advancePenalties(copyPenaltyState(state),seconds),weight:survival});
  // A first PP goal at u leaves phase two active at the horizon. Its density
  // conditional on no second goal is constant; five-second bins keep this
  // small OT-carryover mixture bounded without simulating score paths.
  for(let u=lower;u<upper;){const width=Math.min(5,upper-u),mid=u+width/2,remaining=r2-seconds+mid;if(remaining>0){const next=copyPenaltyState(state);next[owner][0].legs=[{seconds:remaining,cancel:true}];states.push({state:next,weight:lambda*survival*width});}u+=width;}
  const activeMass=states.reduce((n,s)=>n+s.weight,0),empty=copyPenaltyState(state);empty[owner]=[];if(activeMass<1)states.push({state:empty,weight:1-activeMass});return {home:baseHome*seconds+(rates.home-baseHome)*exposure,away:baseAway*seconds+(rates.away-baseAway)*exposure,states};
 }
 let states=[{state:copyPenaltyState(state),weight:1}],elapsed=0,home=0,away=0,steps=0,operations=0;
 while(elapsed<seconds-1e-8){
  operations+=states.length;if(++steps>200||operations>5000)return null;
  if(states.every(s=>!hasTime(s.state))){home+=baseHome*(seconds-elapsed);away+=baseAway*(seconds-elapsed);break;}
  const canChangeOnGoal=states.some(s=>{const rates=stateRates(s.state,h,a,baseHome,baseAway,'REG',2);return rates?.side&&s.state[penaltyOpposite(rates.side)].some(p=>p.running&&p.legs[0].cancel);});
  const dt=Math.min(canChangeOnGoal?5:Infinity,seconds-elapsed,...states.filter(s=>hasTime(s.state)).map(s=>nextChange(s.state))),next=new Map();
  const put=(state,weight)=>{if(weight<1e-9)return;const key=penaltyStateKey(state),existing=next.get(key);if(existing)existing.weight+=weight;else next.set(key,{state,weight});};
  for(const scenario of states){const rates=stateRates(scenario.state,h,a,baseHome,baseAway,'REG',2);if(!rates)return null;home+=scenario.weight*rates.home*dt;away+=scenario.weight*rates.away*dt;
   const canRelease=rates.side&&scenario.state[penaltyOpposite(rates.side)].some(p=>p.running&&p.legs[0].cancel),probability=canRelease?-Math.expm1(-rates[rates.side]*dt):0;
   put(advancePenalties(copyPenaltyState(scenario.state),dt),scenario.weight*(1-probability));if(probability){const released=advancePenalties(copyPenaltyState(scenario.state),dt/2);releaseMinor(released,rates.side);advancePenalties(released,dt/2);put(released,scenario.weight*probability);}
  }
  states=[...next.values()];if(states.length>256)return null;const mass=states.reduce((n,s)=>n+s.weight,0);if(mass<.99999)return null;for(const s of states)s.weight/=mass;elapsed+=dt;
 }
 return {home,away,states};
}
export function penaltyOvertime(state,h,a,seconds,gameType,shootoutShare){
 if(state.quality!=='available')return null;
 const strength=h/(h+a),total=-Math.log(shootoutShare)/300,baseHome=gameType===3?h/3600:total*strength,baseAway=gameType===3?a/3600:total*(1-strength),limit=gameType===3?3600:seconds;
 let current=copyPenaltyState(state),left=limit,survival=1,win=0;
 while(left>1e-8&&hasTime(current)){const rates=stateRates(current,h,a,baseHome,baseAway,'OT',gameType);if(!rates)return null;const dt=Math.min(left,nextChange(current)),sum=rates.home+rates.away,goal=-Math.expm1(-sum*dt);win+=survival*goal*rates.home/sum;survival*=Math.exp(-sum*dt);advancePenalties(current,dt);left-=dt;}
 if(gameType===3)return win+survival*strength;
 const noGoal=Math.exp(-(baseHome+baseAway)*left);return win+survival*((1-noGoal)*strength+noGoal*.5);
}
export const penaltyRateInfo={version:PENALTY_RATES.version,source:PENALTY_RATES.source,fit_seasons:PENALTY_RATES.fit_seasons,validation_season:PENALTY_RATES.validation_season,validation_scope:PENALTY_RATES.validation.scope};
