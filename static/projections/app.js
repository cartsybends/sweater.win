const PROJECTION_DATA=/*__PROJECTION_DATA__*/{};
const ppModel=POINT_PROJECTIONS,ppPlayers=new Map((PROJECTION_DATA.players||[]).map(p=>[p.id,p]));
const ppSharing=createProjectionSharing(ppModel);
const ppSaved=store.get('sweater-projections')||{},ppDefault=ppPlayers.has(8478402)?8478402:[...ppPlayers.values()].sort((a,b)=>b.points-a.points)[0]?.id;
let ppState={mode:ppSaved.mode==='manual'||!ppPlayers.size?'manual':'players',ids:Array.isArray(ppSaved.ids)?[...new Set(ppSaved.ids)].filter(id=>ppPlayers.has(id)).slice(0,3):[],selected:ppSaved.selected,
 seasonGames:Number.isInteger(ppSaved.seasonGames)&&ppSaved.seasonGames>=1&&ppSaved.seasonGames<=200?ppSaved.seasonGames:84,rate:Number.isFinite(ppSaved.rate)&&ppSaved.rate>=50&&ppSaved.rate<=150?ppSaved.rate:100,missed:Number.isInteger(ppSaved.missed)&&ppSaved.missed>=0&&ppSaved.missed<=200?ppSaved.missed:0,manual:{goals:'10',assists:'15',gp:'20',...(ppSaved.manual||{})}};
if(!ppState.ids.length&&ppDefault)ppState.ids=[ppDefault];if(!ppState.ids.includes(ppState.selected))ppState.selected=ppState.ids[0];
let ppReady=false,ppSearchResults=[],ppSearchIndex=-1,ppAnnouncementTimer=0,ppShared=null,ppSharedHash='';
const ppFmt=n=>Number.isFinite(n)?Math.round(n).toLocaleString():'—',ppRate=n=>Number.isFinite(n)?n.toFixed(2):'—';
const ppNorm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const ppSave=()=>store.set('sweater-projections',ppState);
const ppPlayer=id=>ppShared&&ppShared.player.id===id?ppShared.player:ppPlayers.get(id);
function ppCurrent(){return ppState.mode==='manual'?{name:'Your stat line',...ppState.manual,teamGP:ppState.manual.gp}:ppPlayer(ppState.selected);}
function ppDropShared(){ppShared=null;ppSharedHash='';ppState.ids=ppState.ids.filter(id=>ppPlayers.has(id));if(!ppState.ids.includes(ppState.selected))ppState.selected=ppState.ids[0];if(location.hash.startsWith('#projections?'))history.replaceState(null,'','#projections');}
function ppOpenShared(){
 if(!location.hash.startsWith('#projections?')){if(ppShared)ppDropShared();return '';}
 if(ppSharedHash===location.hash)return '';
 const shared=ppSharing.read(location.hash);if(!shared)return 'This shared projection could not be opened. Your calculator is still ready to use.';
 ppShared=shared;ppShared.player.clubs=shared.player.team?[shared.player.team]:[];ppSharedHash=location.hash;
 Object.assign(ppState,{mode:shared.mode,seasonGames:shared.seasonGames,rate:shared.rate,missed:shared.missed});
 if(shared.mode==='players'){ppState.ids=[shared.player.id];ppState.selected=shared.player.id;}else{ppState.manual={goals:String(shared.player.goals),assists:String(shared.player.assists),gp:String(shared.player.gp)};ppReady=false;}
 return '';
}
function ppResult(p){return p?ppModel.calculate({...p,seasonGames:ppState.seasonGames,missed:ppState.missed,rate:ppState.rate}):{valid:false,reason:'Choose a player to get started.'};}
function ppCloseSearch(){$('ppSearchList').hidden=true;$('ppSearch').setAttribute('aria-expanded','false');$('ppSearch').removeAttribute('aria-activedescendant');ppSearchIndex=-1;}
function ppSearch(){
 const q=ppNorm($('ppSearch').value);ppSearchResults=[...ppPlayers.values()].filter(p=>!q||ppNorm(p.name+' '+(p.team||'')+' '+(p.team?teamFullName(p.team):p.clubs.join(' '))).includes(q)).sort((a,b)=>b.points-a.points||a.name.localeCompare(b.name)).slice(0,9);ppSearchIndex=-1;$('ppSearch').removeAttribute('aria-activedescendant');
 $('ppSearchList').innerHTML=ppSearchResults.map((p,i)=>`<li id="ppOption${i}" role="option" aria-selected="false" data-pp-pick="${p.id}"><span>${esc(p.name)}</span><small>${esc(p.team||'NHL')} · ${p.points} PTS</small></li>`).join('');
 $('ppSearchList').hidden=!ppSearchResults.length;$('ppSearch').setAttribute('aria-expanded',String(!!ppSearchResults.length));$('ppSearchStatus').textContent=ppSearchResults.length?'':'No matching skaters. Try a surname or team.';
}
function ppPick(id){
 if(!ppPlayers.has(id))return;
 if(ppShared)ppDropShared();
 if(!ppState.ids.includes(id)){if(ppState.ids.length>=3){$('ppSearchStatus').textContent='You’re comparing three players. Remove one to add someone else.';ppCloseSearch();return;}ppState.ids.push(id);}
 ppState.selected=id;ppCloseSearch();$('ppSearch').value='';$('ppSearchStatus').textContent='';ppRender();ppSave();
}
function ppChart(p,r){
 if(!r.valid)return '<p class="pp-small">A valid stat line will draw your pace here.</p>';
 const maxX=Math.max(r.seasonGames,r.gp,r.finish.gp),maxY=Math.max(10,Math.ceil(Math.max(r.pace.points,r.finish.points,r.points)/25)*25),x=n=>42+n/maxX*442,y=n=>240-n/maxY*202;
 const ax=x(r.gp),ay=y(r.points),bx=x(r.seasonGames),by=y(r.pace.points),fx=x(r.finish.gp),fy=y(r.finish.points);
 return `<svg viewBox="0 0 520 285" role="img" aria-labelledby="ppChartTitle ppChartDesc"><title id="ppChartTitle">${esc(p.name)} point projection</title><desc id="ppChartDesc">${r.points} points in ${r.gp} games. ${ppFmt(r.pace.points)} points over ${r.seasonGames} games at the current rate. Projected finish: ${ppFmt(r.finish.points)} points in ${r.finish.gp} player appearances.</desc>${[0,.25,.5,.75,1].map(t=>`<line x1="42" x2="484" y1="${y(maxY*t)}" y2="${y(maxY*t)}" stroke="var(--line)"/><text x="32" y="${y(maxY*t)+4}" text-anchor="end" fill="var(--muted)" font-size="10">${Math.round(maxY*t)}</text>`).join('')}<line x1="42" y1="240" x2="${bx}" y2="${by}" stroke="var(--muted)" stroke-width="2" opacity=".45"/><line x1="${ax}" y1="${ay}" x2="${fx}" y2="${fy}" stroke="var(--link)" stroke-width="3" stroke-dasharray="6 5"/><line x1="${ax}" x2="${ax}" y1="${ay}" y2="240" stroke="var(--muted)" stroke-dasharray="2 5" opacity=".4"/><circle cx="${bx}" cy="${by}" r="4" fill="var(--link)"/><circle cx="${fx}" cy="${fy}" r="5" fill="var(--link)"/><circle cx="${ax}" cy="${ay}" r="5" fill="var(--panel)" stroke="var(--fg)" stroke-width="2"/>${[0,.25,.5,.75,1].map(t=>`<text x="${x(maxX*t)}" y="261" text-anchor="middle" fill="var(--muted)" font-size="10">${Math.round(maxX*t)}</text>`).join('')}<text x="263" y="281" text-anchor="middle" fill="var(--muted)" font-size="9">GAMES PLAYED</text><text x="${Math.min(475,Math.max(62,fx))}" y="${Math.max(17,fy-13)}" text-anchor="middle" fill="var(--link)" font-size="12" font-weight="700">${ppFmt(r.finish.points)}</text></svg>`;
}
function ppRender(){
 ppState.missed=Math.min(ppState.missed,Number.isInteger(ppState.seasonGames)?ppState.seasonGames:84);$('ppMissed').max=Number.isInteger(ppState.seasonGames)?ppState.seasonGames:84;
 const manual=ppState.mode==='manual',p=ppCurrent(),r=ppResult(p),valid=r.valid;
 $('ppPlayerPanel').hidden=manual;$('ppManualPanel').hidden=!manual;$('ppComparePanel').hidden=manual;$('ppPlayersTab').setAttribute('aria-selected',String(!manual));$('ppManualTab').setAttribute('aria-selected',String(manual));$('ppPlayersTab').tabIndex=manual?-1:0;$('ppManualTab').tabIndex=manual?0:-1;
 const start=ppShared?.start||PROJECTION_DATA.start||2026;
 $('ppSeason').textContent=`${start}–${String(start+1).slice(-2)} · ${ppState.seasonGames||'—'} GAMES`;
 $('ppLength').value=Number.isFinite(ppState.seasonGames)?ppState.seasonGames:'';$('ppRate').value=ppState.rate;$('ppRateValue').textContent=ppState.rate+'%';$('ppMissed').value=ppState.missed;$('ppMissedValue').textContent=ppState.missed;
 $('view-projections').querySelectorAll('[data-pp-length]').forEach(b=>b.setAttribute('aria-pressed',String(+b.dataset.ppLength===ppState.seasonGames)));
 $('ppPicks').innerHTML=ppState.ids.map(id=>{const p=ppPlayer(id);return `<span class="pp-pick${id===ppState.selected?' on':''}"><button type="button" data-pp-focus="${id}" aria-pressed="${id===ppState.selected}">${esc(p.name)}</button><button type="button" data-pp-remove="${id}" aria-label="Remove ${esc(p.name)} from comparison">×</button></span>`;}).join('');
 if(!manual&&p){
  const image=String(p.headshot||'').startsWith('https://assets.nhle.com/')?p.headshot:`https://assets.nhle.com/mugs/nhl/latest/${p.id}.png`,initials=p.name.split(' ').map(s=>s[0]).slice(0,2).join('');
  const card=$('ppPlayerCard'),identity=JSON.stringify([p.id,image]);
  if(card.dataset.player!==identity){
   card.dataset.player=identity;
   card.innerHTML=`<div class="pp-player"><span class="pp-headshot"><span aria-hidden="true">${esc(initials)}</span><img src="${esc(image)}" alt="" onload="this.previousElementSibling.hidden=true" onerror="this.remove()"></span><div><h3></h3><p></p></div></div><div class="pp-record">${['GP','GOALS','ASSISTS','POINTS'].map(label=>`<div><span>${label}</span><b></b></div>`).join('')}</div>`;
  }
  const update=(node,value)=>{if(node.textContent!==String(value))node.textContent=value;};
  update(card.querySelector('.pp-headshot>span'),initials);update(card.querySelector('h3'),p.name);update(card.querySelector('.pp-player p'),`${p.team?teamFullName(p.team):'Multiple / unconfirmed current club'} · ${p.pos==='D'?'Defense':'Forward'}`);
  const stats=card.querySelectorAll('.pp-record b');[p.gp,p.goals,p.assists,p.points].forEach((value,i)=>update(stats[i],value));
  $('ppSource').textContent=`${ppShared?'Shared stat line':'NHL regular season'} · ${ppSnapshotChecked()?'checked':'snapshot'} ${ppCheckedLabel(ppSnapshotChecked(),ppShared?.asof||PROJECTION_DATA.asof||'unavailable')}.`+(p.clubs.length>1?' Season totals combine all clubs.':'');
 }
 if(!manual&&!p){delete $('ppPlayerCard').dataset.player;$('ppPlayerCard').innerHTML='<p class="pp-small">Find a skater above to start a projection.</p>';$('ppSource').textContent='';}
 const value=field=>valid?ppFmt(field):'—';$('ppResultName').textContent=p?.name||'Choose a player';$('ppPaceLabel').textContent=`${ppState.seasonGames||'—'}-game projection`;$('ppPace').textContent=value(r.finish?.points);$('ppPace').classList.toggle('pp-long',$('ppPace').textContent.length>5);$('ppPPG').textContent=valid?ppRate(r.ppg):'—';$('ppPaceGoals').textContent=value(r.finish?.goals);$('ppPaceAssists').textContent=value(r.finish?.assists);
 $('ppError').hidden=valid;$('ppError').textContent=valid?'':r.reason;
 $('ppRemaining').textContent=valid?`${r.clubRemaining} games remain ${!manual&&p.team?'for '+p.team:'in the selected schedule'}. Projection assumes ${r.remaining} more appearances.`:'';
 $('ppChart').innerHTML=ppChart(p||{name:'Your stat line'},r);$('ppCompareLength').textContent=`${ppState.seasonGames||'—'}-game projection`;
 $('ppCompareRows').innerHTML=ppState.ids.map(id=>{const q=ppPlayer(id),n=ppResult(q);return `<tr class="${id===ppState.selected?'on':''}"><td><button type="button" data-pp-focus="${id}">${esc(q.name)}<small>${esc(q.team||'NHL')} · ${q.pos}</small></button></td><td>${q.gp}</td><td>${q.points}</td><td>${n.valid?ppRate(n.ppg):'—'}</td><td>${n.valid?ppFmt(n.finish.points):'—'}</td></tr>`;}).join('');
 ppRenderShare(p,r,manual);
 ppFeedStatus();ppStartFeed();
 clearTimeout(ppAnnouncementTimer);ppAnnouncementTimer=setTimeout(()=>{$('ppAnnouncement').textContent=valid?`${ppState.seasonGames}-game projection: ${ppFmt(r.finish.points)} points. ${ppAdjustmentText(ppState)}.`:r.reason;},200);
}
function closeProjections(){if(!$('view-projections'))return;$('view-projections').hidden=true;document.body.classList.remove('projections-mode');$('projectionsNav').removeAttribute('aria-current');ppCloseSearch();ppCloseShare();ppStopSliderDrags();ppStopFeed();if($('ppImageDialog').open)$('ppImageDialog').close();clearTimeout(ppAnnouncementTimer);}
function openProjections(push=true){
 if(typeof closePlayoffs==='function')closePlayoffs();
 if(push)rememberHubScroll();globalThis.SweaterAnalytics?.leave();leaveGame(game);teamMiniCleanup();closeParty();onHub=false;document.body.classList.remove('hubmode');document.body.classList.add('projections-mode');$('view-hub').hidden=true;$('view-teams').hidden=true;$('view-party').hidden=true;
 new Set(GAME_IDS.map(id=>G[id].view)).forEach(id=>{$(id).hidden=true;});$('view-projections').hidden=false;$('gameBar').hidden=false;$('archBar').hidden=true;$('gIcon').innerHTML=uiIcon('chart');$('gTitle').textContent='Point Projections';$('modeLabel').textContent='NHL players & your own stat lines';$('gameBar').dataset.game='projections';$('projectionsNav').setAttribute('aria-current','page');
 const sharedError=ppOpenShared();
 if(!ppReady){for(const [key,id] of [['goals','ppGoals'],['assists','ppAssists'],['gp','ppGP']])$(id).value=ppState.manual[key];ppReady=true;}
 const available=ppPlayers.size||ppShared?.mode==='players';$('ppPlayersTab').disabled=!available;$('ppAvailability').hidden=!!available;if(!available){ppState.mode='manual';$('ppSearchStatus').textContent='Player data is unavailable. The calculator is ready to use.';}
 if(push&&!/^#projections(?:\?|$)/.test(location.hash))history.pushState(null,'','#projections');document.title='Point Projections · Sweater';ppRender();if(sharedError)$('ppShareStatus').textContent=sharedError;window.scrollTo({top:0});
}
$('projectionsNav').onclick=e=>{e.preventDefault();openProjections();};
$('ppSearch').oninput=ppSearch;$('ppSearch').onfocus=ppSearch;
$('ppSearch').onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();ppCloseSearch();return;}if(e.key==='Tab'){ppCloseSearch();return;}if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();if($('ppSearchList').hidden)ppSearch();if(!ppSearchResults.length)return;ppSearchIndex=ppSearchIndex<0?(e.key==='ArrowDown'?0:ppSearchResults.length-1):(ppSearchIndex+(e.key==='ArrowDown'?1:-1)+ppSearchResults.length)%ppSearchResults.length;$('ppSearchList').querySelectorAll('[role=option]').forEach((o,i)=>o.setAttribute('aria-selected',String(i===ppSearchIndex)));$('ppSearch').setAttribute('aria-activedescendant','ppOption'+ppSearchIndex);$('ppOption'+ppSearchIndex)?.scrollIntoView({block:'nearest'});}else if(e.key==='Enter'&&!$('ppSearchList').hidden&&ppSearchResults.length){e.preventDefault();ppPick(ppSearchResults[Math.max(0,ppSearchIndex)].id);}};
$('ppSearchList').onmousedown=e=>e.preventDefault();document.addEventListener('click',e=>{if(!e.target.closest('.pp-search-wrap'))ppCloseSearch();});
$('view-projections').addEventListener('click',e=>{const b=e.target.closest('[data-pp-pick],button');if(!b)return;
 if(b.dataset.ppPick)ppPick(+b.dataset.ppPick);else if(b.dataset.ppFocus){ppState.selected=+b.dataset.ppFocus;ppRender();ppSave();}
 else if(b.dataset.ppRemove){ppState.ids=ppState.ids.filter(id=>id!==+b.dataset.ppRemove);if(!ppState.ids.includes(ppState.selected))ppState.selected=ppState.ids[0];ppRender();ppSave();}
 else if(b.dataset.ppMode){ppState.mode=b.dataset.ppMode;ppCloseSearch();ppRender();ppSave();}
 else if(b.dataset.ppLength){ppState.seasonGames=+b.dataset.ppLength;ppRender();ppSave();}
});
for(const [key,id] of [['goals','ppGoals'],['assists','ppAssists'],['gp','ppGP']])$(id).oninput=()=>{ppState.manual[key]=$(id).value;ppRender();ppSave();};
$('ppLength').oninput=()=>{ppState.seasonGames=ppModel.number($('ppLength').value);ppRender();ppSave();};
$('ppRate').oninput=()=>{ppState.rate=+$('ppRate').value;ppRender();ppSave();};$('ppMissed').oninput=()=>{ppState.missed=+$('ppMissed').value;ppRender();ppSave();};
$('ppReset').onclick=()=>{ppState.rate=100;ppState.missed=0;ppRender();ppSave();};$('ppClear').onclick=()=>{ppState.manual={goals:'0',assists:'0',gp:'0'};['ppGoals','ppAssists','ppGP'].forEach(id=>$(id).value=0);ppRender();ppSave();};
$('view-projections').querySelector('[role=tablist]').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const manual=e.key==='End'||e.key!=='Home'&&ppState.mode==='players';const target=$(manual?'ppManualTab':'ppPlayersTab');if(!target.disabled){target.click();target.focus();}};
