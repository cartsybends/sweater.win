const PLAYOFF_DATA=/*__PLAYOFF_DATA__*/{};
const poModel=PLAYOFF_PICTURE,poStages=poModel.stages,poSaved=store.get('sweater-playoffs')||{};
const poTabs=['league','games','circle','team','history'];
let poData=poModel.validate(PLAYOFF_DATA),poTeam=poModel.clubs.has(poSaved.team)?poSaved.team:'',poTab='league',poFormat='american',poSort='playoffs',poDescending=true,poShared=null,poSharedHash='',poTimer=null,poController=null,poBusy=false,poAttempt=0,poRequest=0,poError=false,poImageURL='';
const poDate=value=>new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
const poTeamRecord=team=>poData?.teams.find(t=>t.abbr===team);
const poCurrent=()=>poShared?{abbr:poShared.team,name:poShared.name,gp:poShared.gp,points:poShared.points,projected_points:poShared.projected,odds:poShared.odds,shared:true}:poTeamRecord(poTeam);
const poColors=['var(--link)','#d78a38','#8b87de'];
const poDelta=n=>n===null||n===undefined?'—':Math.abs(n)<.05?'0.0':(n>0?'↑ ':'↓ ')+Math.abs(n).toFixed(1);
function poSnapshot(){const t=poCurrent();return t?poModel.snapshot({v:1,team:t.abbr,name:t.name,start:poShared?.start||poData.start,at:poShared?.at||poData.updated_at,gp:t.gp,points:t.points,projected:t.projected_points,n:poShared?.n||poData.simulations,odds:t.odds}):null;}
function poCloseShare(focus=false){$('poShareMenu').hidden=true;$('poShareToggle').setAttribute('aria-expanded','false');if(focus)$('poShareToggle').focus();}
function poDropShared(){poShared=null;poSharedHash='';if(location.hash.startsWith('#playoffs?'))history.replaceState(null,'','#playoffs');}
function poPick(team){if(!poModel.clubs.has(team))return;poDropShared();poTeam=team;poTab='team';store.set('sweater-playoffs',{team});poRender();}
function poOpenShared(){
 if(!location.hash.startsWith('#playoffs?')){poShared=null;poSharedHash='';return;}
 if(poSharedHash===location.hash){poTab='team';return;}
 const snapshot=poModel.read(location.hash);if(snapshot){poShared=snapshot;poTeam=snapshot.team;poTab='team';poSharedHash=location.hash;}else{poShared=null;poSharedHash='';toast('This shared forecast could not be opened. Showing the league board.');}
}
function poDistribution(t){
 if(!t?.distribution?.length)return '<div class="po-empty">Use the latest forecast to explore the final-points distribution.</div>';
 const lo=Math.max(t.points,t.distribution[0][0]-1),hi=Math.min(poData.season_games*2,t.distribution.at(-1)[0]+1),max=Math.max(...t.distribution.map(r=>r[1])),width=460,height=240,left=30,right=445,bottom=205,top=25,x=n=>left+(n-lo)/Math.max(1,hi-lo)*(right-left),bar=Math.max(2,(right-left)/(hi-lo+1)*.82);
 const ticks=[lo,Math.round((lo+hi)/2),hi];
 return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(t.name)} simulated final regular-season points distribution"><line x1="${left}" x2="${right}" y1="${bottom}" y2="${bottom}" stroke="var(--line)"/>${t.distribution.map(([p,prob])=>{const h=Math.max(1,prob/max*(bottom-top));return `<rect x="${x(p)-bar/2}" y="${bottom-h}" width="${bar}" height="${h}" rx="1.5" fill="var(--link)" opacity="${p>=t.points_range[0]&&p<=t.points_range[1]?'.8':'.3'}" tabindex="0" data-po-point="${p}" data-po-prob="${prob}" aria-label="${p} final points: ${prob.toFixed(2)} percent of simulations"><title>${p} points · ${prob.toFixed(2)}%</title></rect>`;}).join('')}${ticks.map(p=>`<text x="${x(p)}" y="226" text-anchor="middle" font-size="10" fill="var(--muted)">${p}</text>`).join('')}<text x="${left}" y="13" font-size="9" fill="var(--muted)">SIMULATED FINISHES</text></svg>`;
}
function poRenderHistory(){
 const available=poData?.teams||[],options='<option value="">No comparison</option>'+[...available].sort((a,b)=>a.name.localeCompare(b.name)).map(t=>`<option value="${t.abbr}">${esc(t.name)}</option>`).join('');
 for(const id of ['poHistoryTeam','poCompare1','poCompare2']){const old=$(id).value;if($(id).dataset.season!==String(poData?.season)){$(id).innerHTML=options;$(id).dataset.season=poData?.season||'';$(id).value=old;}}
 if(!$('poHistoryTeam').value&&available.length)$('poHistoryTeam').value=poTeam||[...available].sort((a,b)=>b.odds.cup-a.odds.cup)[0].abbr;
 const teams=[...new Set([$('poHistoryTeam').value,$('poCompare1').value,$('poCompare2').value].filter(t=>poTeamRecord(t)))],metric=$('poHistoryMetric').value,index=metric==='cup'?1:0,points=poData?.history||[];
 $('poHistoryLegend').innerHTML=teams.map((team,i)=>`<span><i style="background:${poColors[i]}"></i>${esc(poTeamRecord(team).name)}</span>`).join('');
 if(poShared){$('poHistoryChart').innerHTML='<div class="po-empty"><b>A moment, saved.</b>Use the latest forecast to explore live history.</div>';$('poHistoryReadout').textContent='Shared forecasts preserve their original probabilities.';return;}
 if(points.length<2){$('poHistoryChart').innerHTML='<div class="po-empty"><b>The story starts here.</b>The first forecast is recorded. This chart will grow as completed games change the picture.</div>';$('poHistoryReadout').textContent=points.length?'First forecast · '+poDate(points[0].at):'History is temporarily unavailable.';return;}
 const width=960,height=310,left=45,right=935,top=20,bottom=266,min=Date.parse(points[0].at),max=Date.parse(points.at(-1).at),x=at=>left+(Date.parse(at)-min)/Math.max(1,max-min)*(right-left),y=p=>bottom-p/100*(bottom-top);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${metric==='cup'?'Stanley Cup':'Playoff'} probability history">${[0,50,100].map(v=>`<line x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" opacity=".55"/><text x="${left-9}" y="${y(v)+4}" text-anchor="end" font-size="10" fill="var(--muted)">${v}%</text>`).join('')}`;
 teams.forEach((team,i)=>{svg+=`<path d="${points.map((p,j)=>`${j?'L':'M'}${x(p.at).toFixed(2)},${y(p.teams[team][index]).toFixed(2)}`).join(' ')}" fill="none" stroke="${poColors[i]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;
  // The full path retains every forecast; focusable markers are sampled for usable keyboard navigation.
  const step=Math.max(1,Math.ceil(points.length/40));points.forEach((p,j)=>{if(j%step&&j!==points.length-1)return;svg+=`<circle cx="${x(p.at)}" cy="${y(p.teams[team][index])}" r="3" fill="${poColors[i]}" tabindex="0" data-po-history="${j}" data-po-hteam="${team}" aria-label="${esc(poTeamRecord(team).name)}, ${esc(poDate(p.at))}: ${poModel.percent(p.teams[team][index])}"><title>${esc(poDate(p.at))} · ${poModel.percent(p.teams[team][index])}</title></circle>`;});
 });
 svg+=`<text x="${left}" y="296" font-size="10" fill="var(--muted)">${esc(new Date(points[0].at).toLocaleDateString(undefined,{month:'short',day:'numeric'}))}</text><text x="${right}" y="296" text-anchor="end" font-size="10" fill="var(--muted)">${esc(new Date(points.at(-1).at).toLocaleDateString(undefined,{month:'short',day:'numeric'}))}</text></svg>`;
 $('poHistoryChart').innerHTML=svg;$('poHistoryReadout').textContent='Hover, tap, or focus a point to see that forecast. All values are percentages.';
}
function poFeedStatus(){
 $('poRefresh').disabled=poBusy;
 if(!poData){$('poChecked').textContent='Forecast temporarily unavailable';$('poLatest').textContent='Please check again shortly.';return;}
 const stale=Date.now()-Date.parse(poData.checked_at)>30*60*1000,age=Date.now()-Date.parse(poData.checked_at)>6*60*60*1000;
 $('poChecked').textContent=(poBusy?'Checking for a newer forecast…':poError?'Latest check unavailable · keeping the last verified forecast':stale?'Latest published check':'NHL results checked')+' · '+poDate(poData.checked_at);
 const g=poData.latest_game;$('poLatest').textContent=`${poData.completed_games} of ${poData.total_games} regular-season games included`+(g?` · Latest scheduled final: ${g.away} ${g.ag}–${g.hg} ${g.home} (${g.date})`:'');
 $('poNotice').hidden=!age;$('poNotice').textContent=age?'This forecast is more than six hours old. Probabilities below reflect the results included at the displayed time.':'';
}
function poRender(){
 const t=poCurrent(),available=!!t,options=[...(poData?.teams||[])].sort((a,b)=>a.name.localeCompare(b.name));
 if($('poTeam').options.length<2&&options.length)$('poTeam').innerHTML='<option value="">Choose a team…</option>'+options.map(t=>`<option value="${t.abbr}">${esc(t.name)}</option>`).join('');
 $('poTeam').value=poTeam;$('poShareToggle').disabled=!available;$('poHero').hidden=!available;$('poNoTeam').hidden=available;$('poTeamCharts').hidden=!available;$('poOpponentPanel').hidden=!available;$('poTeamRaw').hidden=!available||!!poShared;
 $('poSeason').textContent=`${poShared?.start||poData?.start||'—'}–${String((poShared?.start||poData?.start||0)+1).slice(-2)} · ${poData?.season_games||84} GAMES`;
 $('poSharedNotice').hidden=!poShared;$('poSharedNotice').querySelector('span').textContent=poShared?'Saved team card · '+poDate(poShared.at)+'. The league board uses the latest forecast.':'';
 $('poOddsNote').hidden=false;$('view-playoffs').querySelectorAll('[data-po-format]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.poFormat===poFormat)));
 if(t){
  $('poName').textContent=t.name;$('poRecord').textContent=`${t.gp} GP · ${t.points} PTS · ${Math.round(t.projected_points)} projected final points`;
  const src=`team-logos/${t.abbr}.svg`;if($('poCrest').getAttribute('src')!==src)$('poCrest').src=src;
  $('poChance').textContent=poModel.fair(t.odds.playoffs,poFormat);$('poChance').classList.toggle('po-long',$('poChance').textContent.length>7);
  $('poChancePercent').textContent=poFormat==='percent'?'':poModel.percent(t.odds.playoffs)+' model probability';
  $('poChange').textContent=t.shared?'Saved forecast':t.change===null||t.change===undefined?'First forecast recorded':`${poDelta(t.change)} percentage points since the previous forecast`;$('poChange').classList.toggle('positive',t.change>0);
  $('poHeroStages').innerHTML=poStages.slice(1).map(([key,label])=>`<div><span>${label}</span><b>${poModel.fair(t.odds[key],poFormat)}</b>${poFormat==='percent'?'':`<small class="po-muted">${poModel.percent(t.odds[key])}</small>`}</div>`).join('');
  $('poCardTime').textContent=`SWEATER MODEL ESTIMATE · ${poDate(poShared?.at||poData.updated_at)}`;
  $('poLadder').innerHTML=poStages.map(([key,label])=>`<div class="po-ladder-row"><div><span>${label}</span><b>${poModel.fair(t.odds[key],poFormat)}</b></div><div class="po-ladder-track"><i style="width:${t.odds[key]}%"></i></div></div>`).join('');
  $('poProjected').innerHTML=`${Math.round(t.projected_points)} <small>PTS</small>`;$('poRange').textContent=t.points_range?`Middle 80% of simulated finishes: ${t.points_range[0]}–${t.points_range[1]} points.`:'Saved projected final points.';
  $('poDistribution').innerHTML=poDistribution(t);
  $('poOpponents').innerHTML=t.opponents?.length&&t.odds.playoffs>0?t.opponents.slice(0,4).map(o=>`<div class="po-opponent"><img src="team-logos/${o.team}.svg" alt=""><div>${esc(poTeamRecord(o.team)?.name||o.team)}<b>${poModel.percent(Math.min(100,o.chance/t.odds.playoffs*100))}</b></div></div>`).join(''):'<p class="po-panel-note">First-round opponent forecasts are available in the latest forecast when qualification occurs in the simulations.</p>';
 }
 poRenderBoard();poRenderGames();poRenderCircle();if(t&&!t.shared)poRenderTeamStats(t);
 $('poChangeNote').textContent=poData?.previous_at?`Playoff probability change since ${poDate(poData.previous_at)}. All stage probabilities are measured from today.`:'Changes will appear after the next result changes the forecast. All stage probabilities are measured from today.';
 $('poMethodCount').textContent=`Sweater goals model v1 · ${(poData?.simulations||50000).toLocaleString()} simulations per forecast. Historical validation and the model assumptions are published with the source.`;
 $('poValidationText').textContent=poData?.validation?.summary||'This first version uses a goals-based model. Historical validation is documented alongside its source code.';
 for(const tab of poTabs){const cap=tab[0].toUpperCase()+tab.slice(1),on=tab===poTab;$('poTab'+cap).setAttribute('aria-selected',String(on));$('poTab'+cap).tabIndex=on?0:-1;$('poPanel'+cap).hidden=!on;}
 poRenderHistory();poFeedStatus();poCloseShare();
}
async function poRefresh(force=false){
 if($('view-playoffs').hidden||document.hidden||poBusy||!force&&Date.now()-poAttempt<poModel.interval)return;
 poAttempt=Date.now();poBusy=true;poFeedStatus();const request=++poRequest,controller=new AbortController();poController=controller;const timeout=setTimeout(()=>controller.abort(),15000);
 try{const r=await fetch(poModel.url+'?v='+Math.floor(Date.now()/(force?1000:poModel.interval)),{cache:'no-store',credentials:'omit',signal:controller.signal});if(!r.ok)throw new Error();const next=poModel.validate(await r.json());if(request!==poRequest)return;if(!next)throw new Error();if(!poData||Date.parse(next.checked_at)>Date.parse(poData.checked_at)){const changed=!poData||next.source_sha256!==poData.source_sha256||next.analytics_version!==poData.analytics_version||next.games_today!==poData.games_today||poGamesKey(next)!==poGamesKey(poData);poData=next;if(changed)poRender();}poError=false;}catch{if(request===poRequest)poError=true;}finally{clearTimeout(timeout);if(request===poRequest){poController=null;poBusy=false;poFeedStatus();}}
}
function closePlayoffs(){if(!$('view-playoffs'))return;$('view-playoffs').hidden=true;document.body.classList.remove('playoffs-mode');$('playoffsNav').removeAttribute('aria-current');clearInterval(poTimer);poTimer=null;poRequest++;poController?.abort();poController=null;poBusy=false;poAttempt=0;poCloseShare();if($('poImageDialog').open)$('poImageDialog').close();}
function openPlayoffs(push=true){
 if(push)rememberHubScroll();closeProjections();globalThis.SweaterAnalytics?.leave();leaveGame(game);teamMiniCleanup();closeParty();onHub=false;document.body.classList.remove('hubmode');document.body.classList.add('playoffs-mode');$('view-hub').hidden=true;$('view-teams').hidden=true;$('view-party').hidden=true;new Set(GAME_IDS.map(id=>G[id].view)).forEach(id=>{$(id).hidden=true;});
 $('view-playoffs').hidden=false;$('gameBar').hidden=false;$('archBar').hidden=true;$('gIcon').innerHTML=uiIcon('chart');$('gTitle').textContent='Playoff Picture';$('modeLabel').textContent='League odds, games & results';$('gameBar').dataset.game='playoffs';$('playoffsNav').setAttribute('aria-current','page');
 if(push&&!/^#playoffs(?:\?|$)/.test(location.hash))history.pushState(null,'','#playoffs');poTab='league';poOpenShared();document.title='Playoff Picture · Sweater';poRender();if(!poTimer)poTimer=setInterval(()=>poRefresh(),poModel.interval);poRefresh();window.scrollTo({top:0});
}
async function poDrawImage(snapshot){
 const palette=getComputedStyle($('poHero')),fg=palette.color,bg=palette.backgroundColor,accent=getComputedStyle($('poCardKicker')).color,muted=getComputedStyle($('poRecord')).color;
 const [crest,mark]=await Promise.all([ppLoadCrest(snapshot.team),ppLoadImage('data:image/svg+xml,'+encodeURIComponent(PP_SWEATER_MARK.replace('#8055ff',accent)))]);
 const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=860;const ctx=canvas.getContext('2d');ppRoundRect(ctx,0,0,1200,860,34,bg);ctx.save();ctx.clip();if(crest){ctx.globalAlpha=.045;ppDrawContain(ctx,crest,90,30,1020,760,true);ctx.globalAlpha=1;}ctx.restore();
 const text=(value,x,y,size=24,color=fg,weight=500,align='left')=>{ctx.font=`${weight} ${size}px Arial, sans-serif`;ctx.fillStyle=color;ctx.textAlign=align;ctx.fillText(String(value),x,y);};
 text(`${snapshot.start}–${String(snapshot.start+1).slice(-2)} · PLAYOFF PICTURE`,60,77,20,accent,650);
 let size=52;while(size>28){ctx.font=`750 ${size}px Arial`;if(ctx.measureText(snapshot.name).width<=1060)break;size--;}
 text(snapshot.name,60,151,size,fg,750);text(`${snapshot.gp} GP · ${snapshot.points} PTS · ${Math.round(snapshot.projected)} projected final points`,62,197,24,muted);
 text('MAKE THE PLAYOFFS',63,281,22,muted,550);text(poModel.percent(snapshot.odds.playoffs),53,446,150,fg,800);
 poStages.slice(1).forEach(([key,label],i)=>{const x=62+i*284;text(label,x,535,20,muted);text(poModel.percent(snapshot.odds[key]),x,596,43,accent,700);});
 text('CHANCES OF REACHING EACH STAGE FROM THIS FORECAST',62,663,18,muted);
 if(mark)ctx.drawImage(mark,60,753,43,43);text('sweater.win',116,787,30,fg,750);text('SWEATER MODEL ESTIMATE',1138,760,16,muted,500,'right');text(poDate(snapshot.at),1138,790,17,muted,500,'right');
 return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Image unavailable')),'image/png'));
}
function poPreview(blob){if(poImageURL)URL.revokeObjectURL(poImageURL);poImageURL=URL.createObjectURL(blob);$('poImagePreview').src=poImageURL;$('poImageSave').href=poImageURL;if(!$('poImageDialog').open)$('poImageDialog').showModal();}
async function poShare(action){
 const snapshot=poSnapshot();if(!snapshot)return;poCloseShare();$('poShareStatus').textContent='Preparing…';
 try{
  if(action==='link'){const url=new URL(SITE||location.href);url.search='';url.hash='playoffs?s='+encodeURIComponent(JSON.stringify(snapshot));try{await navigator.clipboard.writeText(url.href);toast('Playoff Picture link copied');$('poShareStatus').textContent='';}catch{$('poShareStatus').textContent='Copy this forecast link: '+url.href;}return;}
  const promise=poDrawImage(snapshot);
  if(action==='copy'&&navigator.clipboard?.write&&typeof ClipboardItem!=='undefined'){try{await navigator.clipboard.write([new ClipboardItem({'image/png':promise})]);$('poShareStatus').textContent='';toast('Playoff Picture image copied');return;}catch{}}
  const blob=await promise;if(action==='save'){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`sweater-playoff-picture-${snapshot.team.toLowerCase()}.png`;link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('Playoff Picture image ready to save');}else poPreview(blob);$('poShareStatus').textContent='';
 }catch{$('poShareStatus').textContent='The image could not be prepared. Please try again.';}
}
$('poBrand').innerHTML=PP_SWEATER_MARK+'<span>sweater.win</span>';
$('playoffsNav').onclick=e=>{e.preventDefault();openPlayoffs();};$('poTeam').onchange=e=>{if(e.target.value)poPick(e.target.value);else{poDropShared();poTeam='';poRender();}};$('poRefresh').onclick=()=>poRefresh(true);$('poUseLatest').onclick=()=>{poDropShared();poRender();poRefresh(true);};
$('poConference').onchange=poRender;for(const id of ['poHistoryTeam','poCompare1','poCompare2','poHistoryMetric'])$(id).onchange=poRenderHistory;
$('view-playoffs').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.poTeam)poPick(b.dataset.poTeam);else if(b.dataset.poTab){poTab=b.dataset.poTab;poRender();}else if(b.dataset.poFormat){poFormat=b.dataset.poFormat;poRender();}else if(b.dataset.poSort){if(poSort===b.dataset.poSort)poDescending=!poDescending;else{poSort=b.dataset.poSort;poDescending=true;}poRender();}else if(b.dataset.poShare)poShare(b.dataset.poShare);});
$('poShareToggle').onclick=e=>{const open=$('poShareMenu').hidden;$('poShareMenu').hidden=!open;$('poShareToggle').setAttribute('aria-expanded',String(open));if(open&&e.detail===0)$('poShareMenu').querySelector('button').focus();};
document.addEventListener('click',e=>{if(!e.target.closest('.po-share-wrap'))poCloseShare();});
$('poShareMenu').parentElement.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();poCloseShare(true);}else if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();$('poShareMenu').hidden=false;$('poShareToggle').setAttribute('aria-expanded','true');const buttons=[...$('poShareMenu').querySelectorAll('button')],i=buttons.indexOf(document.activeElement),next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowUp'?-1:1)+buttons.length)%buttons.length;buttons[next].focus();}};
$('view-playoffs').querySelector('[role=tablist]').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const i=poTabs.indexOf(poTab),index=e.key==='Home'?0:e.key==='End'?poTabs.length-1:(i+(e.key==='ArrowLeft'?-1:1)+poTabs.length)%poTabs.length;poTab=poTabs[index];poRender();$('poTab'+poTab[0].toUpperCase()+poTab.slice(1)).focus();};
function poChartReadout(e){const p=e.target.closest('[data-po-point]'),h=e.target.closest('[data-po-history]');if(p)$('poDistributionReadout').textContent=`${p.dataset.poPoint} final points · ${Number(p.dataset.poProb).toFixed(2)}% of simulations`;if(h){const point=poData.history[+h.dataset.poHistory],index=$('poHistoryMetric').value==='cup'?1:0;$('poHistoryReadout').textContent=`${poTeamRecord(h.dataset.poHteam).name} · ${poDate(point.at)} · ${poModel.percent(point.teams[h.dataset.poHteam][index])}`;}}
for(const event of ['pointerover','focusin','click'])$('view-playoffs').addEventListener(event,poChartReadout);
$('poImageClose').onclick=()=>$('poImageDialog').close();$('poImageDialog').addEventListener('close',()=>{if(poImageURL)URL.revokeObjectURL(poImageURL);poImageURL='';$('poImagePreview').removeAttribute('src');$('poImageSave').removeAttribute('href');$('poShareToggle').focus();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poRefresh();});
