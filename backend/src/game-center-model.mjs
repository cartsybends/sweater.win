import {eventTime,currentTime} from './nhl-clock.mjs';
import {penaltyTimeline,penaltyContext} from './penalty-state.mjs';
import {liveProbability} from './playoff-live-model.mjs';
import {shotProbability,shotModelInfo} from './shot-quality.mjs';
const shotKinds={'shot-on-goal':'saved',goal:'goal','missed-shot':'missed','blocked-shot':'blocked'};
const integer=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
function modelState(t,homeScore,awayScore,gameType){
 if(t<=3600){const period=Math.max(1,Math.ceil(t/1200));return {homeScore,awayScore,period,periodType:'REG',seconds:period*1200-t,gameType};}
 const length=gameType===3?1200:300,offset=t-3600,period=3+Math.ceil(offset/length);
 return {homeScore,awayScore,period,periodType:'OT',seconds:(period-3)*length-offset,gameType};
}
export function winHistory(raw,baseline,goals,endTime,penalties=[],timeline=null){
 const p=baseline.prediction;
 if(!['pregame','recorded'].includes(p?.basis)||!Number.isFinite(Date.parse(p.at))||Date.parse(p.at)>=Date.parse(baseline.start))return {status:'unavailable',reason:'pregame_unavailable',points:[]};
 if(!Number.isFinite(endTime))return {status:'unavailable',reason:'clock_unavailable',points:[]};
 const home=raw.homeTeam.score,away=raw.awayTeam.score,final=['OFF','FINAL'].includes(raw.gameState),shootout=raw.periodDescriptor?.periodType==='SO'||raw.gameOutcome?.lastPeriodType==='SO';
 const expectedHome=home-(final&&shootout&&home>away?1:0),expectedAway=away-(final&&shootout&&away>home?1:0);
 let hs=0,as=0;
 for(const g of goals){const nextH=hs+Number(g.team===baseline.home),nextA=as+Number(g.team===baseline.away);if(g.t>endTime+1||g.home_score!==nextH||g.away_score!==nextA)return {status:'unavailable',reason:'play_by_play_catching_up',points:[]};hs=nextH;as=nextA;}
 if(hs!==expectedHome||as!==expectedAway)return {status:'unavailable',reason:'play_by_play_catching_up',points:[]};
 const points=[],step=Math.max(30,Math.ceil(endTime/240/15)*15);hs=0;as=0;let tick=0;
 const add=(t,kind,event=null,before=false)=>{const state=modelState(t,hs,as,raw.gameType),penaltyState=timeline?(event?(before?timeline.before(event.id):timeline.after(event.id)):timeline.at(t)):null,value=liveProbability(p,{...state,penalties:penaltyState});if(!value)return;points.push({t,period:event?.period||state.period,period_type:event?.period_type||state.periodType,remaining:event?.remaining||`${Math.floor(state.seconds/60)}:${String(state.seconds%60).padStart(2,'0')}`,home:value.home_win,away:value.away_win,kind,...(event?{event_id:event.id}:{}),home_score:hs,away_score:as,...(penaltyState?{penalty:{...penaltyContext(penaltyState,state.periodType,raw.gameType),status:value.penalty_status==='available'?'available':'unavailable'}}:{})});};
 const events=[...goals.map(g=>({...g,kind:'goal'})),...penalties.map(g=>({...g,kind:'penalty'}))].sort((a,b)=>a.t-b.t||a.sort_order-b.sort_order);
 for(const event of events){while(tick<event.t){add(tick,'clock');tick+=step;}add(event.t,'before_'+event.kind,event,true);if(event.kind==='goal'){hs=event.home_score;as=event.away_score;}add(event.t,event.kind,event);}
 while(tick<endTime){add(tick,'clock');tick+=step;}
 if(final){points.push({t:endTime,period:raw.periodDescriptor.number,period_type:raw.periodDescriptor.periodType,remaining:raw.periodDescriptor.periodType==='OT'?goals.at(-1)?.remaining||raw.clock.timeRemaining:raw.clock.timeRemaining,home:home>away?100:0,away:away>home?100:0,kind:'final',home_score:home,away_score:away});}
 else if(!shootout){const penaltyState=timeline?.at(endTime),state={homeScore:home,awayScore:away,period:raw.periodDescriptor.number,periodType:raw.periodDescriptor.periodType,seconds:raw.clock.secondsRemaining,gameType:raw.gameType,penalties:penaltyState},prob=liveProbability(p,state);if(prob)points.push({t:endTime,period:state.period,period_type:state.periodType,remaining:raw.clock.timeRemaining||`${Math.floor(state.seconds/60)}:${String(state.seconds%60).padStart(2,'0')}`,home:prob.home_win,away:prob.away_win,kind:'current',home_score:home,away_score:away,...(penaltyState?{penalty:{...penaltyContext(penaltyState,state.periodType,raw.gameType),status:prob.penalty_status==='available'?'available':'unavailable'}}:{})});}
 else add(endTime,'clock');
 return {status:shootout&&!final?'shootout':'available',model:timeline?'sweater-live-v2':'sweater-live-v1',pregame_at:p.at,points,current:shootout&&!final?null:points.at(-1)||null};
}
export function gameCenter(raw,baseline,at){
 if(!raw||raw.id!==baseline.id||raw.homeTeam?.abbrev!==baseline.home||raw.awayTeam?.abbrev!==baseline.away||Date.parse(raw.startTimeUTC)!==Date.parse(baseline.start)||![2,3].includes(raw.gameType)||!['FUT','PRE','LIVE','CRIT','OFF','FINAL'].includes(raw.gameState))throw new Error('Invalid NHL game identity');
 const scheduled=['FUT','PRE'].includes(raw.gameState),final=['OFF','FINAL'].includes(raw.gameState);
 if(scheduled)raw={...raw,plays:raw.plays||[],rosterSpots:raw.rosterSpots||[]};
 if(!Array.isArray(raw.plays)||raw.plays.length>3000||!Array.isArray(raw.rosterSpots)||raw.rosterSpots.length>100)throw new Error('Invalid NHL events');
 if(!scheduled&&![raw.homeTeam.score,raw.awayTeam.score].every(n=>integer(n,0,30)))throw new Error('Invalid NHL score');
 if(final&&raw.homeTeam.score===raw.awayTeam.score)throw new Error('Incomplete NHL final');
 const players=new Map(raw.rosterSpots.filter(p=>integer(p.playerId,1,99999999)).map(p=>[p.playerId,{id:p.playerId,name:[p.firstName?.default,p.lastName?.default].filter(x=>typeof x==='string').join(' ').slice(0,100),number:integer(p.sweaterNumber,1,99)?p.sweaterNumber:null}]));
 const player=id=>players.get(id)||(integer(id,1,99999999)?{id,name:'Player unavailable',number:null}:null),teamFor=id=>id===raw.homeTeam.id?baseline.home:id===raw.awayTeam.id?baseline.away:null;
 const ordered=raw.plays.map((p,index)=>({p,index,t:eventTime(p,raw.gameType)})).filter(p=>p.t!==null).sort((a,b)=>a.t-b.t||(a.p.sortOrder??a.index)-(b.p.sortOrder??b.index)),shots=[],goals=[],penalties=[],seen=new Set();let previous=null;
 for(const {p,t} of ordered){
  const d=p.details||{},outcome=shotKinds[p.typeDescKey];
  if(p.typeDescKey==='penalty'&&integer(p.eventId,1,9999999)&&teamFor(d.eventOwnerTeamId)){
   if(seen.has(p.eventId))throw new Error('Duplicate NHL event');seen.add(p.eventId);
   penalties.push({id:p.eventId,t,sort_order:p.sortOrder??0,period:p.periodDescriptor.number,period_type:p.periodDescriptor.periodType,remaining:p.timeRemaining,team:teamFor(d.eventOwnerTeamId),player:player(d.committedByPlayerId),drawn_by:player(d.drawnByPlayerId),served_by:player(d.servedByPlayerId),reason:typeof d.descKey==='string'?d.descKey.slice(0,80):'penalty',minutes:integer(d.duration,0,25)?d.duration:null,type:typeof d.typeCode==='string'?d.typeCode.slice(0,12):null});
  }
  if(!outcome){previous={p,t};continue;}
  if(!integer(p.eventId,1,9999999)||seen.has(p.eventId))throw new Error('Duplicate NHL shot');seen.add(p.eventId);
  const team=d.eventOwnerTeamId===raw.homeTeam.id?baseline.home:d.eventOwnerTeamId===raw.awayTeam.id?baseline.away:null;if(!team){previous={p,t};continue;}
  const direction=p.homeTeamDefendingSide,sign=direction==='right'?(team===baseline.home?-1:1):direction==='left'?(team===baseline.home?1:-1):null;
  const located=sign!==null&&[d.xCoord,d.yCoord].every(Number.isFinite)&&Math.abs(d.xCoord)<=100&&Math.abs(d.yCoord)<=43&&!(d.xCoord===0&&d.yCoord===0);
  const x=located?d.xCoord*sign:null,y=located?d.yCoord*sign:null,situation=typeof p.situationCode==='string'&&/^[01][3-6][3-6][01]$/.test(p.situationCode)?p.situationCode:null,homeTeam=team===baseline.home;
  const attack=situation?Number(situation[homeTeam?2:1]):null,defend=situation?Number(situation[homeTeam?1:2]):null,empty=situation?situation[homeTeam?0:3]==='0':null;
  const rebound=previous?.p.typeDescKey==='shot-on-goal'&&t-previous.t>=0&&t-previous.t<=3;
  const type=typeof d.shotType==='string'?d.shotType.slice(0,30):'unknown';
  const probability=located&&situation&&outcome!=='blocked'?shotProbability({x,y,type,attack,defend,empty,rebound}):null;
  const actor=player(outcome==='goal'?d.scoringPlayerId:d.shootingPlayerId),goalie=player(d.goalieInNetId);
  const shot={id:p.eventId,t,period:p.periodDescriptor.number,period_type:p.periodDescriptor.periodType,remaining:p.timeRemaining,team,outcome,player:actor,goalie,shot_type:type,x:located?(homeTeam?x:-x):null,y:located?(homeTeam?y:-y):null,distance:located?Number(Math.hypot(89-x,y).toFixed(1)):null,angle:located?Number((Math.abs(Math.atan2(y,89-x))/Math.PI*180).toFixed(1)):null,strength:situation?`${attack}-on-${defend}`:null,empty_net:empty,rebound,xg:probability};
  if(probability===null)shot.estimate_note=outcome==='blocked'?'Blocked attempts are not assigned a shot probability.':!located?'NHL location unavailable.':empty?'Empty-net attempts are outside this shot model.':x<0?'Own-half attempts are outside this shot model.':'Shot context unavailable.';
  if(outcome==='goal')Object.assign(shot,{assists:[d.assist1PlayerId,d.assist2PlayerId].filter((id,index,ids)=>integer(id,1,99999999)&&ids.indexOf(id)===index).map(player),home_score:integer(d.homeScore,0,30)?d.homeScore:null,away_score:integer(d.awayScore,0,30)?d.awayScore:null});
  shots.push(shot);
  if(outcome==='goal')goals.push({id:p.eventId,t,sort_order:p.sortOrder??0,period:shot.period,period_type:shot.period_type,remaining:shot.remaining,team,player:actor?.name||'Scorer unavailable',home_score:d.homeScore,away_score:d.awayScore});
  previous={p,t};
 }
 const attempts=[],rounds={[baseline.home]:0,[baseline.away]:0},shootoutGoals={[baseline.home]:0,[baseline.away]:0};
 for(const {p} of raw.plays.map((p,index)=>({p,index})).filter(({p})=>raw.gameType===2&&p.periodDescriptor?.periodType==='SO').sort((a,b)=>(a.p.sortOrder??a.index)-(b.p.sortOrder??b.index))){
  const d=p.details||{},team=teamFor(d.eventOwnerTeamId),outcome=p.typeDescKey==='failed-shot-attempt'?'unsuccessful':shotKinds[p.typeDescKey];
  if(!team||!['goal','saved','missed','unsuccessful'].includes(outcome)||!integer(p.eventId,1,9999999))continue;
  if(seen.has(p.eventId))throw new Error('Duplicate NHL shootout attempt');seen.add(p.eventId);
  attempts.push({id:p.eventId,round:++rounds[team],team,outcome,player:player(outcome==='goal'?d.scoringPlayerId:d.shootingPlayerId),goalie:player(d.goalieInNetId),reason:typeof d.reason==='string'?d.reason.slice(0,80):null});if(outcome==='goal')shootoutGoals[team]++;
 }
 const shootoutStarted=raw.periodDescriptor?.periodType==='SO'||attempts.length>0,shootout={started:shootoutStarted,complete:shootoutStarted&&(final||raw.plays.some(p=>p.typeDescKey==='shootout-complete')),attempts,home_goals:shootoutGoals[baseline.home],away_goals:shootoutGoals[baseline.away]};
 const elapsed=scheduled?0:currentTime(raw),timeline=scheduled?null:penaltyTimeline(raw),forecast=scheduled?{status:'scheduled',points:[],current:null}:winHistory(raw,baseline,goals,elapsed,penalties,timeline);
 const club=side=>{const p=raw[side+'Team'];return {abbr:baseline[side],name:baseline[side],score:scheduled?null:p.score,shots:integer(p.sog,0,150)?p.sog:null,expected_goals:Number(shots.filter(s=>s.team===baseline[side]&&s.xg!==null).reduce((n,s)=>n+s.xg,0).toFixed(3)),modeled_shots:shots.filter(s=>s.team===baseline[side]&&s.xg!==null).length};};
 return {version:1,id:baseline.id,game_type:raw.gameType,checked_at:at,refresh_seconds:scheduled?60:final?60:15,source:'NHL play-by-play',source_url:`https://www.nhl.com/gamecenter/${baseline.id}`,state:raw.gameState,status:scheduled?'scheduled':final?'final':'live',home:club('home'),away:club('away'),clock:scheduled?null:{period:raw.periodDescriptor?.number,type:raw.periodDescriptor?.periodType,remaining:raw.clock?.timeRemaining||'',seconds_remaining:raw.clock?.secondsRemaining,intermission:raw.clock?.inIntermission===true},elapsed,forecast,shots,goals,penalties,shootout,shot_model:shotModelInfo};
}
