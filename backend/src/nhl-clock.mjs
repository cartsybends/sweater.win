const nhlClock=value=>{if(typeof value!=='string'||!/^\d{1,2}:[0-5]\d$/.test(value))return null;const [m,s]=value.split(':').map(Number);return m*60+s;};
export function eventTime(play,gameType=2){const p=play.periodDescriptor,n=p?.number,type=p?.periodType,elapsed=nhlClock(play.timeInPeriod);if(!Number.isInteger(n)||n<1||n>20||elapsed===null)return null;if(type==='REG'&&n<=3&&elapsed<=1200)return (n-1)*1200+elapsed;if(type==='OT'&&n>=4&&elapsed<=(gameType===3?1200:300)&&(gameType===3||n===4))return 3600+(n-4)*(gameType===3?1200:300)+elapsed;return null;}
// NHL's intermission countdown measures the break, not remaining hockey time.
// Play-by-play can also advance before the header clock at a period transition.
export function gameClock(raw){
 const length=type=>type==='OT'&&raw.gameType===2?300:1200;
 const valid=p=>p&&Number.isInteger(p.number)&&p.number>=1&&p.number<=20&&(p.periodType==='REG'&&p.number<=3||p.periodType==='OT'&&p.number>=4&&(raw.gameType===3||p.number===4));
 const elapsed=c=>eventTime({periodDescriptor:{number:c.period,periodType:c.type},timeInPeriod:`${Math.floor((length(c.type)-c.seconds)/60)}:${String((length(c.type)-c.seconds)%60).padStart(2,'0')}`},raw.gameType);
 const format=c=>({...c,remaining:`${Math.floor(c.seconds/60)}:${String(c.seconds%60).padStart(2,'0')}`.padStart(5,'0')});
 const p=raw.periodDescriptor;
 if(p?.periodType==='SO'&&raw.gameType===2)return {period:p.number,type:'SO',seconds:0,remaining:'00:00',intermission:false};
 let clock=null;
 if(valid(p)){
  let descriptor=p;
  if(raw.clock?.inIntermission===true){
   const end=(raw.plays||[]).filter(play=>play.typeDescKey==='period-end'&&valid(play.periodDescriptor)&&play.periodDescriptor.number<=p.number&&play.periodDescriptor.number>=p.number-1).at(-1);
   if(end)descriptor=end.periodDescriptor;
   clock={period:descriptor.number,type:descriptor.periodType,seconds:0,intermission:true};
  }else if(Number.isInteger(raw.clock?.secondsRemaining)&&raw.clock.secondsRemaining>=0&&raw.clock.secondsRemaining<=length(p.periodType))clock={period:p.number,type:p.periodType,seconds:raw.clock.secondsRemaining,intermission:false};
 }
 let latest=null;
 for(const play of Array.isArray(raw.plays)?raw.plays:[]){
  const t=eventTime(play,raw.gameType);if(t!==null&&(!latest||t>latest.t||t===latest.t&&play.periodDescriptor.number>latest.period))latest={t,period:play.periodDescriptor.number,type:play.periodDescriptor.periodType,seconds:length(play.periodDescriptor.periodType)-nhlClock(play.timeInPeriod),intermission:play.typeDescKey==='period-end'&&raw.clock?.inIntermission===true};
 }
 // Use a published event's hockey clock when the header is still at 20:00.
 if(latest&&(!clock||latest.t>elapsed(clock)||latest.t===elapsed(clock)&&latest.period>clock.period))clock={period:latest.period,type:latest.type,seconds:latest.seconds,intermission:latest.intermission};
 return clock?format(clock):null;
}
export function currentTime(raw){
 if(['OFF','FINAL'].includes(raw.gameState)&&raw.periodDescriptor?.periodType==='OT'&&Array.isArray(raw.plays)){
  const goal=raw.plays.filter(p=>p.typeDescKey==='goal'&&p.periodDescriptor?.periodType==='OT').at(-1),ended=goal?eventTime(goal,raw.gameType):null;if(ended!==null)return ended;
 }
 const clock=gameClock(raw);if(!clock)return null;if(clock.type==='SO')return 3900;
 return eventTime({periodDescriptor:{number:clock.period,periodType:clock.type},timeInPeriod:`${Math.floor(((clock.type==='OT'&&raw.gameType===2?300:1200)-clock.seconds)/60)}:${String(((clock.type==='OT'&&raw.gameType===2?300:1200)-clock.seconds)%60).padStart(2,'0')}`},raw.gameType);
}
