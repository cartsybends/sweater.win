// A visible Game Center polls one compact, edge-cached NHL feed. Closing it or
// hiding the document aborts the request and stops its polling timer.
let poGCGame=null,poGCData=null,poGCTimer=null,poGCController=null,poGCRequest=0,poGCSelected=null,poGCShots=[],poGCFrame=0,poGCPoint=null,poGCReturn=null,poGCReturnID=null;
const poGCDialog=$('poGameDialog'),poGCPercent=n=>Number.isFinite(n)?(n<.1&&n>0?'<0.1':n>99.9&&n<100?'>99.9':n.toFixed(1))+'%':'—';
const poGCName=abbr=>poTeamRecord(abbr)?.name||abbr;
function poGCStop(){clearTimeout(poGCTimer);poGCTimer=null;poGCRequest++;poGCController?.abort();poGCController=null;cancelAnimationFrame(poGCFrame);poGCFrame=0;}
function poCloseGameCenter(){poGCStop();if(poGCDialog.open)poGCDialog.close();poGCGame=null;poGCData=null;}
function poGCStatus(delayed=false){
 if(!$('poGCUpdated'))return;
 $('poGCUpdated').dataset.delayed=String(delayed||!!poGCData?.stale);
 $('poGCUpdated').textContent=poGCData?(delayed||poGCData.stale?'Update delayed · Showing feed checked ':'NHL feed checked ')+poDate(poGCData.checked_at)+(poGCData.status==='live'?' · Checks about every 15 seconds':''):delayed?'NHL feed temporarily unavailable. Retrying automatically.':'Connecting to NHL play-by-play…';
}
function poGCMarket(){
 if(!poGCDialog.open||!poGCGame||!$('poGCMarket'))return;
 const g=(poData?.games||[]).find(g=>g.id===poGCGame.id)||poGCGame;
 $('poGCMarket').innerHTML=`<p class="po-gc-subtitle">${esc(g.away)} / ${esc(g.home)} · American odds</p>${poMarketMoneyline(poEffectiveGame(g))}`;
 const panel=$('poGCAvailability'),key=JSON.stringify([g.context,poData?.goalie_leaders]);
 if(panel.dataset.context!==key){const active=panel.contains(document.activeElement)?document.activeElement.getAttribute('href'):null;panel.innerHTML='<h3>Team availability</h3>'+poAvailabilityBody(g,true);panel.dataset.context=key;if(active)[...panel.querySelectorAll('a')].find(a=>a.getAttribute('href')===active)?.focus({preventScroll:true});}
}
function poGCOpen(id,trigger){
 const g=(poData?.games||[]).find(g=>String(g.id)===String(id));if(!g)return;
 poGCStop();poGCGame=g;poGCData=null;poGCSelected=null;poGCReturn=trigger;poGCReturnID=g.id;
 $('poGCBody').innerHTML=`<div id="poGCScore" class="po-gc-score"></div><p id="poGCUpdated" class="po-gc-update" role="status"></p>
 <div class="po-gc-tabs" role="tablist" aria-label="Game Center views"><button type="button" id="poGCTabLive" role="tab" aria-selected="true" aria-controls="poGCLive" data-gc-tab="live">Game Center</button><button type="button" id="poGCTabAvailability" role="tab" aria-selected="false" aria-controls="poGCAvailability" tabindex="-1" data-gc-tab="availability">Team availability</button></div>
 <div id="poGCLive" role="tabpanel" aria-labelledby="poGCTabLive"><div class="po-gc-layout"><div>
 <section class="po-gc-panel"><h3>Win probability</h3><p class="po-gc-subtitle">Both sides of the game. Sweater estimates, including overtime and shootouts.</p><div id="poGCLegend" class="po-gc-legend"></div><div id="poGCChart" class="po-gc-chart"></div><p id="poGCReadout" class="po-gc-readout" aria-live="polite"></p></section>
 <section class="po-gc-panel"><h3>The chances, on ice</h3><p class="po-gc-subtitle">Explore every recorded attempt. Larger dots mean a higher estimated chance of scoring; goals have a star.</p>
 <div class="po-gc-filters"><label>Team<select id="poGCTeam"><option value="">Both</option><option value="${g.away}">${esc(g.away)}</option><option value="${g.home}">${esc(g.home)}</option></select></label><label>Period<select id="poGCPeriod"><option value="">All periods</option></select></label><label>Attempts<select id="poGCOutcome"><option value="unblocked">Shots</option><option value="goal">Goals</option><option value="saved">Saved</option><option value="missed">Missed</option><option value="blocked">Blocked</option><option value="all">All attempts</option></select></label></div>
 <div id="poGCRink" class="po-gc-rink" role="group" aria-label="Shot locations on a top-down hockey rink"></div><div class="po-gc-rink-key"><span><i class="po-gc-swatch away"></i>${esc(g.away)} attacks ←</span><span>● Saved &nbsp; ◇ Missed &nbsp; ★ Goal &nbsp; × Blocked</span><span><i class="po-gc-swatch"></i>${esc(g.home)} attacks →</span></div>
 <div id="poGCShot" class="po-gc-shot-detail" aria-live="polite"></div><p id="poGCShotCount" class="po-gc-rink-note"></p><div id="poGCShotList" class="po-gc-shot-list" aria-label="Shot event list"></div><p class="po-gc-rink-note">Positions are aligned to one attacking direction per team across every period. Blocked markers indicate the reported block location. Shootout attempts are excluded.</p></section></div>
 <aside class="po-gc-rail"><section class="po-gc-panel"><h3>Before puck drop</h3><p class="po-gc-subtitle">${g.prediction.basis==='reconstructed'?'Reconstructed forecast':'Saved pregame forecast'}</p><div class="po-gc-pregame">${['away','home'].map(s=>`<span>${esc(g[s])}<b>${poGCPercent(g.prediction[s+'_win'])}</b></span>`).join('')}</div></section><section class="po-gc-panel po-gc-market"><h3>Market moneyline</h3><div id="poGCMarket"></div></section><section class="po-gc-panel"><h3>Shot quality</h3><div id="poGCQuality"></div></section>
 <details class="po-gc-method"><summary>How these estimates work</summary><p>The win curve uses Sweater’s saved pregame expected goals and win probability, then conditions on score and time remaining. It does not yet adjust for in-game shot quality, penalties, a pulled goalie, or individual shootout attempts. It is a beta model, not a live sportsbook quote.</p><p>Shot percentages come from Sweater’s separate logistic shot model: distance, angle, shot type, rebound and skater counts. It uses factual shots and goals from the 2023–24 and 2024–25 seasons, calibration on 2025–26, and a held-out 2026–27 snapshot. It makes no individual shooter or goalie adjustment.</p><p>On 25,818 held-out goalie-in-net attempts, Brier score was 0.0637 (lower is better). This does not establish future accuracy or superiority to another model. Empty nets, own-half shots, blocked attempts, missing context and shootouts receive no shot percentage. Shot-quality totals cover supported attempts only.</p><p>Official events: <a id="poGCNHL" href="https://www.nhl.com/gamecenter/${g.id}" target="_blank" rel="noopener noreferrer">NHL Gamecenter ↗</a>. Factual training data: <a href="https://moneypuck.com/data.htm" target="_blank" rel="noopener noreferrer">MoneyPuck.com ↗</a>. MoneyPuck does not supply these live predictions.</p><p>Checks target 15 seconds while this view is open and visible; upstream publication, caching and network delays still apply. The curve is reconstructed from the current official event log and a frozen pregame forecast; NHL corrections can revise earlier points.</p></details></aside></div></div>
 <section id="poGCAvailability" role="tabpanel" aria-labelledby="poGCTabAvailability" class="po-gc-panel po-gc-availability" hidden><h3>Team availability</h3>${poAvailabilityBody(g,true)}</section>`;
 $('poGCAvailability').dataset.context=JSON.stringify([g.context,poData?.goalie_leaders]);poGCScore();poGCStatus();poGCChart();poGCRink();poGCQuality();
 if(!poGCDialog.open)poGCDialog.showModal();$('poGCClose').focus();poGCMarket();poGCLoad();
}
function poGCScore(){
 const d=poGCData,g=poGCGame,phase=d?.status==='final'?'Final'+(d.clock?.type==='REG'?'':` / ${d.clock?.type||''}`):d?.status==='live'?`${d.clock?.type==='SO'?'Shootout':d.clock?.type==='OT'?'OT':`P${d.clock?.period||''}`} · ${d.clock?.intermission?'Intermission':d.clock?.remaining||''}`:new Date(g.start).toLocaleString(undefined,{weekday:'short',hour:'numeric',minute:'2-digit'});
 const club=s=>`<div class="po-gc-club"><div><b>${esc(poGCName(g[s]))}</b><small>${s==='home'?'Home':'Away'}${Number.isInteger(d?.[s].shots)?` · ${d[s].shots} shots`:''}</small></div><img src="team-crests/${g[s]}.svg" alt="${g[s]}"></div>`;
 $('poGCScore').innerHTML=club('away')+`<div class="po-gc-tally"><b>${d&&d.status!=='scheduled'?d.away.score+' – '+d.home.score:'vs'}</b><small>${d?.status==='live'?'<span class="po-live-match">LIVE</span> ':''}${esc(phase)}</small></div>`+club('home');
}
async function poGCLoad(){
 if(!poGCDialog.open||!poGCGame||document.hidden||poGCController)return;
 clearTimeout(poGCTimer);const g=poGCGame,request=++poGCRequest,controller=new AbortController();poGCController=controller;const timeout=setTimeout(()=>controller.abort(),18000);
 try{
  const r=await fetch((API_ON?API:'https://api.sweater.win')+'/api/playoffs/game?id='+g.id,{credentials:'omit',cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();
  const d=GAME_CENTER.validate(await r.json(),g);if(!d||poGCData&&Date.parse(d.checked_at)<Date.parse(poGCData.checked_at))throw Error();
  if(request!==poGCRequest||!poGCDialog.open)return;
  const changed=JSON.stringify([d.elapsed,d.forecast,d.shots,d.home,d.away])!==JSON.stringify([poGCData?.elapsed,poGCData?.forecast,poGCData?.shots,poGCData?.home,poGCData?.away]);poGCData=d;
  poGCStatus();if(changed){poGCScore();poGCChart();poGCPeriods();poGCRink();poGCQuality();}poGCMarket();
 }catch{if(request===poGCRequest)poGCStatus(true);}
 finally{clearTimeout(timeout);if(request===poGCRequest){poGCController=null;if(poGCDialog.open&&!document.hidden)poGCTimer=setTimeout(poGCLoad,poGCData?.refresh_seconds*1000||15000);}}
}
function poGCChart(){
 const d=poGCData,g=poGCGame,forecast=d?.forecast,points=forecast?.points||[],latest=forecast?.status==='scheduled'?{home:g.prediction.home_win,away:g.prediction.away_win}:forecast?.current;
 $('poGCLegend').innerHTML=['away','home'].map(s=>`<span><i class="po-gc-swatch ${s}"></i><img src="team-crests/${g[s]}.svg" alt=""><span>${esc(g[s])}</span><b>${poGCPercent(latest?.[s])}</b></span>`).join('');
 const host=$('poGCChart');
 if(!points.length){host.innerHTML=`<div class="po-gc-empty">${!d?'Connecting to the game…':forecast.status==='scheduled'?'The live curve begins at puck drop.':forecast.reason==='pregame_unavailable'?'A saved pregame forecast is unavailable for this game.':forecast.reason==='play_by_play_catching_up'?'The official event log is catching up with the score.':'Win probability is temporarily unavailable.'}</div>`;$('poGCReadout').textContent='The shot map and team availability remain available independently.';return;}
 const w=Math.max(260,host.clientWidth),h=host.clientHeight,left=40,right=w-12,top=15,bottom=h-30,max=Math.max(3600,d.elapsed||0),x=t=>left+t/max*(right-left),y=p=>bottom-p/100*(bottom-top);
 host.dataset.gcGeometry=JSON.stringify({w,left,right,max});
 const periods=[0,1200,2400,3600],extras=max>3600?[max]:[];
 host.innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(g.away)} and ${esc(g.home)} win probabilities over game time">${[0,50,100].map(v=>`<line x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-dasharray="${v===50?'4 4':'0'}"/><text x="${left-8}" y="${y(v)+4}" text-anchor="end">${v}%</text>`).join('')}${[...periods,...extras].map(t=>`<line x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${bottom}" stroke="var(--line)" opacity=".5"/><text x="${x(t)}" y="${h-8}" text-anchor="${t===0?'start':t===max?'end':'middle'}">${t===0?'Start':t===1200?'End P1':t===2400?'End P2':t===3600?'End P3':'OT'}</text>`).join('')}${['home','away'].map(s=>`<path d="${points.map((p,i)=>`${i?'L':'M'}${x(p.t).toFixed(2)},${y(p[s]).toFixed(2)}`).join(' ')}" stroke="var(--gc-${s})" stroke-width="2.5" fill="none" stroke-dasharray="${s==='away'?'7 4':'0'}" stroke-linejoin="round"/>`).join('')}${points.filter(p=>p.kind==='goal').map(p=>`<circle cx="${x(p.t)}" cy="${y(p.home)}" r="3.5" fill="var(--gc-home)" stroke="var(--panel)" stroke-width="1.5"/>`).join('')}<line id="poGCCursor" x1="0" x2="0" y1="${top}" y2="${bottom}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/></svg>`;
 host.tabIndex=0;host.setAttribute('role','slider');host.setAttribute('aria-label','Explore game win probabilities. Use left and right arrow keys.');host.setAttribute('aria-valuemin','0');host.setAttribute('aria-valuemax',String(max));poGCPoint=null;poGCRead(points.at(-1),false);
}
function poGCRead(p,cursor=true){
 if(!p||!poGCGame)return;const g=poGCGame,chart=$('poGCChart'),geo=JSON.parse(chart.dataset.gcGeometry||'null');
 $('poGCReadout').innerHTML=`<b>${GAME_CENTER.time(p.t)} elapsed${p.kind==='goal'?' · Goal':''}</b> · ${esc(g.away)} ${poGCPercent(p.away)} / ${esc(g.home)} ${poGCPercent(p.home)}${Number.isInteger(p.home_score)?` · Score ${p.away_score}–${p.home_score}`:''}${poGCData.forecast.status==='shootout'?' · Shootout estimate unavailable':''}`;
 chart.setAttribute('aria-valuenow',String(p.t));chart.setAttribute('aria-valuetext',`${GAME_CENTER.time(p.t)} elapsed, ${g.away} ${poGCPercent(p.away)}, ${g.home} ${poGCPercent(p.home)}`);
 const line=$('poGCCursor');if(line&&geo){const x=geo.left+p.t/geo.max*(geo.right-geo.left);line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('visibility',cursor?'visible':'hidden');}
}
function poGCNear(t){return poGCData?.forecast.points.reduce((a,p)=>!a||Math.abs(p.t-t)<=Math.abs(a.t-t)?p:a,null);}
function poGCPeriods(){const select=$('poGCPeriod'),old=select.value,periods=[...new Set(poGCData.shots.map(s=>s.period))].sort((a,b)=>a-b);if(select.dataset.periods===periods.join(','))return;select.dataset.periods=periods.join(',');select.innerHTML='<option value="">All periods</option>'+periods.map(n=>`<option value="${n}">${n<=3?'P'+n:n===4?'OT':(n-3)+'OT'}</option>`).join('');if(periods.includes(Number(old)))select.value=old;}
function poGCRink(reset=false){
 const list=$('poGCShotList'),scroll=reset?0:list.scrollTop,focused=list.contains(document.activeElement)?document.activeElement.dataset.gcShot:null;
 const all=poGCData?.shots||[];poGCShots=GAME_CENTER.filter(all,{team:$('poGCTeam').value,period:$('poGCPeriod').value,outcome:$('poGCOutcome').value});
 if(!poGCShots.some(s=>s.id===poGCSelected))poGCSelected=poGCShots.at(-1)?.id??null;
 const x=n=>(n+100)*5,y=n=>(42.5-n)*5;
 const circles=[[-69,-22],[-69,22],[69,-22],[69,22]];
 $('poGCRink').innerHTML=`<svg viewBox="0 0 1000 425" aria-label="Shot map: ${esc(poGCGame.away)} attacks left, ${esc(poGCGame.home)} attacks right"><defs><clipPath id="poGCIceClip"><rect x="4" y="4" width="992" height="417" rx="140"/></clipPath></defs><g clip-path="url(#poGCIceClip)"><rect width="1000" height="425" fill="#f3f6fa"/><path d="M${x(-25)} 0V425M${x(25)} 0V425" stroke="#326cbb" stroke-width="5"/><path d="M500 0V425M${x(-89)} 0V425M${x(89)} 0V425" stroke="#d06670" stroke-width="2"/><circle cx="500" cy="212.5" r="75" fill="none" stroke="#326cbb" stroke-width="2"/><circle cx="500" cy="212.5" r="4" fill="#326cbb"/>${circles.map(([a,b])=>`<circle cx="${x(a)}" cy="${y(b)}" r="75" fill="none" stroke="#d06670" stroke-width="2"/><circle cx="${x(a)}" cy="${y(b)}" r="4" fill="#d06670"/>`).join('')}${[-1,1].map(sign=>`<path d="M${x(sign*89)} ${y(6)}A30 30 0 0 ${sign===1?0:1} ${x(sign*89)} ${y(-6)}Z" fill="#cbdfee" stroke="#d06670" stroke-width="1.8"/><rect x="${x(sign===1?89:-93)}" y="${y(3)}" width="20" height="30" rx="4" fill="none" stroke="#b44751" stroke-width="3"/>`).join('')}${poGCShots.filter(s=>s.x!==null).map(s=>{const cx=x(s.x),cy=y(s.y),r=s.xg===null?5:5+Math.sqrt(s.xg)*14,color=s.team===poGCGame.home?'var(--gc-home)':'var(--gc-away)',attr=`data-shot="${s.id}" class="${s.id===poGCSelected?'selected':''}" fill="${color}"`;return s.outcome==='goal'?`<g ${attr}><circle cx="${cx}" cy="${cy}" r="${r+4}"/><text x="${cx}" y="${cy+4}" text-anchor="middle" fill="#fff" stroke="none" font-size="15">★</text></g>`:s.outcome==='missed'?`<path ${attr} d="M${cx} ${cy-r}l${r} ${r}-${r} ${r}-${r}-${r}Z"/>`:s.outcome==='blocked'?`<path ${attr} d="M${cx-5} ${cy-5}l10 10m0-10-10 10" fill="none" style="stroke:${color};stroke-width:3"/>`:`<circle ${attr} cx="${cx}" cy="${cy}" r="${r}"/>`;}).join('')}</g><rect x="4" y="4" width="992" height="417" rx="140" fill="none" stroke="#74828e" stroke-width="6" pointer-events="none"/></svg>`;
 $('poGCShotList').innerHTML=poGCShots.length?[...poGCShots].reverse().map(s=>`<button type="button" data-gc-shot="${s.id}" aria-pressed="${s.id===poGCSelected}"><img src="team-crests/${s.team}.svg" alt="${s.team}"><span><b>${esc(s.player?.name||'Player unavailable')}</b><small>${esc(GAME_CENTER.shotTime(s))} · ${s.outcome==='saved'?'Saved shot':s.outcome==='goal'?'Goal':s.outcome==='blocked'?'Blocked attempt':'Missed shot'}${s.x===null?' · Location unavailable':''}</small></span><strong>${s.xg===null?'—':poGCPercent(s.xg*100)}</strong></button>`).join(''):'<p class="po-gc-empty">'+(!poGCData?'Waiting for play-by-play.':poGCData.status==='scheduled'?'Attempts will appear after puck drop.':'No attempts match these filters.')+'</p>';
 list.scrollTop=scroll;if(focused)list.querySelector(`[data-gc-shot="${focused}"]`)?.focus({preventScroll:true});
 const located=poGCShots.filter(s=>s.x!==null).length;$('poGCShotCount').textContent=`${poGCShots.length} attempts · ${located} located on the rink. Tap a dot or select an event below for details.`;poGCShotDetail();
}
function poGCShotDetail(){
 const s=poGCShots.find(s=>s.id===poGCSelected),host=$('poGCShot');if(!s){host.innerHTML='<p>Select a shot to see who took it, when, and its estimated chance of scoring.</p>';return;}
 const player=s.player,img=Number.isInteger(player?.id)?`<img src="https://assets.nhle.com/mugs/nhl/latest/${player.id}.png" alt="" loading="lazy" data-gc-headshot>`:'';
 host.innerHTML=`${img}<div><b>${esc(player?.name||'Player unavailable')}</b><small>${esc(s.team+' · '+GAME_CENTER.shotTime(s))} · ${esc(s.outcome==='saved'?'Saved shot':s.outcome)}</small><small>${[s.shot_type!=='unknown'?s.shot_type.replaceAll('-',' '):'',Number.isFinite(s.distance)?s.distance+' ft':'',Number.isFinite(s.angle)?Math.round(s.angle)+'°':'',s.strength,s.rebound?'Rebound':''].filter(Boolean).map(esc).join(' · ')}</small>${s.goalie?.name?`<small>Goalie: ${esc(s.goalie.name)}</small>`:''}${s.xg===null?`<small>${esc(s.estimate_note||'Shot estimate unavailable.')}</small>`:''}</div><div class="po-gc-chance"><strong>${s.xg===null?'—':poGCPercent(s.xg*100)}</strong><small>Sweater goal probability</small></div>`;
}
function poGCSelect(id){
 if(!poGCShots.some(s=>s.id===id))return;poGCSelected=id;poGCShotDetail();for(const e of $('poGCRink').querySelectorAll('[data-shot]'))e.classList.toggle('selected',Number(e.dataset.shot)===id);for(const e of $('poGCShotList').querySelectorAll('[data-gc-shot]'))e.setAttribute('aria-pressed',String(Number(e.dataset.gcShot)===id));
}
function poGCQuality(){
 $('poGCQuality').innerHTML=`<p class="po-gc-subtitle">Estimated goals from supported attempts so far. Goalie in net only.</p><div class="po-gc-pregame">${['away','home'].map(s=>`<span>${esc(poGCGame[s])}<b>${poGCData?poGCData[s].expected_goals.toFixed(2):'—'}</b>${poGCData?poGCData[s].modeled_shots+' modeled attempts':''}</span>`).join('')}</div>`;
}
function poGCTab(name){
 for(const b of poGCDialog.querySelectorAll('[data-gc-tab]')){const active=b.dataset.gcTab===name;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;$(b.getAttribute('aria-controls')).hidden=!active;}
 if(name==='live')poGCChart();
}
$('view-playoffs').addEventListener('click',e=>{const trigger=e.target.closest('[data-po-center]');if(trigger){e.preventDefault();poGCOpen(trigger.dataset.poCenter,trigger);}});
poGCDialog.addEventListener('click',e=>{
 const tab=e.target.closest('[data-gc-tab]'),shot=e.target.closest('[data-gc-shot]');if(tab)poGCTab(tab.dataset.gcTab);if(shot)poGCSelect(Number(shot.dataset.gcShot));
 const rink=e.target.closest('#poGCRink');if(rink&&poGCData){const rect=rink.getBoundingClientRect();let best=null,distance=25;for(const s of poGCShots){if(s.x===null)continue;const dx=rect.left+(s.x+100)/200*rect.width-e.clientX,dy=rect.top+(42.5-s.y)/85*rect.height-e.clientY,d=Math.hypot(dx,dy);if(d<distance){best=s;distance=d;}}if(best)poGCSelect(best.id);}
 if(e.target===poGCDialog){const r=poGCDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)poCloseGameCenter();}
});
poGCDialog.addEventListener('change',e=>{if(['poGCTeam','poGCPeriod','poGCOutcome'].includes(e.target.id))poGCRink(true);});
poGCDialog.addEventListener('pointermove',e=>{const chart=e.target.closest('#poGCChart');if(!chart||!poGCData?.forecast.points.length)return;const geo=JSON.parse(chart.dataset.gcGeometry||'null');if(!geo)return;const rect=chart.getBoundingClientRect();poGCPoint=poGCNear(Math.max(0,Math.min(geo.max,(e.clientX-rect.left-geo.left)/(geo.right-geo.left)*geo.max)));if(!poGCFrame)poGCFrame=requestAnimationFrame(()=>{poGCFrame=0;poGCRead(poGCPoint);});});
poGCDialog.addEventListener('pointerout',e=>{const chart=e.target.closest('#poGCChart');if(chart&&!chart.contains(e.relatedTarget)){cancelAnimationFrame(poGCFrame);poGCFrame=0;poGCPoint=null;poGCRead(poGCData?.forecast.points.at(-1),false);}});
poGCDialog.addEventListener('keydown',e=>{
 const tab=e.target.closest('[data-gc-tab]');if(tab&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const other=tab.dataset.gcTab==='live'?'availability':'live',next=e.key==='Home'?'live':e.key==='End'?'availability':other;poGCTab(next);poGCDialog.querySelector(`[data-gc-tab="${next}"]`).focus();}
 if(e.target.id==='poGCChart'&&['ArrowLeft','ArrowRight','Home','End'].includes(e.key)&&poGCData?.forecast.points.length){e.preventDefault();const points=poGCData.forecast.points,index=poGCPoint?points.indexOf(poGCPoint):points.length-1,n=e.key==='Home'?0:e.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,index+(e.key==='ArrowLeft'?-1:1)));poGCPoint=points[n];poGCRead(poGCPoint);}
});
poGCDialog.addEventListener('error',e=>{if(e.target.matches('[data-gc-headshot]'))e.target.hidden=true;},true);
poGCDialog.addEventListener('close',()=>{poGCStop();poGCGame=null;poGCData=null;if(!$('view-playoffs').hidden){const trigger=poGCReturn?.isConnected?poGCReturn:[...document.querySelectorAll(`[data-po-center="${poGCReturnID}"]`)].find(e=>e.getClientRects().length);trigger?.focus();}});
$('poGCClose').onclick=()=>poCloseGameCenter();
document.addEventListener('visibilitychange',()=>{if(!poGCDialog.open)return;if(document.hidden)poGCStop();else poGCLoad();});
let poGCWidth=0;new ResizeObserver(entries=>{const width=entries[0]?.contentRect.width;if(width&&width!==poGCWidth){poGCWidth=width;if(poGCDialog.open&&poGCGame&&!$('poGCLive').hidden)poGCChart();}}).observe(poGCDialog);
