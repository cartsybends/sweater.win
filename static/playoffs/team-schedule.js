let poTeamView='overview',poCalendarMonth='',poCalendarSeason=0;
const poSchedules=new Map();
const poScheduleVisible=()=>poTeamView==='schedule'&&poTab==='team'&&!!poCurrent()&&!$('view-playoffs').hidden;
const poScheduleDate=(day,options)=>new Date(day+'T12:00:00Z').toLocaleDateString(undefined,{...options,timeZone:'UTC'});
const poMonthLabel=month=>poScheduleDate(month+'-01',{month:'long',year:'numeric'});

function poScheduleEntry(){
 const team=poCurrent().abbr,year=poShared?.start||poData.start,season=year*10000+year+1;
 const key=`${team}:${season}`;
 if(!poSchedules.has(key))poSchedules.set(key,{team,year,season,data:null,attempt:0,pending:false,failed:false});
 return poSchedules.get(key);
}

function poRenderTeamViews(team){
 const scheduling=poScheduleVisible();
 $('poTeamTabs').hidden=!team;
 $('poTeamOverview').hidden=!team||scheduling;
 $('poTeamSchedule').hidden=!scheduling;
 for(const tab of $('poTeamTabs').querySelectorAll('[role=tab]')){
  const selected=tab.dataset.poTeamView===poTeamView;
  tab.setAttribute('aria-selected',String(selected));
  tab.tabIndex=selected?0:-1;
 }
 if(scheduling){poRenderSchedule(poScheduleEntry());poScheduleLoad();}
}

function poScheduleResult(game,club){
 if(game.status!=='final')return '';
 const won=game.home===club?game.hg>game.ag:game.ag>game.hg;
 return won?'W':game.end==='OT'||game.end==='SO'?'OTL':'L';
}

function poScheduleMonthSummary(games,club,future){
 if(future){
  const scheduled=games.filter(game=>game.status==='scheduled').length;
  return {value:scheduled,label:scheduled===1?'Game scheduled':'Games scheduled',spoken:`${scheduled} ${scheduled===1?'game':'games'} scheduled`};
 }
 const record={W:0,L:0,OTL:0};
 for(const game of games){
  const result=poScheduleResult(game,club);
  if(result)record[result]++;
 }
 return {value:`${record.W}–${record.L}–${record.OTL}`,label:'W–L–OTL',
  spoken:`Monthly record, ${record.W} wins, ${record.L} regulation losses, ${record.OTL} overtime or shootout losses`};
}

function poScheduleTile(game,club,day,inGameCenter){
 const home=game.home===club,opponent=home?game.away:game.home;
 const opponentName=poTeamRecord(opponent)?.name||opponent;
 const scored=game.hg!==null&&game.ag!==null;
 const forGoals=home?game.hg:game.ag,against=home?game.ag:game.hg;
 const score=scored?`${forGoals}–${against}`:'';
 const end=game.end==='OT'||game.end==='SO'?game.end:'';
 const result=poScheduleResult(game,club);
 let label=score,time='';
 if(game.status==='final'){
  label=`${{W:'Win',L:'Loss',OTL:'Overtime or shootout loss'}[result]} ${score}${end?' '+end:''}`;
 }else if(game.status==='scheduled'){
  time=game.time_tbd?'Time TBD':new Date(game.start).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
  label=time;
 }else{
  time={live:'LIVE',pending:'Final pending',postponed:'Postponed',cancelled:'Cancelled'}[game.status];
  label=time+(score?' '+score:'');
 }
 const endLabel=game.status==='final'?(end?`<small>${end}</small>`:''):`<small>${esc(time)}</small>`;
 const aria=`${poScheduleDate(day,{weekday:'long',month:'long',day:'numeric'})}, ${home?'versus':'at'} ${opponentName}, ${label}`;
 const body=`<span class="po-schedule-opponent"><small>${home?'vs':'@'}</small><img src="team-crests/${opponent}.svg" width="29" height="29" loading="lazy" alt=""><b>${opponent}</b></span><span class="po-schedule-result" data-status="${game.status}">${result?`<b data-result="${result}">${result}</b>`:''}${score?`<strong>${score}</strong>`:''}${endLabel}</span>`;
 const attributes=`class="po-schedule-game" aria-label="${esc(aria)}"`;
 return inGameCenter?`<button type="button" ${attributes} data-po-center="${game.id}">${body}</button>`:
  `<a ${attributes} href="https://www.nhl.com/gamecenter/${game.id}" target="_blank" rel="noopener noreferrer">${body}</a>`;
}

function poRenderSchedule(entry){
 const {team,year,season,data,failed}=entry;
 const status=$('poScheduleStatus'),host=$('poScheduleCalendar'),select=$('poScheduleMonth');
 const previous=$('poSchedulePrev'),next=$('poScheduleNext'),summary=$('poScheduleSummary');
 const title=`${poCurrent().name} schedule`;
 if($('poScheduleTitle').textContent!==title)$('poScheduleTitle').textContent=title;
 const seasonLabel=`${year}–${String(year+1).slice(-2)} · NHL schedule · Local time`;
 if($('poScheduleSeason').textContent!==seasonLabel)$('poScheduleSeason').textContent=seasonLabel;
 const crest=`team-crests/${team}.svg`;
 if($('poScheduleCrest').getAttribute('src')!==crest)$('poScheduleCrest').src=crest;
 const message=data?(failed||data.stale?'Last available NHL schedule · ':'NHL schedule checked · ')+poDate(data.checked_at):
  failed?'The NHL schedule is temporarily unavailable.':'Loading NHL schedule…';
 if(status.textContent!==message)status.textContent=message;
 $('poScheduleRetry').hidden=!failed&&!data?.stale;
 summary.hidden=!data;
 if(!data){
  host.replaceChildren();host._poScheduleKey='';
  previous.disabled=next.disabled=select.disabled=true;
  select.selectedIndex=-1;
  return;
 }

 const dates=data.games.map(game=>({game,day:poModel.localDay(game.start)}));
 const months=[...new Set(dates.map(({day})=>day.slice(0,7)))].sort();
 const today=poModel.localDay(Date.now());
 if(poCalendarSeason!==season){poCalendarSeason=season;poCalendarMonth=today.slice(0,7);}
 if(!months.includes(poCalendarMonth))poCalendarMonth=months.find(month=>month>=poCalendarMonth)||months.at(-1);
 const index=months.indexOf(poCalendarMonth);
 if(select._poMonths!==months.join(',')){
  select._poMonths=months.join(',');
  select.innerHTML=months.map(month=>`<option value="${month}">${esc(poMonthLabel(month))}</option>`).join('');
 }
 select.value=poCalendarMonth;
 select.disabled=false;previous.disabled=index===0;next.disabled=index===months.length-1;
 const dated=dates.filter(({day})=>day.startsWith(poCalendarMonth));
 const monthTotal=poScheduleMonthSummary(dated.map(({game})=>game),team,poCalendarMonth>today.slice(0,7));
 const summaryText=`<strong aria-hidden="true">${monthTotal.value}</strong><small aria-hidden="true">${monthTotal.label}</small><span class="po-sr">${monthTotal.spoken}</span>`;
 if(summary.innerHTML!==summaryText)summary.innerHTML=summaryText;
 const listed=new Set(poData.games?.map(game=>game.id));
 const key=JSON.stringify([team,poCalendarMonth,today,dated,dated.map(({game})=>listed.has(game.id))]);
 if(host._poScheduleKey===key)return;
 host._poScheduleKey=key;

 const [yearNumber,monthNumber]=poCalendarMonth.split('-').map(Number);
 const first=new Date(Date.UTC(yearNumber,monthNumber-1,1)).getUTCDay();
 const days=new Date(Date.UTC(yearNumber,monthNumber,0)).getUTCDate();
 const calendarDays=Math.ceil((first+days)/7)*7;
 const weekdays=Array.from({length:7},(_,i)=>`<span>${esc(poScheduleDate('2026-01-'+String(i+4).padStart(2,'0'),{weekday:'short'}))}</span>`).join('');
 const byDay=new Map();
 for(const {game,day} of dated){
  if(!byDay.has(day))byDay.set(day,[]);
  byDay.get(day).push(game);
 }
 const cells=Array.from({length:calendarDays},(_,i)=>{
  const date=i-first+1;
  if(date<1||date>days)return '<li class="po-schedule-void" aria-hidden="true"></li>';
  const day=poCalendarMonth+'-'+String(date).padStart(2,'0'),games=byDay.get(day)||[];
  const weekday=poScheduleDate(day,{weekday:'short'});
  return `<li class="po-schedule-day${games.length?' has-game':''}"${day===today?' data-today="true"':''}><time datetime="${day}"${day===today?' aria-current="date"':''}><small>${esc(weekday)}</small><b>${date}</b></time><div>${games.map(game=>poScheduleTile(game,team,day,listed.has(game.id))).join('')}</div></li>`;
 }).join('');
 host.innerHTML=`<div class="po-schedule-weekdays" aria-hidden="true">${weekdays}</div><ol class="po-schedule-grid" aria-label="${esc(title+' · '+poMonthLabel(poCalendarMonth))}">${cells}</ol>`;
}

async function poScheduleLoad(force=false){
 if(!poScheduleVisible()||document.hidden)return;
 const entry=poScheduleEntry();
 if(entry.pending||!force&&Date.now()-entry.attempt<120000)return;
 entry.pending=true;
 entry.attempt=Date.now();
 const url=new URLSearchParams({team:entry.team,season:entry.season});
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),11000);
 try{
  const response=await fetch((API_ON?API:'https://api.sweater.win')+'/api/playoffs/team-schedule?'+url,{credentials:'omit',cache:'no-store',signal:controller.signal});
  if(!response.ok)throw new Error('Schedule unavailable');
  const data=poModel.validateSchedule(await response.json(),entry.team,entry.season);
  if(!data)throw new Error('Invalid NHL schedule');
  entry.data=data;entry.failed=false;
 }catch{entry.failed=true;}
 finally{
  clearTimeout(timeout);entry.pending=false;
  if(poScheduleVisible()&&poScheduleEntry()===entry){
   const dialog=$('poGameDialog');
   if(dialog.open)dialog.dataset.dashboardPending='true';
   else poRenderSchedule(entry);
  }
 }
}

$('poTeamTabs').onclick=event=>{
 const tab=event.target.closest('[data-po-team-view]');
 if(tab&&tab.dataset.poTeamView!==poTeamView){poTeamView=tab.dataset.poTeamView;poRender();}
};
$('poTeamTabs').onkeydown=event=>{
 if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
 event.preventDefault();
 const tabs=$('poTeamTabs').querySelectorAll('[role=tab]');
 const index=event.key==='Home'?0:event.key==='End'?1:poTeamView==='overview'?1:0;
 tabs[index].click();tabs[index].focus();
};
function poMoveScheduleMonth(direction){
 const select=$('poScheduleMonth');
 const option=select.options[select.selectedIndex+direction];
 if(option){poCalendarMonth=option.value;poRenderSchedule(poScheduleEntry());}
}
$('poScheduleMonth').onchange=event=>{poCalendarMonth=event.target.value;poRenderSchedule(poScheduleEntry());};
$('poSchedulePrev').onclick=()=>poMoveScheduleMonth(-1);
$('poScheduleNext').onclick=()=>poMoveScheduleMonth(1);
$('poScheduleRetry').onclick=()=>poScheduleLoad(true);
