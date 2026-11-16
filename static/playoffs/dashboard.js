const poOddsColumns=[['playoffs','Playoffs'],['round2','Round 2'],['conference','Conf. final'],['final','Cup Final'],['cup','Win Cup'],['points','PTS'],['projected','Proj. PTS'],['gp','GP'],['record','W–L–OT'],['winPct','Win %']];
const poStatColumns=[['gp','GP'],['record','W–L–OT'],['points','PTS'],['winPct','Win %'],['pointPct','Points %'],['gf','GF'],['ga','GA'],['diff','+/−'],['rw','RW'],['row','ROW'],['form','Last 10']];
let poGamesMode='upcoming',poGamesDate='',poGamesAutoDate=true,poGamesZone='',poCircleSelected='',poCircleStage='cup',poCircleKeyFocus=false;
let poCircleHoverFrame=0,poCirclePendingHover=null,poCircleFocusKey='',poCircleTipKey='',poCircleTipSize=null,poCircleBounds=null,poCircleActiveNodes=[];
let poBracketSelected='',poBracketKeyFocus=false;
const poCircleNodes=new Map();
const poLiveGames=new Map();
let poLiveTimer=null,poLiveController=null,poLiveRequest=0,poLiveAttempt=0,poLiveScope='',poLiveBusy=false,poLiveError=false;
const poGamePair=(away,home,extra='')=>`<div class="po-game-pair${extra?' '+extra:''}"><span>${away}</span><span>${home}</span></div>`;
function poLiveFor(g){const s=poLiveGames.get(g.id);return s&&s.home===g.home&&s.away===g.away&&s.start===g.start?s:null;}
function poEffectiveGame(g){
 if(['OFF','FINAL'].includes(g.state))return g;
 const s=poLiveFor(g);if(!s||s.status==='scheduled')return g;
 if(s.status==='final')return {...g,state:s.state,hg:s.home_score,ag:s.away_score,end:s.end};
 return ['LIVE','CRIT'].includes(s.state)?{...g,state:s.state}:g;
}
function poGameWin(g,part='all'){
 const s=poLiveFor(g),playing=['LIVE','CRIT'].includes(g.state),final=['OFF','FINAL'].includes(g.state);
 if(playing&&!final){
  const available=s?.status==='live',delayed=poLiveError||!s||Date.now()-Date.parse(s.at)>90000;
  const values=available?poGamePair(poModel.percent(s.away_win),poModel.percent(s.home_win)):poGamePair('—','—');
  const label=available?delayed?'DELAYED':'LIVE':s?.reason==='shootout'?'SHOOTOUT':'LIVE UNAVAILABLE';
  const at=available?`As of ${new Date(s.at).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',second:'2-digit'})}`:s?.reason==='shootout'?'Awaiting the shootout result':'Waiting for score and clock data';
  const note=`<small class="po-game-basis"><span class="po-live-badge${delayed||!available?' po-live-delayed':''}">${label}</span><span class="po-live-time">${esc(at)}${s?.model==='sweater-live-v1'?' · Penalty feed unavailable; score/clock estimate':''}</span></small>`;
  return part==='prices'?values:part==='note'?note:values+note;
 }
 const values=poGamePair(poModel.percent(g.prediction.away_win),poModel.percent(g.prediction.home_win)),note='<small class="po-game-basis">Pregame</small>';
 return part==='prices'?values:part==='note'?note:values+note;
}
function poGamePhase(s){
 const seconds=s?.seconds_remaining,clock=Number.isInteger(seconds)?`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`:'';
 const period=s?.period_type==='SO'?'Shootout':s?.period_type==='OT'?`OT${s.period>4?' '+(s.period-3):''}`:s?.period?'P'+s.period:'';
 const stage=period?`<strong class="po-period-label">${esc(period)}</strong>`:'',resurfacer='<svg class="po-intermission-icon" viewBox="0 0 34 23" aria-hidden="true"><path d="M3 9h8V4h14l5 6v8H3Z" fill="currentColor" opacity=".2"/><path d="M3 9h8V4h14l5 6v8H3Zm8 0h19M15 4v5M3 14h8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M17 5h7l3 3H17Z" fill="currentColor" opacity=".55"/><path d="M1 18h6v3H1Z" fill="currentColor" opacity=".5"/><circle cx="9" cy="18" r="3" fill="currentColor"/><circle cx="25" cy="18" r="3" fill="currentColor"/></svg>';
 return s?.intermission?`<span class="po-intermission-label">${resurfacer}<strong>Intermission</strong></span>${stage?' · '+stage:''}`:[stage,esc(clock)].filter(Boolean).join(' · ');
}
function poGameStatus(g){
 const s=poLiveFor(g),final=['OFF','FINAL'].includes(g.state);
 if(final)return poGamePair(`<b>${g.ag}</b>`,`<b>${g.hg}</b>`)+`<small class="po-game-basis">Final${g.end==='REG'?'':' / '+g.end}</small>`;
 if(['LIVE','CRIT'].includes(g.state)){
  const scores=Number.isInteger(s?.home_score)&&Number.isInteger(s?.away_score)?poGamePair(`<b>${s.away_score}</b>`,`<b>${s.home_score}</b>`):'<span>In progress</span>';
  return scores+`<small class="po-game-basis po-period-status">${poGamePhase(s)}</small>`;
 }
 return `<div class="po-scheduled-time"><span>${esc(new Date(g.start).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',timeZoneName:'short'}))}</span><small class="po-game-basis">${g.state==='PRE'?'Pregame':'Scheduled'}</small></div>`;
}
function poGameBasis(g){const p=g.prediction,text=['LIVE','CRIT'].includes(g.state)?'<span class="po-live-match">LIVE</span>':p.basis==='reconstructed'?'Reconstructed':p.basis==='recorded'?'Saved pregame':'Pregame estimate',previous=p.model&&p.model!==poData.model||p.basis==='recorded'&&poData.advanced?.skater_impact&&p.impact_model!==poData.advanced.skater_impact.version;return text+(g.neutral?' · neutral site':'')+(previous?' · previous model':'');}
function poStopLive(){clearInterval(poLiveTimer);poLiveTimer=null;poLiveRequest++;poLiveController?.abort();poLiveController=null;poLiveBusy=false;poLiveAttempt=0;poLiveScope='';}
function poLiveDates(){
 if($('view-playoffs').hidden||document.hidden||poTab!=='games'||poGamesMode!=='upcoming')return [];
 const today=Date.parse(poModel.localDay(Date.now(),'America/New_York')+'T12:00:00Z');
 return [...new Set((poData?.games||[]).map(poEffectiveGame).filter(g=>!['OFF','FINAL'].includes(g.state)&&poModel.localDay(g.start)===poGamesDate&&Math.abs(Date.parse(g.date+'T12:00:00Z')-today)<=86400000).map(g=>g.date))].sort();
}
function poSyncLive(){
 if(!poLiveDates().length){poStopLive();return;}
 if(!poLiveTimer)poLiveTimer=setInterval(()=>poUpdateLive(true),30000);
 poUpdateLive();
}
function poApplyLive(){
 const games=(poData?.games||[]).map(poEffectiveGame),results=poGamesMode==='results',shown=games.filter(g=>poModel.localDay(g.start)===poGamesDate&&(results?['OFF','FINAL'].includes(g.state):!['OFF','FINAL'].includes(g.state))),rows=[...$('poGamesRows').querySelectorAll('[data-po-game]')];
 if(shown.length!==rows.length||rows.some(row=>!shown.some(g=>String(g.id)===row.dataset.poGame))){poRenderGames();return;}
 for(const row of rows){const g=shown.find(g=>String(g.id)===row.dataset.poGame);row.querySelector('.po-model-win').innerHTML=poGameWin(g);row.querySelector('.po-game-status').innerHTML=poGameStatus(g);row.querySelector('.po-market-cell').innerHTML=poMarketMoneyline(g);row.querySelector('.po-match-basis').innerHTML=poGameBasis(g);}
 for(const card of $('poGameCards').querySelectorAll('[data-po-game]')){
  const g=shown.find(g=>String(g.id)===card.dataset.poGame);if(!g){poRenderGames();return;}
  card.querySelector('.po-game-status').innerHTML=poCardStatus(g);card.querySelector('.po-model-win').innerHTML=poGameWin(g,'prices');card.querySelector('.po-card-win-note').innerHTML=poGameWin(g,'note');card.querySelector('.po-market-cell').innerHTML=poMarketMoneyline(g,'prices');card.querySelector('.po-card-market-note').innerHTML=poMarketMoneyline(g,'note');
  const scoreboard=card.querySelector('.po-card-scoreboard'),scores=poCardScoreboard(g);scoreboard.innerHTML=scores;scoreboard.hidden=!scores;
 }
 if(typeof poGCMarket==='function')poGCMarket();
}
async function poUpdateLive(force=false){
 const dates=poLiveDates(),scope=dates.join(',');if(!scope)return;
 if(scope!==poLiveScope){poLiveController?.abort();poLiveRequest++;poLiveBusy=false;poLiveAttempt=0;poLiveScope=scope;}
 if(poLiveBusy||!force&&Date.now()-poLiveAttempt<30000)return;
 poLiveAttempt=Date.now();poLiveBusy=true;const request=++poLiveRequest,controller=new AbortController();poLiveController=controller;const timeout=setTimeout(()=>controller.abort(),12000);
 try{
  const feeds=await Promise.all(dates.map(async date=>{const response=await fetch((API_ON?API:'https://api.sweater.win')+'/api/playoffs/live?date='+date+'&penalties=1',{credentials:'omit',cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const data=poModel.liveFeed(await response.json(),poData.games);if(!data)throw Error();return data;}));
  if(request!==poLiveRequest)return;
  for(const feed of feeds)for(const s of feed.games){const previous=poLiveGames.get(s.id);if(!previous||Date.parse(s.at)>=Date.parse(previous.at))poLiveGames.set(s.id,s);}
  const known=new Set(poData.games.map(g=>g.id));for(const id of poLiveGames.keys())if(!known.has(id))poLiveGames.delete(id);
  poLiveError=false;poApplyLive();
 }catch{if(request===poLiveRequest){poLiveError=true;poApplyLive();}}finally{clearTimeout(timeout);if(request===poLiveRequest){poLiveBusy=false;poLiveController=null;}}
}
function poCircleLogoURL(team){return `team-crests/${team}.svg`;}
const poRatePercent=n=>Number.isFinite(n)?n.toFixed(1)+'%':'—';
function poGamesKey(data){return JSON.stringify([data.goalie_leaders,(data.games||[]).map(g=>[g.id,g.state,g.hg,g.ag,g.end,g.start,g.home_shots,g.away_shots,g.prediction?.home_win,g.prediction?.home_goals,g.prediction?.away_goals,g.prediction?.basis,g.market,g.context])]);}
function poMarketMoneyline(g,part='all'){
 if(['LIVE','CRIT'].includes(g.state)){
  const m=poLiveFor(g)?.market,available=m?.status==='live',delayed=poLiveError||!!m&&Date.now()-Date.parse(m.observed_at)>90000;
  const pre=g.market?.provider==='DraftKings'?{...g.market,basis:'pregame'}:null,q=available?m:m?.last_quote||pre;
  const number=n=>(n>0?'+':'−')+Math.abs(n).toLocaleString(),prices=q?poGamePair(number(q.away),number(q.home),'po-market-prices'):poGamePair('—','—','po-market-prices');
  const label=delayed?'DELAYED':available?'LIVE':m?.status==='suspended'?'SUSPENDED':q?'LAST QUOTE':'UNAVAILABLE';
  const href=q?.source_url||m?.source_url||g.market?.source_url,shownAt=q?.observed_at||m?.observed_at;
  const source=href?`<div class="po-market-attribution"><a class="po-market-source" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${q||m?.source_url?'DraftKings via ESPN':'ESPN game'}</a>${shownAt?`<time class="po-market-time" datetime="${esc(shownAt)}">${esc(poDate(shownAt))}</time>`:''}</div>`:'';
  const note=`${source}<small class="po-game-basis"><span class="po-live-badge${delayed||!available?' po-live-delayed':''}${!delayed&&m?.status==='suspended'?' po-market-suspended':''}">${label}</span>${!shownAt?'<span class="po-live-time">Live DraftKings quote unavailable</span>':''}</small>`;
  return part==='prices'?prices:part==='note'?note:prices+note;
 }
 const m=g.market;if(!m)return part==='prices'?poGamePair('—','—'):part==='note'?'<small class="po-game-basis">Sportsbook quote unavailable</small>':'<span class="po-market-unavailable">Unavailable</span>';
 const number=n=>(n>0?'+':'−')+Math.abs(n).toLocaleString(),past=Date.now()>=Date.parse(g.start),stale=!past&&Date.now()-Date.parse(m.observed_at)>1800000;
 const prices=poGamePair(number(m.away),number(m.home),'po-market-prices'),note=`<div class="po-market-attribution"><a class="po-market-source" href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">${esc(m.provider)} via ESPN</a><time class="po-market-time" datetime="${esc(m.observed_at)}">${esc(poDate(m.observed_at))}</time></div><small class="po-game-basis${stale?' po-market-stale':''}">${past?'Saved pregame':stale?'Older quote':'Pregame'}</small>`;
 return part==='prices'?prices:part==='note'?note:prices+note;
}
function poGoalieStats(player,game){
 const s=player.stats;if(!s)return '<p class="po-goalie-stats-missing">Season stats unavailable</p>';
 const current=game&&!['OFF','FINAL'].includes(game.state)&&typeof poData!=='undefined'&&poData?.goalie_leaders?.season===s.season?poData.goalie_leaders:null,leader=current?.players?.[player.id];
 const ranks=current?Object.fromEntries(['sv','gaa'].filter(key=>leader?.ranks?.[key]&&Number.isFinite(s[key])&&Math.abs(s[key]-leader[key])<=(key==='sv'?.00001:.0001)).map(key=>[key,leader.ranks[key]])):s.ranks;
 const values=[['GP',s.gp],['GS',s.gs],['SV%',s.sv===null?'—':s.sv.toFixed(3).replace(/^0/,''),'sv'],['GAA',s.gaa===null?'—':s.gaa.toFixed(2),'gaa']];
 return `<div class="po-goalie-stats" aria-label="Current-season NHL goalie statistics">${values.map(([label,value,field])=>{const rank=ranks?.[field],medal=['gold','silver','bronze'][rank-1],title=medal?`NHL ${label} leader · ${['1st','2nd','3rd'][rank-1]} · ${poDate(current?.as_of||s.as_of)}`:'';return `<span${medal?` class="po-goalie-medal po-medal-${medal}" title="${esc(title)}" aria-label="${esc(title)}: ${value}"`:''}><small>${label}</small><b>${value}</b></span>`;}).join('')}</div>${s.status==='cached'?`<small class="po-goalie-stats-age">Last available stats · ${poDate(s.as_of)}</small>`:''}`;
}
function poGameGoalie(g,side){
 const goalie=g.context?.[side]?.goalie;if(!goalie)return '';
 const top=goalie.players?.[0];if(!top||goalie.status==='unknown')return '<small class="po-game-goalie">Starter unconfirmed</small>';
 const confirmed=goalie.status==='confirmed',report=goalie.report,shown=report?.status==='likely'?goalie.players.find(p=>p.id===report.player_id)||top:top;
 const chance=shown.probability>0&&shown.probability<1?'&lt;1%':shown.probability>99&&shown.probability<100?'&gt;99%':`${Math.round(shown.probability)}%`,style=`--po-start-hue:${Math.round(shown.probability*1.2)}`;
 const status=confirmed?`<a class="po-goalie-confirmed" href="${esc(report.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Confirmed starter report for ${esc(shown.name)}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3.5 8 3 3 6-6"/></svg>Confirmed</a>`:report?.status==='likely'?`<a class="po-goalie-chance" style="${style}" href="${esc(report.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="${Math.round(shown.probability)}% chance to start; likely starter report for ${esc(shown.name)}">${chance}</a>`:`<span class="po-goalie-chance" style="${style}" aria-label="${Math.round(shown.probability)}% chance to start">${chance}</span>`;
 return `<div class="po-game-goalie"><div class="po-goalie-heading"><strong>${esc(shown.name)}</strong>${status}</div>${report?.status==='conflicting'?'<small>Reports conflict · starter unconfirmed</small>':''}${poGoalieStats(shown,g)}</div>`;
}
function poReturnEstimate(value){
 const day=typeof value==='string'?value.slice(0,10):'';
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(Date.parse(day)))return 'Return date unknown';
 const date=new Date(day+'T12:00:00'),label=date.toLocaleDateString(undefined,{month:'short',day:'numeric',...(date.getFullYear()!==new Date().getFullYear()?{year:'numeric'}:{})});
 return day<poModel.localDay(Date.now())?`Previous estimate ${label} · awaiting update`:`Est. return ${label}`;
}
function poInjuryPortrait(player){
 const espn=typeof player.portrait_url==='string'&&/^https:\/\/a\.espncdn\.com\/i\/headshots\/nhl\/players\/full\/\d+\.png$/.test(player.portrait_url)?player.portrait_url:'',nhl=Number.isInteger(player.player_id)&&player.player_id>0&&player.player_id<100000000?`https://assets.nhle.com/mugs/nhl/latest/${player.player_id}.png`:'',url=espn||nhl;
 const image=url?`<img src="${esc(url)}"${espn&&nhl?` data-po-injury-fallback="${esc(nhl)}"`:''} alt="" loading="lazy" decoding="async" data-po-injury-image>`:'';
 return `<span class="po-injury-portrait" aria-hidden="true"><svg viewBox="0 0 40 40" fill="currentColor"><circle cx="20" cy="13" r="7"/><path d="M6 39v-5c0-8 5-12 14-12s14 4 14 12v5Z"/></svg>${image}</span>`;
}
function poInjuryBadge(i){
 const label=/injured reserve|^ir$/i.test(i.status)?'IR':/day.?to.?day|^dtd$/i.test(i.status)?'DTD':i.status;
 const report=i.report,rotowire=report?.source==='RotoWire RSS'&&/^https:\/\/www\.rotowire\.com\/hockey\/player\/[a-z0-9-]+-\d+$/.test(report.source_url||''),espn=/^https:\/\/www\.espn\.com\/nhl\/player\/(?:news\/)?_\/id\/\d+(?:\/[a-z0-9-]+)?$/.test(i.source_url||'');
 const href=rotowire?report.source_url:espn?i.source_url.replace('/player/news/','/player/'):'',source=rotowire?'RotoWire':'ESPN',reason=report?.reason||i.reason,title=`${i.name}${reason?' · '+reason:''} · Read ${source} injury report`;
 return href?`<a class="po-injury-status" href="${esc(href)}" target="_blank" rel="noopener noreferrer" title="${esc(title)}" aria-label="${esc(title)}">${esc(label)}<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4 2h6v6M10 2 3 9"/></svg></a>`:`<span class="po-injury-status">${esc(label)}</span>`;
}
function poInjurySummary(c){
 if(c.injury_status==='not_reconstructed')return '<p class="po-availability-note">Historical injury reports unavailable.</p>';
 if(!['reported','cached','stale'].includes(c.injury_status))return '<p class="po-availability-note">Injury report unavailable.</p>';
 const injuries=c.injuries||[],note=c.injury_status==='stale'?'Older injury report; availability may have changed.':c.injury_status==='cached'?'Last available injury report.':'';
 return (note?`<p class="po-availability-note">${note}</p>`:'')+(injuries.length?`<ul class="po-injury-list">${injuries.map(i=>`<li>${poInjuryPortrait(i)}<div class="po-injury-copy"><strong>${esc(i.name)}</strong><small>${esc([i.report?.reason||i.reason,poReturnEstimate(i.return_estimate)].filter(Boolean).join(' · '))}</small></div>${poInjuryBadge(i)}</li>`).join('')}</ul>`:'<p class="po-availability-note">No absences listed.</p>');
}
function poAvailabilityBody(g,goalies=false){
 if(!g.context)return '<p class="po-availability-note">Team availability unavailable.</p>';
 const teams=['away','home'].map(side=>{
  const c=g.context[side];
  return `<section><div class="po-availability-team"><img src="team-crests/${g[side]}.svg" alt=""><div><b>${esc(poTeamRecord(g[side])?.name||g[side])}</b><small>${c.rest_days===1?'Back-to-back':`${c.rest_days===7?'7+':c.rest_days} days since last game`}</small></div></div>${goalies?poGameGoalie(g,side):''}${poInjurySummary(c)}${poSkaterImpact(c.skater_impact)}</section>`;
 });
 const reported=g.context.home.injury_reported_at||g.context.away.injury_reported_at;
 return `<div class="po-availability-teams">${teams.join('')}</div><small class="po-availability-source"><a href="https://www.espn.com/nhl/injuries" target="_blank" rel="noopener noreferrer">ESPN injury report</a>${reported?` · ${poDate(reported)}`:''}<br>Linked status badges open the matching RotoWire report when available, otherwise the player’s ESPN overview. Return dates are estimates and may change.</small>`;
}
function poSkaterImpact(impact){
 if(!impact||!['available','partial'].includes(impact.status)||!impact.players?.length)return '';
 const signed=(n,suffix='%')=>`${n>0?'+':''}${Number(n).toFixed(1)}${suffix}`;
 const game=Number.isFinite(impact.game_win)&&Number.isFinite(impact.game_win_if_available)?`<p class="po-impact-comparison"><strong>${impact.game_win.toFixed(1)}%</strong> win chance · <strong>${impact.game_win_if_available.toFixed(1)}%</strong> if these skaters were available <span>(${signed(impact.win_change_pp,' pp')})</span></p>`:'';
 return `<details class="po-skater-impact"><summary>Player availability impact <span>Beta</span></summary>${game}<p>Estimated scoring change with each player absent versus available, including projected replacements. Other listed absences stay in place.</p><div class="po-impact-players">${impact.players.map(p=>`<article><strong>${esc(p.name)}</strong><div><span>Team scoring <b>${signed(p.attack_change_pct)}</b></span><span>Opponent scoring <b>${signed(p.opponent_attack_change_pct)}</b></span></div><small>${p.expected_minutes.ev.toFixed(1)} EV · ${p.expected_minutes.pp.toFixed(1)} PP · ${p.expected_minutes.pk.toFixed(1)} PK projected min${p.sample==='trained'?'':' · replacement prior'}</small></article>`).join('')}</div><p class="po-impact-note">Training through ${esc(impact.trained_through)} · Usage through ${esc(impact.usage_through||'unavailable')}. Recovery windows are assumptions around reported estimates, not confirmed return dates. Estimates can be small or positive; star status does not set the result.${impact.status==='partial'?' Some additional absences have no sampled recovery date.':''}</p></details>`;
}
function poGameContext(g){return `<details class="po-game-context" data-po-disclosure="availability"><summary data-po-center="${g.id}" aria-haspopup="dialog">Team availability / Game Center</summary>${poAvailabilityBody(g)}</details>`;}
function poCardScore(g,side){const s=poLiveFor(g),value=['OFF','FINAL'].includes(g.state)?g[side==='home'?'hg':'ag']:['LIVE','CRIT'].includes(g.state)?s?.[side+'_score']:null;return Number.isInteger(value)?String(value):'';}
function poCardScoreboard(g){
 const scores={away:poCardScore(g,'away'),home:poCardScore(g,'home')};if(scores.away===''||scores.home==='')return '';
 return `<small>${['OFF','FINAL'].includes(g.state)?'Final score':'Live score'}</small>${['away','home'].map(side=>`<span><abbr title="${esc(poTeamRecord(g[side])?.name||g[side])}">${esc(g[side])}</abbr><b data-po-score="${side}">${scores[side]}</b></span>`).join('')}`;
}
function poCardStatus(g){
 if(['OFF','FINAL'].includes(g.state))return `<b>Final${g.end==='REG'?'':' / '+esc(g.end)}</b><span>${g.prediction.basis==='reconstructed'?'Reconstructed forecast':'Saved pregame forecast'}</span>`;
 if(['LIVE','CRIT'].includes(g.state))return `<span class="po-live-match">LIVE</span><span class="po-period-status">${poGamePhase(poLiveFor(g))||'In progress'}</span>`;
 return `<b>${esc(new Date(g.start).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',timeZoneName:'short'}))}</b><span>${g.state==='PRE'?'Pregame':'Scheduled'}</span>`;
}
function poGameCard(g){
 const results=['OFF','FINAL'].includes(g.state),scoreboard=poCardScoreboard(g),team=side=>`<button class="po-card-team" type="button" data-po-team="${g[side]}"><img src="team-crests/${g[side]}.svg" alt=""><span>${esc(poTeamRecord(g[side])?.name||g[side])}</span></button>`;
 const details=['away','home'].map(side=>`<section><div class="po-availability-team"><img src="team-crests/${g[side]}.svg" alt=""><b>${esc(poTeamRecord(g[side])?.name||g[side])}</b></div>${poGameGoalie(g,side)||'<p class="po-availability-note">Starting goalie unavailable</p>'}<p class="po-card-game-stats"><span>Sweater model goals <b>${g.prediction[side+'_goals'].toFixed(2)}</b></span>${results?`<span>Shots <b>${g[side+'_shots']??'—'}</b></span><span>Goals / shot <b>${poRatePercent(poModel.shooting(g,side))}</b></span>`:''}</p></section>`).join('');
 return `<article class="po-game-card" data-po-game="${g.id}" aria-label="${esc(g.away+' at '+g.home)}"><header class="po-game-status">${poCardStatus(g)}</header><div class="po-card-scoreboard" role="group" aria-label="Game score"${scoreboard?'':' hidden'}>${scoreboard}</div><div class="po-card-metrics"><div><small>Matchup</small>${poGamePair(team('away'),team('home'))}</div><div><small aria-label="Sweater model win percentage">Win %</small><div class="po-model-win">${poGameWin(g,'prices')}</div></div><div><small>Moneyline</small><div class="po-market-cell">${poMarketMoneyline(g,'prices')}</div></div></div><div class="po-card-win-note">${poGameWin(g,'note')}</div><div class="po-card-market-note">${poMarketMoneyline(g,'note')}</div><details class="po-card-extra" data-po-disclosure="stats"><summary>Starting goalies & game stats</summary><div>${details}</div><small class="po-availability-source">Goals are Sweater’s saved pregame projection.${g.neutral?' Neutral site.':''}${g.prediction.basis==='reconstructed'?' Forecast reconstructed from earlier dates.':''}</small></details>${poGameContext(g)}</article>`;
}
function poLocalClockChanged(){return poGamesAutoDate&&poGamesDate!==poModel.localDay(Date.now())||poGamesZone!==Intl.DateTimeFormat().resolvedOptions().timeZone;}
function poFilteredTeams(){const conference=$('poConference').value;return (poData?.teams||[]).filter(t=>conference==='all'||t.conference===conference).sort((a,b)=>(poDescending?-1:1)*(poModel.sortValue(a,poSort)-poModel.sortValue(b,poSort))||a.name.localeCompare(b.name));}
function poOddsValue(n){const secondary=poFormat==='percent'?poModel.fair(n,'american'):poModel.percent(n);return `<b>${poModel.fair(n,poFormat)}</b><small>${secondary}</small>`;}
function poRenderBoard(){
 const columns=$('poLeagueView').value==='stats'?poStatColumns:poOddsColumns,teams=poFilteredTeams(),field=poTodayMode?poTodayField:null;
 $('poLeagueSummary').textContent=`${teams.length} teams · ${poTodayMode?(field?teams.filter(t=>field.qualifiers.includes(t.abbr)).length+' qualify at this snapshot · Darkened teams are outside the field.':'Playoff seed ordering is unavailable for this snapshot.'):(poData?.simulations||50000).toLocaleString()+' season simulations · Select a team for its full breakdown.'}`;
 $('poTableHead').innerHTML=`<tr><th scope="col" class="po-logo-head"><span class="po-sr">Team logo</span></th><th scope="col" class="po-team-head">Team</th>${columns.map(([key,label])=>`<th scope="col" data-po-column="${key}"${key===poSort?` aria-sort="${poDescending?'descending':'ascending'}"`:''}>${key==='record'?label:`<button type="button" data-po-sort="${key}">${label}${key===poSort?(poDescending?' ↓':' ↑'):''}</button>`}</th>`).join('')}</tr>`;
 $('poRows').innerHTML=teams.map(t=>{const r=poModel.record(t),outside=!!field&&!field.qualifiers.includes(t.abbr),clinch=PLAYOFF_FIELD.clinched(t),seed=field?.seeds[t.abbr],attrs=outside?'disabled aria-disabled="true"':`data-po-team="${t.abbr}"`,flag=clinch?` <em class="po-clinch-badge" aria-label="${esc(clinch.label)}" title="${esc(clinch.label)}">${clinch.code}</em>`:'';return `<tr class="${outside?'po-outside-field ':''}${clinch?'po-clinched':''}" data-po-field="${outside?'outside':field?'qualified':'forecast'}"><td class="po-logo-cell"><button type="button" class="po-team-button po-logo-button" ${attrs} aria-label="${esc(outside?t.name+' is outside this playoff field':'View '+t.name+' breakdown')}"><img src="team-crests/${t.abbr}.svg" alt=""></button></td><td class="po-name-cell"><button type="button" class="po-team-button" ${attrs}><span><b>${esc(t.name)}${flag}</b><small>${esc(t.division)}${seed?' · '+seed:outside?' · Outside field':''}</small></span></button></td>${columns.map(([key])=>{
  if(poStages.some(([s])=>s===key))return `<td class="po-odds-cell" style="--po-intensity:${Math.round(t.odds[key]*.13)}%;--po-heat-hue:${Math.round(t.odds[key]*1.28)}">${poOddsValue(t.odds[key])}</td>`;
  const value=key==='record'?`${r.wins}–${r.losses}–${r.ot}`:key==='winPct'?poRatePercent(r.winPct):key==='pointPct'?poRatePercent(r.pointPct):key==='projected'?Math.round(t.projected_points):key==='diff'?(r.diff>0?'+':'')+r.diff:key==='form'?(t.form?(()=>{const f=poModel.record(t.form);return `${f.wins}–${f.losses}–${f.ot}`;})():'—'):t[key];
  return `<td>${value}</td>`;
 }).join('')}</tr>`;}).join('');
}
function poRenderTeamStats(t){const r=poModel.record(t),f=t.form?poModel.record(t.form):null;const values=[['Record',`${r.wins}–${r.losses}–${r.ot}`],['Win %',poRatePercent(r.winPct)],['Points %',poRatePercent(r.pointPct)],['Goals for / against',`${t.gf} / ${t.ga}`],['Goal differential',(r.diff>0?'+':'')+r.diff],['Last 10',f?`${f.wins}–${f.losses}–${f.ot}`:'—']];$('poTeamRaw').innerHTML=values.map(([label,value])=>`<div><span>${label}</span><b>${value}</b></div>`).join('');}
function poRenderGames(){
 const disclosures=$('poPanelGames').querySelectorAll('[data-po-game] details[open]'),open=new Set([...disclosures].map(d=>d.closest('[data-po-game]').dataset.poGame+'|'+d.dataset.poDisclosure));
 const games=(poData?.games||[]).map(poEffectiveGame),zone=Intl.DateTimeFormat().resolvedOptions().timeZone,today=poModel.localDay(Date.now(),zone),dates=games.map(g=>poModel.localDay(g.start,zone)).sort();
 poGamesZone=zone;
 if(!poGamesDate||poGamesAutoDate)poGamesDate=today;
 $('poGamesDate').min=dates[0]||today;$('poGamesDate').max=dates.at(-1)||today;$('poGamesDate').value=poGamesDate;$('poGamesZoneNote').textContent=`Game dates and start times use your device’s time zone (${zone||'local time'}).`;
 const final=g=>['OFF','FINAL'].includes(g.state),results=poGamesMode==='results',rows=games.filter(g=>poModel.localDay(g.start,zone)===poGamesDate&&(results?final(g):!final(g))).sort((a,b)=>a.start.localeCompare(b.start));
 $('view-playoffs').querySelectorAll('[data-po-games]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.poGames===poGamesMode)));
 $('poGamesTitle').textContent=results?'Recent game analysis':'Game probabilities';
 const two=poGamePair;
 $('poGamesHead').innerHTML=`<tr><th>Matchup</th><th>${results?'Final':'Start / status'}</th><th>Sweater model win %<small>${results?'before game':'pregame / live'}</small></th><th>Market moneyline<small>sportsbook quote</small></th><th>Sweater model goals<small>before game</small></th>${results?'<th>Shots</th><th>Goals / shot</th>':''}</tr>`;
 $('poGamesRows').innerHTML=rows.map(g=>{const p=g.prediction,team=(abbr,side)=>`<div class="po-game-club"><button class="po-game-team" type="button" data-po-team="${abbr}"><img src="team-crests/${abbr}.svg" alt=""><span>${esc(poTeamRecord(abbr)?.name||abbr)}</span></button>${poGameGoalie(g,side)}</div>`;
  return `<tr data-po-game="${g.id}"><td>${two(team(g.away,'away'),team(g.home,'home'))}<small class="po-game-basis po-match-basis">${poGameBasis(g)}</small>${poGameContext(g)}</td><td class="po-game-status">${poGameStatus(g)}</td><td class="po-model-win">${poGameWin(g)}</td><td class="po-market-cell">${poMarketMoneyline(g)}</td><td>${two(p.away_goals.toFixed(2),p.home_goals.toFixed(2))}</td>${results?`<td>${two(g.away_shots??'—',g.home_shots??'—')}</td><td>${two(poRatePercent(poModel.shooting(g,'away')),poRatePercent(poModel.shooting(g,'home')))}</td>`:''}</tr>`;
 }).join('');
 $('poGameCards').innerHTML=rows.map(poGameCard).join('');
 $('poGamesEmpty').hidden=rows.length>0;$('poGamesEmpty').textContent=!poData?.analytics_version?'The game feed is updating. League projections remain available.':results?'No completed games on this date. Choose another date to review results.':'No upcoming games on this date. Select Results for finished games or choose another date.';
 $('poGamesNote').textContent=results?'Scores and shots are official NHL results. “Reconstructed” estimates use earlier calendar dates; they were not recorded before those games. Saved pregame estimates stay fixed after puck drop.':'Win percentages switch from Pregame to LIVE during play. Live checks run about every 30 seconds using NHL score, clock, and penalty data plus the saved model’s scoring rates. Delayed feeds are labelled; shootout estimates await the result. Saved pregame estimates remain available in Results. Live estimates include supported timed penalties using NHL manpower scoring rates. Missing or inconsistent penalty data falls back to score and clock. Empty-net play remains outside this adjustment.';
 for(const details of $('poPanelGames').querySelectorAll('[data-po-game] details'))if(open.has(details.closest('[data-po-game]').dataset.poGame+'|'+details.dataset.poDisclosure))details.open=true;
 poSyncLive();
}
function poDonutSector(cx,cy,outer,inner,start,end){
 const point=(r,a)=>[cx+r*Math.cos(a),cy+r*Math.sin(a)].map(v=>v.toFixed(3)).join(','),span=end-start;
 if(span>=Math.PI*2-.000001){const mid=start+Math.PI;return `M${point(outer,start)}A${outer},${outer} 0 1 1 ${point(outer,mid)}A${outer},${outer} 0 1 1 ${point(outer,end)}L${point(inner,end)}A${inner},${inner} 0 1 0 ${point(inner,mid)}A${inner},${inner} 0 1 0 ${point(inner,start)}Z`;}
 const large=span>Math.PI?1:0;return `M${point(outer,start)}A${outer},${outer} 0 ${large} 1 ${point(outer,end)}L${point(inner,end)}A${inner},${inner} 0 ${large} 0 ${point(inner,start)}Z`;
}
const poCirclePercent=n=>n>0&&n<.1?Number(n.toFixed(3))+'%':n>99.9&&n<100?n.toFixed(3)+'%':poModel.percent(n);
const poCircleRingNames={playoffs:'Make playoffs',round2:'Make 2nd round',conference:'Make conference finals',final:'Make Stanley Cup Final',cup:'Win Stanley Cup'};
function poRenderCircle(){
 const today=poTodayMode;poCircleHide();$('poProbabilityCircle').hidden=today;$('poTodayCircle').hidden=!today;$('poCircleViewControl').hidden=today;$('poCircleTitle').textContent=today?'If playoffs started today':'The playoff circle';$('poCircleSubtitle').textContent=today?'Current division seeds and wild cards, arranged into the NHL first-round bracket.':'Compare the whole league, from qualifying to lifting the Cup.';if(today){poRenderBracket();return;}
 $('poCircleChart').style.width=Number($('poCircleZoom').value)*100+'%';
 poCircleCancelHover();poCircleSelected='';poCircleKeyFocus=false;poCircleFocusKey='';poCircleTipKey='';poCircleTipSize=null;poCircleBounds=null;poCircleActiveNodes=[];poCircleNodes.clear();
 const teams=[...(poData?.teams||[])].sort((a,b)=>a.conference.localeCompare(b.conference)||a.division.localeCompare(b.division)||a.abbr.localeCompare(b.abbr)),mode=$('poCircleMode').value,rings=poModel.circleRings(mode),label=key=>poStages.find(([k])=>key===k)?.[1]||key;
 $('poCircleStageKey').innerHTML='<span>Outer → inner</span>'+poStages.map(([stage],i)=>`<button type="button" data-po-circle-set="${stage}" aria-pressed="${mode===stage}"><b>${i+1}</b>${poCircleRingNames[stage]}</button>`).join('')+(mode!=='all'?'<button type="button" data-po-circle-set="all">All rings</button>':'');
 let svg='<svg viewBox="-40 -40 920 920" aria-label="League playoff probability circle. Outer to inner: playoffs, Round 2, conference final, Cup Final, champion. Hover, focus, or tap a slice to inspect a team.">';
 rings.forEach(({stage,outer,inner})=>{const slices=poModel.circle(teams,stage);for(const s of slices){const pad=Math.min(.002,(s.end-s.start)*.06),path=poDonutSector(420,420,outer,inner,s.start+pad,s.end-pad),team=poTeamRecord(s.team);svg+=`<path d="${path}" fill="${poModel.teamColors[s.team]}" class="po-circle-slice" tabindex="0" role="button" data-po-circle-team="${s.team}" data-po-circle-stage="${stage}" aria-label="${esc(team.name)}, ${label(stage)}: ${poModel.percent(s.probability)}"></path>`;}
  for(const p of poModel.circleLabels(slices,outer,inner,stage==='playoffs'))svg+=`<text class="po-circle-percent" data-po-circle-percent="${stage}" data-po-percent-team="${p.team}" x="${p.x}" y="${p.y}" transform="rotate(${p.rotation} ${p.x} ${p.y})" text-anchor="middle" dominant-baseline="central" fill="#fff" font-size="${p.fontSize}" font-weight="650" aria-hidden="true">${p.text}</text>`;
 });
 const {outer,inner,stage:firstStage}=rings[0]||{};
 if(firstStage)for(const c of poModel.circleCallouts(poModel.circle(teams,firstStage),outer)){const size=c.logoSize,team=poTeamRecord(c.team);svg+=`<g class="po-circle-callout" tabindex="0" role="button" data-po-circle-team="${c.team}" data-po-circle-stage="${firstStage}" aria-label="${esc(team.name)}, ${label(firstStage)}: ${poCirclePercent(c.probability)}"><path d="M${c.anchorX},${c.anchorY}L${c.x},${c.y}" fill="none" stroke="var(--muted)" stroke-width="1" pointer-events="none"/><image class="po-circle-logo" data-po-circle-logo="${c.team}" x="${c.x-size/2}" y="${c.y-size/2}" width="${size}" height="${size}" href="${poCircleLogoURL(c.team)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"/><rect x="${c.x-18}" y="${c.y-18}" width="36" height="36" fill="transparent"/></g>`;}
 rings.forEach(({stage,outer})=>{const y=420-outer+12,w=poCircleRingNames[stage].length*6+12;svg+=`<g class="po-circle-ring-label" data-po-ring-label="${stage}" data-po-circle-set="${stage}" tabindex="0" role="button" aria-label="View ${poCircleRingNames[stage]}"><rect x="${420-w/2}" y="${y-9}" width="${w}" height="16" rx="4"/><text x="420" y="${y}" dominant-baseline="central" text-anchor="middle" font-size="11.5" font-weight="700">${poCircleRingNames[stage]}</text></g>`;});
 const cupRadius=mode==='all'?73:132,cupHeight=cupRadius*1.8,cupWidth=cupHeight*2/3;
 svg+=`<defs><clipPath id="poCupClip"><circle cx="420" cy="420" r="${cupRadius}"/></clipPath></defs><circle cx="420" cy="420" r="${cupRadius}" fill="#000"/><image id="poStanleyCup" x="${420-cupWidth/2}" y="${420-cupHeight/2}" width="${cupWidth}" height="${cupHeight}" href="trophies/stanley-cup.jpg" preserveAspectRatio="xMidYMid meet" clip-path="url(#poCupClip)" role="img" aria-label="Stanley Cup"/></svg>`;
 $('poCircleChart').innerHTML=(teams.length?svg:'<div class="po-empty">The circle will be available with the next verified forecast.</div>')+'<div class="po-circle-tooltip" id="poCircleTooltip" role="tooltip" hidden></div>';
 $('poCircleChart').querySelectorAll('[data-po-circle-team],[data-po-circle-logo]').forEach(node=>{const team=node.dataset.poCircleTeam||node.dataset.poCircleLogo;if(!poCircleNodes.has(team))poCircleNodes.set(team,[]);poCircleNodes.get(team).push(node);});
 $('poCircleExplanation').textContent=(mode==='all'?'Each labeled ring shows its share of that round’s expected places, from 16 playoff teams to one champion.':'Slices show each team’s share of expected places in this round. Cup slices are actual title probabilities; earlier rounds are normalized because multiple teams advance.')+(mode==='all'||mode==='playoffs'?' Every playoff percentage appears inside the outer ring; narrow slices use compact, turned labels. Later-round percentages appear where they fit.':' Percentages appear inside slices where they fit.')+' All logos sit outside the circle, with crowded crests spaced apart and connected to their slices. Hover, tap, or use the legend for every team’s exact chances.';
 const track=mode==='all'?'cup':mode;$('poCircleLegend').innerHTML=[...teams].sort((a,b)=>b.odds[track]-a.odds[track]).map(t=>`<button type="button" data-po-circle-team="${t.abbr}" data-po-circle-stage="${track}"><i style="background:${poModel.teamColors[t.abbr]}"></i><img data-po-circle-logo="${t.abbr}" src="${poCircleLogoURL(t.abbr)}" alt=""><span>${esc(t.name)}</span><b>${poModel.percent(t.odds[track])}</b></button>`).join('');
 if(!poTeamRecord(poCircleSelected))poCircleSelected='';poCircleHighlight(poCircleSelected,mode==='all'?poCircleStage:mode);
}
function poCircleReadout(t,stage){
 const readout=$('poCircleMobileReadout');if(!readout)return;
 readout.innerHTML=t?`<img src="${poCircleLogoURL(t.abbr)}" alt=""><div><button type="button" data-po-team="${t.abbr}" aria-label="View ${esc(t.name)} breakdown">${esc(t.name)} ↗</button><span>${esc(poStages.find(([key])=>key===stage)?.[1]||'')}</span></div><strong>${poCirclePercent(t.odds[stage])}</strong><button type="button" class="po-circle-dismiss" data-po-circle-close aria-label="Clear selected team">×</button>`:'<p>Tap a slice or team to see its chance here.</p>';
}
function poCircleHighlight(team,stage){
 const key=team+'|'+stage;if(poCircleFocusKey===key)return;
 if(poCircleSelected!==team||!poCircleFocusKey){for(const node of poCircleActiveNodes)node.classList.remove('po-circle-active');poCircleActiveNodes=poCircleNodes.get(team)||[];for(const node of poCircleActiveNodes)node.classList.add('po-circle-active');}
 poCircleFocusKey=key;
 poCircleSelected=team;poCircleStage=stage;const t=poTeamRecord(team);poCircleReadout(t,stage);
 if(!t){$('poCircleFocus').innerHTML='<h3>Every team. Every round.</h3><p>Hover, focus, or tap a slice to see its actual probability. Use the legend to inspect the smallest slices.</p><small>Legend: '+($('poCircleMode').value==='all'?'Win the Cup':poStages.find(([k])=>k===$('poCircleMode').value)?.[1])+'</small>';return;}
 $('poCircleFocus').innerHTML=`<div><img src="team-logos/${t.abbr}.svg" alt=""><h3>${esc(t.name)}</h3></div><p>${poStages.find(([k])=>k===stage)?.[1]} <strong>${poCirclePercent(t.odds[stage])}</strong></p><small>${poArchiveActive()?'Saved forecast · '+esc(poArchiveLabel(poArchiveDate)):'Estimated chance at this stage of the current forecast.'}</small><div class="po-circle-stage-values">${poStages.map(([key,name])=>`<p class="${key===stage?'on':''}"><span>${name}</span><b>${poCirclePercent(t.odds[key])}</b></p>`).join('')}</div><small>Fair American odds ${poModel.fair(t.odds[stage],'american')}</small><button type="button" class="po-plain-button" data-po-team="${t.abbr}">View team breakdown →</button>`;
}
function poCircleIsCompact(){return typeof matchMedia==='function'&&matchMedia('(max-width:700px)').matches;}
function poCircleTooltip(event,node){
 const tooltip=$('poCircleTooltip');if(!tooltip||!node)return;const team=poTeamRecord(node.dataset.poCircleTeam),stage=node.dataset.poCircleStage;if(!team||!stage)return;
 if(poCircleIsCompact()){tooltip.hidden=true;return;}
 if(!poCircleBounds)poCircleBounds={box:$('poCircleChart').getBoundingClientRect(),scroll:$('poCircleScroll').getBoundingClientRect(),height:innerHeight};
 const {box,scroll,height}=poCircleBounds,key=team.abbr+'|'+stage;
 if(poCircleTipKey!==key){tooltip.innerHTML=`<b>${esc(team.name)}</b><span>${poStages.find(([s])=>s===stage)[1]}</span><strong>${poCirclePercent(team.odds[stage])}</strong><small>Sweater model probability</small>`;poCircleTipKey=key;poCircleTipSize=null;}
 tooltip.hidden=false;if(!poCircleTipSize)poCircleTipSize={width:tooltip.offsetWidth,height:tooltip.offsetHeight};
 const pointer=Number.isFinite(event.clientX)&&event.type!=='focusin',target=pointer?null:node.getBoundingClientRect(),x=pointer?event.clientX-box.left:target.left+target.width/2-box.left,y=pointer?event.clientY-box.top:target.top+target.height/2-box.top,left=Math.max(4,scroll.left-box.left+4),right=Math.min(box.width,scroll.right-box.left)-poCircleTipSize.width-4,top=Math.max(0,-box.top+4),bottom=Math.min(box.height,height-box.top)-poCircleTipSize.height-4;
 tooltip.style.transform=`translate3d(${Math.round(Math.max(left,Math.min(right,x+14)))}px,${Math.round(Math.max(top,Math.min(bottom,y+14)))}px,0)`;
}
function poCircleCancelHover(){if(poCircleHoverFrame)cancelAnimationFrame(poCircleHoverFrame);poCircleHoverFrame=0;poCirclePendingHover=null;}
function poCircleHide(){poCircleCancelHover();const tooltip=$('poCircleTooltip');if(tooltip)tooltip.hidden=true;poCircleBounds=null;poCircleKeyFocus=false;for(const node of poCircleActiveNodes)node.classList.remove('po-circle-active');poCircleActiveNodes=[];poCircleSelected='';poCircleFocusKey='';if(typeof poCircleReadout==='function')poCircleReadout(null);}
function poCircleQueueHover(event,node){
 poCirclePendingHover={node,clientX:event.clientX,clientY:event.clientY,type:event.type};if(poCircleHoverFrame)return;
 poCircleHoverFrame=requestAnimationFrame(()=>{poCircleHoverFrame=0;const pending=poCirclePendingHover;poCirclePendingHover=null;if(!pending?.node.isConnected||poTab!=='circle'||$('view-playoffs').hidden)return;const node=pending.node;poCircleHighlight(node.dataset.poCircleTeam,node.dataset.poCircleStage);if(node.closest('#poCircleChart'))poCircleTooltip(pending,node);else if($('poCircleTooltip'))$('poCircleTooltip').hidden=true;});
}
$('poLeagueView').onchange=()=>{poSort=$('poLeagueView').value==='stats'?'points':'playoffs';poDescending=true;poRenderBoard();};
$('poGamesDate').onchange=e=>{poGamesAutoDate=false;poGamesDate=e.target.value;poRenderGames();};$('poCircleMode').onchange=poRenderCircle;
$('poCircleZoom').onchange=()=>{poCircleHide();$(poTodayMode?'poBracketChart':'poCircleChart').style.width=(Number($('poCircleZoom').value)*100)+'%';};
$('view-playoffs').addEventListener('click',e=>{if(e.target.closest('[data-po-circle-close]')){poCircleHide();if(e.detail===0)$('poCircleScroll').focus();return;}const set=e.target.closest('[data-po-circle-set]'),mode=e.target.closest('[data-po-games]'),slice=e.target.closest('[data-po-circle-team]');if(set){$('poCircleMode').value=set.dataset.poCircleSet;poRenderCircle();return;}if(mode){poGamesMode=mode.dataset.poGames;poGamesAutoDate=poGamesMode==='upcoming';if(poGamesMode==='results'){poGamesDate=(poData?.games||[]).map(poEffectiveGame).filter(g=>['OFF','FINAL'].includes(g.state)).map(g=>poModel.localDay(g.start)).sort().at(-1)||poModel.localDay(Date.now());}else poGamesDate=poModel.localDay(Date.now());poRenderGames();}if(slice){poCircleHighlight(slice.dataset.poCircleTeam,slice.dataset.poCircleStage);if(slice.closest('#poCircleChart'))poCircleTooltip(e,slice);}});
$('poPanelCircle').addEventListener('keydown',e=>{if(e.key==='Escape'){poCircleHide();if(poTodayMode)poBracketSelect(null);$(poTodayMode?'poBracketScroll':'poCircleScroll').focus();}});
$('poPanelCircle').addEventListener('pointerover',e=>{if(poTodayMode)return;if(e.pointerType==='touch'||poCircleIsCompact()||poCircleKeyFocus)return;const slice=e.target.closest('[data-po-circle-team]');if(slice)poCircleQueueHover(e,slice);});
$('poPanelCircle').addEventListener('pointermove',e=>{if(poTodayMode)return;if(e.pointerType==='touch'||poCircleIsCompact())return;poCircleKeyFocus=false;const slice=e.target.closest('[data-po-circle-team]');if(slice)poCircleQueueHover(e,slice);else poCircleHide();});
$('poPanelCircle').addEventListener('pointerout',e=>{if(poTodayMode)return;if(e.pointerType!=='touch'&&!poCircleIsCompact()&&!poCircleKeyFocus&&e.target.closest('[data-po-circle-team]')&&!e.relatedTarget?.closest?.('[data-po-circle-team]'))poCircleHide();});
for(const id of ['poPanelCircle','poCircleChart'])$(id).addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'&&!poCircleIsCompact())poCircleHide();});
$('poPanelCircle').addEventListener('focusin',e=>{if(poTodayMode)return;const slice=e.target.closest('[data-po-circle-team]');if(!slice){if(!e.target.closest('#poCircleMobileReadout'))poCircleHide();return;}poCircleCancelHover();poCircleKeyFocus=true;poCircleHighlight(slice.dataset.poCircleTeam,slice.dataset.poCircleStage);if(slice.closest('#poCircleChart'))poCircleTooltip(e,slice);else if($('poCircleTooltip'))$('poCircleTooltip').hidden=true;});
$('poPanelCircle').addEventListener('focusout',e=>{if(poTodayMode)return;if(!e.relatedTarget?.closest?.('[data-po-circle-team],#poCircleMobileReadout'))poCircleHide();});
window.addEventListener('scroll',()=>{poCircleBounds=null;if(poCircleIsCompact())return;if(!poCircleKeyFocus&&(poCircleSelected||poCirclePendingHover)&&!poCirclePendingHover?.node.matches(':hover'))poCircleHide();},{capture:true,passive:true});
window.addEventListener('resize',()=>{poCircleTipSize=null;poCircleHide();},{passive:true});window.addEventListener('blur',poCircleHide);
document.addEventListener('click',e=>{if(poTab==='circle'&&!$('view-playoffs').hidden&&!e.target.closest('[data-po-circle-team]'))poCircleHide();});
$('poCircleChart').addEventListener('keydown',e=>{if(!['Enter',' '].includes(e.key))return;const set=e.target.closest('[data-po-circle-set]');if(set){e.preventDefault();$('poCircleMode').value=set.dataset.poCircleSet;poRenderCircle();return;}if(e.target.matches('[data-po-circle-team]')){e.preventDefault();poCircleHighlight(e.target.dataset.poCircleTeam,e.target.dataset.poCircleStage);}});
$('poExportCSV').onclick=()=>{
 const headings=['Team','GP','W','L','OTL','PTS','Win %','Points %','GF','GA','RW','ROW','Projected points',...poStages.flatMap(([,label])=>[label+' %',label+' fair American'])],rows=poFilteredTeams().map(t=>{const r=poModel.record(t);return [t.name,t.gp,t.wins,r.losses,r.ot,t.points,r.winPct,r.pointPct,t.gf,t.ga,t.rw,t.row,t.projected_points,...poStages.flatMap(([key])=>[t.odds[key],poModel.fair(t.odds[key],'american')])];});
 const csv=[headings,...rows].map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n'),url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download='sweater-playoff-data'+(poArchiveActive()?'-'+poArchiveDate:'')+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
};

// Standings-only first-round bracket. Unknown advancing teams stay unassigned.
function poRenderBracket(){
 poBracketSelected='';poBracketKeyFocus=false;
 const host=$('poBracketChart'),field=poTodayField;
 $('poBracketCards').innerHTML='';$('poBracketReadout').textContent='Select a first-round matchup to explore the seeds.';
 if(!field){host.innerHTML='<div class="po-empty">Official seed ordering is unavailable for this snapshot. Use the probability circle or choose another date.</div>';return;}
 const matches=PLAYOFF_FIELD.geometry(field.matches),point=(r,a)=>[450+r*Math.cos(a),450+r*Math.sin(a)],xy=(r,a)=>point(r,a).map(n=>n.toFixed(2)).join(','),arc=(r,a,b)=>`M${xy(r,a)}A${r},${r} 0 0 1 ${xy(r,b)}`;
 let svg='<svg viewBox="0 0 900 900" role="group" aria-label="If playoffs started at this standings snapshot: sixteen teams in eight first-round matchups. Eastern conference on the right, Western on the left."><g class="po-bracket-paths" fill="none" stroke="var(--muted)" stroke-width="2" opacity=".65" aria-hidden="true">';
 for(const m of matches)svg+=`<path d="M${xy(243,m.angle)}L${xy(195,m.angle)}"/>`;
 for(let i=0;i<8;i+=2){const a=matches[i].angle,b=matches[i+1].angle,middle=(a+b)/2;svg+=`<path d="${arc(195,a,b)}M${xy(195,middle)}L${xy(125,middle)}"/><circle cx="${point(195,middle)[0]}" cy="${point(195,middle)[1]}" r="4" fill="var(--bg)"/>`;}
 for(let i=0;i<8;i+=4){const a=(matches[i].angle+matches[i+1].angle)/2,b=(matches[i+2].angle+matches[i+3].angle)/2,middle=(a+b)/2;svg+=`<path d="${arc(125,a,b)}M${xy(125,middle)}L${xy(65,middle)}"/>`;}
 svg+='</g><text class="po-bracket-conference" x="600" y="456" text-anchor="middle">EAST</text><text class="po-bracket-conference" x="300" y="456" text-anchor="middle">WEST</text>';
 for(const m of matches){
  const label=m.teams.map(t=>t.name+' ('+t.seed+')').join(' vs ');
  svg+=`<g class="po-bracket-match" data-po-bracket="${m.id}" tabindex="0" role="button" aria-pressed="false" aria-label="First round: ${esc(label)}">`;
  m.teams.forEach((t,j)=>{const start=m.start+j*Math.PI/8,end=start+Math.PI/8,pad=.005,[x,y]=point(304,t.angle);svg+=`<path class="po-bracket-sector" d="${poDonutSector(450,450,334,270,start+pad,end-pad)}" fill="${poModel.teamColors[t.abbr]}"/><text x="${x}" y="${y+5}" class="po-bracket-abbr" text-anchor="middle">${t.abbr}</text><image data-po-bracket-logo="${t.abbr}" x="${t.x-26}" y="${t.y-26}" width="52" height="52" href="${poCircleLogoURL(t.abbr)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"/><text x="${t.x}" y="${t.y+43}" text-anchor="middle" class="po-bracket-seed">${t.seed}</text>`;});
  const [x,y]=point(248,m.angle);svg+=`<path class="po-bracket-pair" d="${poDonutSector(450,450,264,233,m.start+.005,m.end-.005)}"/><text x="${x}" y="${y+5}" class="po-bracket-vs" text-anchor="middle">vs</text></g>`;
 }
 svg+='<circle cx="450" cy="450" r="63" fill="#000"/><defs><clipPath id="poBracketCupClip"><circle cx="450" cy="450" r="60"/></clipPath></defs><image x="414" y="396" width="72" height="108" href="trophies/stanley-cup.jpg" preserveAspectRatio="xMidYMid meet" clip-path="url(#poBracketCupClip)" role="img" aria-label="Stanley Cup"/><text x="450" y="366" text-anchor="middle" class="po-bracket-final">CUP FINAL</text></svg>';
 host.innerHTML=svg;host.style.width=Number($('poCircleZoom').value)*100+'%';
 $('poBracketCards').innerHTML=['E','W'].map(conference=>`<section><h3>${conference==='E'?'Eastern':'Western'} Conference</h3>${field.matches.filter(m=>m.conference===conference).map(m=>`<article class="po-bracket-card" data-po-bracket="${m.id}"><p>${esc(m.division)} path · Round 1</p><div>${m.teams.map(t=>`<button type="button" data-po-team="${t.abbr}" aria-label="View ${esc(t.name)} breakdown"><img src="${poCircleLogoURL(t.abbr)}" alt=""><span><b>${esc(t.name)}</b><small>${t.seed} · ${t.points} PTS · ${t.gp} GP</small></span></button>`).join('<span class="po-bracket-vs-label" aria-label="versus">VS</span>')}</div></article>`).join('')}</section>`).join('');
}
function poBracketSelect(id){
 const key=id||'';if(key===poBracketSelected)return;poBracketSelected=key;
 const m=poTodayField?.matches.find(m=>m.id===id);for(const node of $('poTodayCircle').querySelectorAll('[data-po-bracket]')){const on=!!m&&node.dataset.poBracket===id;node.classList.toggle('is-selected',on);if(node.hasAttribute('aria-pressed'))node.setAttribute('aria-pressed',String(on));}
 $('poBracketReadout').textContent=m?'Round 1 · '+m.teams.map(t=>t.name+' ('+t.seed+', '+t.points+' PTS)').join(' vs '):'Select a first-round matchup to explore the seeds.';
}
$('poTodayCircle').addEventListener('pointerover',e=>{if(e.pointerType==='touch'||poBracketKeyFocus)return;const match=e.target.closest('[data-po-bracket]');if(match)poBracketSelect(match.dataset.poBracket);});
$('poTodayCircle').addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'&&!poBracketKeyFocus)poBracketSelect(null);});
$('poTodayCircle').addEventListener('pointermove',e=>{if(e.pointerType==='touch')return;poBracketKeyFocus=false;const match=e.target.closest('[data-po-bracket]');if(match)poBracketSelect(match.dataset.poBracket);});
$('poTodayCircle').addEventListener('click',e=>{if(e.detail>0)poBracketKeyFocus=false;if(e.target.closest('[data-po-team]'))return;const match=e.target.closest('[data-po-bracket]');if(match)poBracketSelect(match.dataset.poBracket);});
$('poTodayCircle').addEventListener('focusin',e=>{poBracketKeyFocus=true;const match=e.target.closest('[data-po-bracket]');if(match)poBracketSelect(match.dataset.poBracket);});
$('poTodayCircle').addEventListener('focusout',e=>{if(!e.relatedTarget?.closest?.('[data-po-bracket]')){poBracketKeyFocus=false;poBracketSelect(null);}});
$('poTodayCircle').addEventListener('keydown',e=>{const match=e.target.closest('[data-po-bracket]');if(match&&['Enter',' '].includes(e.key)){e.preventDefault();poBracketSelect(match.dataset.poBracket);}});
