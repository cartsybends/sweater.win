import {SHOT_MODEL} from './shot-model.mjs';
const types=['BACK','SNAP','SLAP','TIP','DEFL','WRAP','UNKNOWN'];
const map={wrist:'WRIST',snap:'SNAP',slap:'SLAP',backhand:'BACK','tip-in':'TIP',deflected:'DEFL','wrap-around':'WRAP'};
export function shotFeatures({x,y,type,attack,defend,empty,rebound}){
 if(![x,y].every(Number.isFinite)||Math.abs(x)>100||Math.abs(y)>43||x===0&&y===0||![attack,defend].every(n=>Number.isInteger(n)&&n>=3&&n<=6)||typeof empty!=='boolean'||typeof rebound!=='boolean')return null;
 const distance=Math.hypot(89-x,y),angle=Math.abs(Math.atan2(y,89-x))/Math.PI*2,d=distance/60,kind=map[type]||'UNKNOWN';
 return [1,d,Math.log1p(distance)/4,angle,angle*angle,d*angle,Number(empty),Number(empty)*d,Number(rebound),Number(rebound)*d,(attack-defend)/2,Number(attack===3),Number(defend===3),...types.map(t=>Number(t===kind))];
}
export function shotProbability(features){
 // The released domain excludes empty nets and attempts from a team's own half.
 // Training coordinates normalize shots to the offensive end; do not extrapolate.
 if(features.empty||features.x<0)return null;
 const values=shotFeatures(features);if(!values)return null;
 const raw=values.reduce((sum,x,i)=>sum+x*SHOT_MODEL.weights[i],0),[intercept,slope]=SHOT_MODEL.calibration;
 return Number(Math.max(.0001,Math.min(.995,1/(1+Math.exp(-(intercept+slope*raw))))).toFixed(5));
}
export const shotModelInfo={version:SHOT_MODEL.version,training_seasons:SHOT_MODEL.training_seasons,calibration_season:SHOT_MODEL.calibration_season,evaluation_season:SHOT_MODEL.evaluation_season,validation:SHOT_MODEL.subgroups.goalie_in_net,source:'MoneyPuck.com factual shot data',source_url:'https://moneypuck.com/data.htm',domain:'Located, unblocked offensive-half shots with a goalie in net; shootouts and empty nets excluded.'};
