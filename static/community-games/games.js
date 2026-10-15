const COMMUNITY_DATA = /*__COMMUNITY_DATA__*/{};
const COMMUNITY_POPULARITY = /*__GRID_POPULARITY__*/{};
const cgPlayer = id => COMMUNITY_MODEL.index(COMMUNITY_DATA).players.get(id);
const cgPhoto = (id, cls = '') => `<img class="${cls}" src="https://assets.nhle.com/mugs/nhl/latest/${id}.png" alt="" decoding="async" onerror="this.onerror=null;this.src=FALLBACK">`;
const CG_CREST_SCALE={BOS:1.103,BUF:1.103,PIT:1.103,STL:1.103,VGK:1.103,FLA:1.143,NJD:1.143,NYI:1.143,SEA:1.143,DET:.889,UTA:.889,OTT:.914,CAR:.914,DAL:.914,MIN:.914,MTL:.928,TBL:1.067,TOR:1.067,PHI:1.067,CHI:1.067,COL:1.067,WPG:1.067,ANA:1.067,EDM:1.067,VAN:1.067,CBJ:1.016,NYR:1.231,WSH:.853,NSH:.970,CGY:1.123,LAK:.842,SJS:.955};
const cgTeam = team => `<img class="cg-team-art" style="--cg-crest-scale:${CG_CREST_SCALE[team]||1}" src="team-logos/${team}.svg" alt="${esc(teamName(team))}" title="${esc(teamName(team))}">`;
const cgIdentity = (id,team) => `<span class="cg-player-media">${cgPhoto(id)}<span class="cg-team-stamp">${cgTeam(team)}</span></span>`;
const cgSeason = year => `${year}–${String(year+1).slice(-2)}`;
const cgSearchMeta = p => `${p.pos} · born ${p.birthYear} · ${p.gp.toLocaleString()} career GP`;
const cgState = (id,t,guesses) => COMMUNITY_MODEL[id==='teammatetrail'?'trail':id==='benchboss'?'boss':'grid'](t,guesses,COMMUNITY_DATA);
let cgCell = 0, cgPosition = 'F', cgChoiceKey = '', cgChoices = [];
let cgGridPlayers;
const cgAnimations=new Set();let cgBudgetFrame=0,cgForfeit=null,cgDrag=null;
const cgReduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function cgAnimate(el,frames,options={}){if(cgReduced()||!el?.animate)return;const a=el.animate(frames,{duration:240,easing:'cubic-bezier(.2,.8,.2,1)',...options});cgAnimations.add(a);a.finished.then(()=>cgAnimations.delete(a),()=>cgAnimations.delete(a));return a;}
function cgCleanup(){for(const a of cgAnimations)a.cancel();cgAnimations.clear();cancelAnimationFrame(cgBudgetFrame);document.querySelectorAll('.cg-flying-player,.cg-drag-player').forEach(el=>el.remove());cgDragCancel();cgForfeit=null;if($('cgBossForfeit').open)$('cgBossForfeit').close();}
function cgFly(from,to){if(cgReduced()||!from)return;const a=from.getBoundingClientRect(),b=to?.getBoundingClientRect();if(!a.width)return;const ghost=from.cloneNode(true);ghost.classList.add('cg-flying-player');ghost.setAttribute('aria-hidden','true');ghost.style.cssText=`position:fixed;left:${a.left}px;top:${a.top}px;width:${a.width}px;height:${a.height}px;pointer-events:none;z-index:90;`;document.body.append(ghost);const end=b?.width?`translate(${b.left-a.left}px,${b.top-a.top}px) scale(${b.width/a.width})`:'translateY(8px) scale(.92)';const anim=cgAnimate(ghost,[{transform:'translate(0,0) scale(1)',opacity:.9},{transform:end,opacity:0}],{duration:b?.width?300:180});if(anim)anim.finished.then(()=>ghost.remove(),()=>ghost.remove());else ghost.remove();}
function cgBudget(cost,budget,animate){cancelAnimationFrame(cgBudgetFrame);const el=$('cgBossSpent'),from=Number(el.textContent)||0,start=performance.now();$('cgBossBudget').setAttribute('aria-valuenow',cost);$('cgBossBudget').setAttribute('aria-valuemax',budget);$('cgBossBudget').dataset.level=cost>=budget?'full':cost>=budget*.8?'near':'normal';$('cgBossBudgetBar').style.width=`${cost/budget*100}%`;
  const frame=now=>{const k=Math.min(1,(now-start)/300);el.textContent=String(Math.round(from+(cost-from)*(1-(1-k)**3)));if(k<1)cgBudgetFrame=requestAnimationFrame(frame);};if(animate&&!cgReduced())cgBudgetFrame=requestAnimationFrame(frame);else el.textContent=String(cost);
  if(animate&&cost>=budget*.8)cgAnimate($('cgBossBudget'),[{boxShadow:'0 0 0 0 transparent'},{boxShadow:'0 0 0 4px color-mix(in srgb,var(--accent) 14%,transparent)'},{boxShadow:'0 0 0 0 transparent'}],{duration:440});
}
function cgClearSearch(inputId,listId){$(inputId).value='';$(inputId).setAttribute('aria-expanded','false');$(listId).hidden=true;}

for(const [id,title,next] of [['grid','Sweater Grid','Next grid'],['benchboss','Bench Boss','Next market'],['teammatetrail','Teammate Trail','Next trails']]){
  G[id]={kind:'score',repeat:id==='teammatetrail',title,share:`Sweater ${title}`,view:`view-${id}`,max:id==='grid'?12:id==='benchboss'?1:100,
    next,hideReveal:true,quietFinish:true,persistUnlimited:true,
    pool:()=>COMMUNITY_DATA[id]||[],
    daily(k){const ref=DAILY[id]?.[k],target=this.pool().find(t=>t.id===ref?.id)||this.pool()[hash(`sweater-${id}-${k}`)%this.pool().length];return id==='grid'&&ref?.rarity?{...target,rarity:ref.rarity}:target;},
    prepareTarget(t,opts,restore){if(id!=='grid'||mode!=='unlimited')return t;const rarity=Object.hasOwn(opts,'gridRarity')?opts.gridRarity:restore.length?null:COMMUNITY_MODEL.raritySnapshot(t,COMMUNITY_POPULARITY);opts.gridRarity=rarity;return {...t,rarity};},
    random(){return pick(this.pool());},tid:t=>t.id,player:()=>null,meta:()=>'',reset(){cgCleanup();cgCell=0;cgPosition='F';cgChoiceKey='';cgChoices=[];},
    forfeited:(t,g)=>id==='benchboss'&&g.length===1&&g[0]==='END',
    guess(t,x,fresh){try{return cgState(id,t,[...S[id].guesses,x]).won;}catch(e){if(fresh)toast(e.message);return null;}},
    right(t,x,i){if(id==='grid'&&x!=='END')return cgState(id,t,S[id].guesses.slice(0,i+1)).last?.correct;if(id==='teammatetrail'&&String(x).startsWith('ADD:'))return true;},
    isDone:(t,g)=>cgState(id,t,g).over,wonGame:(t,g)=>cgState(id,t,g).won,score:(t,g)=>cgState(id,t,g).score,
    archiveStatus:h=>h.forfeit?'Forfeited':`${h.s} pts`,celebrate:()=>false,
    onFinish(st){const score=this.score(st.target,st.guesses),key=`sweater-${id}-best`;store.set(key,Math.max(score,Number(store.get(key))||0));if(id==='grid')globalThis.SweaterAnalytics?.gridAnswers?.(st.target.id,st.guesses.slice(),mode,mode==='unlimited'?dayKey():st.day);},
    endText(t,g){const state=cgState(id,t,g);return id==='grid'?{result:state.won?'Grid complete':`${state.used.size} of 9 filled`,cheer:`${state.score} points · ${state.won?'Every connection found':'See the remaining connections below'}`}:
      id==='benchboss'?{result:g[0]==='END'?'Lineup forfeited':state.perfect?'Perfect lineup':state.won?'Strong lineup':'Lineup revealed',cheer:g[0]==='END'?'0 points · no XP earned':`${state.score}/10 · ${state.points} season points · best possible ${t.par}`}:
      {result:`${state.rounds.filter(r=>r.won).length} of 3 trails connected`,cheer:`${state.score}/30 points · each link backed by NHL appearances`};},
    shareText(t,saved,num,link){const state=cgState(id,t,saved.guesses),marks=id==='grid'?[0,3,6].map(i=>state.cells.slice(i,i+3).map(x=>x?'🟩':'⬛').join('')).join('\n'):id==='teammatetrail'?state.rounds.map(r=>r.won?'🟩':'⬛').join(''):'🏒';return `Sweater ${title} #${num}\n${marks}\n${state.score}${id==='benchboss'?'/10':id==='teammatetrail'?'/30':' points'}${link}`;},
    render(t,st){if(id==='grid')renderSweaterGrid(t,st);else if(id==='benchboss')renderBenchBoss(t,st);else renderTeammateTrail(t,st);},
  };
}

const CG_TROPHY_SHORT={'Hart Memorial Trophy':'Hart','Vezina Trophy':'Vezina','Calder Memorial Trophy':'Calder','Lady Byng Memorial Trophy':'Lady Byng'};
function cgClueLabel(clue){return clue.kind==='team'?teamName(clue.value):clue.kind==='country'?`Born in ${countryName(clue.value)}`:clue.kind==='trophy'?`${CG_TROPHY_SHORT[clue.value]||clue.value} winner`:clue.kind==='season_goals'?`${clue.value}+ goals in a season`:clue.kind==='position'?{F:'Forward',D:'Defenseman',G:'Goalie'}[clue.value]:clue.kind==='games'?`${clue.value.toLocaleString()}+ career games`:'Hall of Famer';}
function cgClue(clue){
  const label=cgClueLabel(clue),art=clue.kind==='team'?`<span class="cg-crest cg-grid-crest">${cgTeam(clue.value)}</span>`:clue.kind==='country'?`<img class="cg-country-flag" src="grid-flags/${COUNTRY_ALPHA2[clue.value].toLowerCase()}.svg" alt="${esc(countryName(clue.value))} flag">`:clue.kind==='trophy'?`<img class="cg-trophy-photo" src="${TROPHY_IMAGES[clue.value]}" alt="${esc(clue.value)}">`:'';
  return `${art}<b title="${esc(clue.kind==='trophy'?clue.value:label)}">${esc(label)}</b>`;
}
function renderSweaterGrid(t,st){
  const state=COMMUNITY_MODEL.grid(t,st.guesses,COMMUNITY_DATA),display=st.over?COMMUNITY_MODEL.fillGrid(t,state,COMMUNITY_DATA):state.cells;
  cgClearSearch('cgGridGuess','cgGridOpts');
  if(state.cells[cgCell]!==null)cgCell=state.cells.findIndex(id=>id===null);
  $('cgGrid').innerHTML='<div class="cg-corner" aria-hidden="true"></div>'+t.cols.map(c=>`<div class="cg-grid-heading${c.kind==='team'?' cg-team-heading':''}">${cgClue(c)}</div>`).join('')+t.rows.map((team,row)=>
    `<div class="cg-grid-heading cg-team-heading">${cgClue({kind:'team',value:team})}</div>`+t.cols.map((clue,col)=>{
      const cell=row*3+col,id=display[cell],p=id&&cgPlayer(id),filled=state.cells[cell]!==null;
      return `<button type="button" class="cg-square${filled?' is-filled':id?' is-revealed':''}${cgCell===cell&&!st.over?' is-active':''}" data-grid-cell="${cell}" aria-label="${esc(`${teamName(team)} · ${cgClueLabel(clue)} ${p?': '+p.name:': choose a player'}`)}" aria-pressed="${cgCell===cell&&!st.over}"${filled||st.over?' disabled':''}>${p?cgPhoto(id)+`<b>${esc(p.name)}</b>${filled?`<small>+${10+COMMUNITY_MODEL.bonus(t,cell,p)}</small>`:'<small>Valid example</small>'}`:'<span aria-hidden="true">+</span><small>Choose player</small>'}</button>`;
    }).join('')).join('');
  $('cgGridScore').textContent=`${state.used.size} / 9 filled · ${state.score} points`;
  $('cgGridTries').textContent=st.over?'':`${12-state.tried.size} guesses left`;
  $('cgGridSearch').hidden=st.over;
  $('cgGridGuess').disabled=st.over;
  $('cgGridPrompt').textContent=st.over?'':`${teamName(t.rows[Math.floor(cgCell/3)])} · ${cgClueLabel(t.cols[cgCell%3])}`;
  $('cgGridSource').textContent=`Team connections require a played NHL regular-season game. ${COMMUNITY_DATA.grid_asof?'Verified through '+COMMUNITY_DATA.grid_asof:'Club appearances through 2025–26'}; predecessor clubs are separate. Trophy wins and 30-goal regular seasons can be with any NHL team. A traded player’s goals count across all teams that season. Less popular answers earn bigger bonuses once enough games have been played. Until then, short team stints earn bonuses.`;
  const last=state.last;
  $('cgGridFeedback').textContent=st.over?state.won?'All nine connections found. Every square accepts multiple players.':'Each square accepts multiple players. Muted cards show valid examples; highlighted answers are yours.':last?last.correct?`${cgPlayer(last.id).name} fits. +${10+COMMUNITY_MODEL.bonus(t,last.cell,cgPlayer(last.id))} points.`:`${cgPlayer(last.id).name} doesn’t match that square. Try another connection.`:'Select a square, then search for a player.';
  $('cgGridReveal').hidden=st.over;
  cgFitGridLabels();
}
function cgFitGridLabels(){for(const label of $('cgGrid').querySelectorAll('.cg-grid-heading b')){label.style.fontSize='';const maximum=parseFloat(getComputedStyle(label).fontSize);let size=maximum;while(label.scrollWidth>label.clientWidth+.5&&size>7){size-=.25;label.style.fontSize=size+'px';}}}
window.addEventListener('resize',()=>{if(game==='grid')cgFitGridLabels();});
document.fonts?.ready.then(()=>{if(game==='grid')cgFitGridLabels();});
$('cgGrid').addEventListener('click',e=>{const b=e.target.closest('[data-grid-cell]');if(!b||b.disabled||game!=='grid')return;cgCell=Number(b.dataset.gridCell);renderSweaterGrid(S.grid.target,S.grid);$('cgGridGuess').value='';$('cgGridGuess').focus();});
$('cgGridReveal').onclick=()=>{if(game==='grid')doGuess('END');};

function renderBenchBoss(t,st,animateBudget=false){
  const state=COMMUNITY_MODEL.boss(t,st.guesses,COMMUNITY_DATA),saved=Array.isArray(st.opts?.lineup)?st.opts.lineup:[];
  let ids=st.over&&st.guesses[0]!=='END'?state.ids:saved;
  try{COMMUNITY_MODEL.draft(t,ids,COMMUNITY_DATA);}catch{ids=[];st.opts={...st.opts,lineup:[]};}
  const selected=new Set(ids),draft=COMMUNITY_MODEL.draft(t,ids,COMMUNITY_DATA),cards=new Map(t.cards.map(c=>[c[0],c]));
  $('cgBossYear').textContent=`${t.year}–${t.year+1} NHL season`;
  $('cgBossRemaining').textContent=`$${t.budget-draft.cost} left`;
  cgBudget(draft.cost,t.budget,animateBudget);
  $('cgBossBudgetStatus').textContent=draft.cost===t.budget?'Budget filled — every dollar is in your lineup.':draft.cost>=80?'Getting close to the limit. Look for value in your remaining slots.':'Spend wisely. You can swap players before locking your lineup.';
  const slots=['F','F','F','D','D','G'],buckets={F:[],D:[],G:[]};for(const id of ids)buckets[COMMUNITY_MODEL.group(cards.get(id)[8])].push(id);
  $('cgBossLineup').innerHTML=slots.map((pos,i)=>{const id=buckets[pos].shift(),p=id&&cgPlayer(id);return `<button type="button" class="cg-lineup-slot${id?' is-picked':''}" style="--slot:${i}" data-boss-remove="${id||''}" aria-label="${p?`Remove ${esc(p.name)}`:`Empty ${pos} slot`}"${!id||st.over?' disabled':''}><small>${pos}</small>${p?cgIdentity(id,cards.get(id)[6])+`<b>${esc(p.name)}</b><span>$${cards.get(id)[1]}${st.over?` · ${cards.get(id)[2]} pts`:''}</span>`:'<span class="cg-slot-empty">Choose player</span>'}</button>`;}).join('');
  document.querySelectorAll('[data-boss-position]').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.bossPosition===cgPosition);});
  $('cgBossMarket').innerHTML=t.cards.filter(c=>COMMUNITY_MODEL.group(c[8])===cgPosition).map(c=>{
    const p=cgPlayer(c[0]),hit=selected.has(c[0]);let eligible=true;try{if(!hit)COMMUNITY_MODEL.draft(t,[...ids,c[0]],COMMUNITY_DATA);}catch{eligible=false;}
    return `<button type="button" class="cg-market-card${hit?' is-picked':''}" data-boss-player="${c[0]}" aria-pressed="${hit}" aria-label="${esc(p.name)}, ${esc(teamName(c[6]))}, $${c[1]}${hit?', selected':''}"${st.over||!eligible?' disabled':''}>${cgIdentity(c[0],c[6])}<span class="cg-card-copy"><b>${esc(p.name)}</b><small>${esc(teamName(c[6]))} · ${c[8]}</small>${st.over?`<em>${COMMUNITY_MODEL.group(c[8])==='G'?`${c[5]} wins`:`${c[3]} goals · ${c[4]} assists`} · ${c[2]} pts</em>`:''}</span><strong>$${c[1]}</strong></button>`;
  }).join('');
  $('cgBossLock').disabled=st.over||!draft.complete;$('cgBossLock').hidden=st.over;$('cgBossReveal').hidden=st.over;
  $('cgBossReveal').textContent=mode==='unlimited'?'Reveal best lineup':'Forfeit & reveal best lineup';
  $('cgBossFeedback').textContent=st.over?st.guesses[0]==='END'?'Run forfeited. Your draft was not scored; the best lineup is shown below.':`${state.points} season points. Best possible: ${t.par}. ${state.perfect?'You found an optimal lineup.':'The best lineup is shown below.'}`:`${ids.length} / 6 slots filled · statistics reveal when you lock your lineup`;
  $('cgBossOptimal').hidden=!st.over;
  if(st.over)$('cgBossOptimal').innerHTML=`<h3>Best ${t.year}–${t.year+1} lineup · ${t.par} season points</h3><div class="cg-optimal-list">${t.optimal.map(id=>{const p=cgPlayer(id),c=cards.get(id);return `<div>${cgIdentity(id,c[6])}<span class="cg-card-copy"><b>${esc(p.name)}</b><small>${c[8]} · $${c[1]} · ${esc(teamName(c[6]))}</small></span><strong>${c[2]} pts</strong></div>`;}).join('')}</div>`;
}
function cgDraftToggle(id){
  const st=S.benchboss;if(game!=='benchboss'||st.over)return;
  const ids=(st.opts.lineup||[]).slice(),at=ids.indexOf(id);if(at>=0)ids.splice(at,1);else ids.push(id);
  const before=new Map([...$('cgBossLineup').querySelectorAll('[data-boss-remove]')].filter(b=>b.dataset.bossRemove).map(b=>[Number(b.dataset.bossRemove),b.getBoundingClientRect()]));
  const source=document.querySelector(`${at>=0?'#cgBossLineup [data-boss-remove':'#cgBossMarket [data-boss-player'}="${id}"] .cg-player-media`)?.cloneNode(true),sourceBox=document.querySelector(`${at>=0?'#cgBossLineup [data-boss-remove':'#cgBossMarket [data-boss-player'}="${id}"] .cg-player-media`)?.getBoundingClientRect();
  try{COMMUNITY_MODEL.draft(st.target,ids,COMMUNITY_DATA);st.opts={...st.opts,lineup:ids};saveProgress();renderBenchBoss(st.target,st,true);
    for(const b of $('cgBossLineup').querySelectorAll('[data-boss-remove]')){const old=before.get(Number(b.dataset.bossRemove));if(old){const rect=b.getBoundingClientRect();cgAnimate(b,[{transform:`translate(${old.x-rect.x}px,${old.y-rect.y}px)`},{transform:'none'}]);}}
    const destination=document.querySelector(`${at>=0?'#cgBossMarket [data-boss-player':'#cgBossLineup [data-boss-remove'}="${id}"] .cg-player-media`);
    if(source&&sourceBox){source.getBoundingClientRect=()=>sourceBox;cgFly(source,destination);}cgAnimate(destination?.closest('button'),[{backgroundColor:'color-mix(in srgb,var(--accent) 18%,var(--cell))'},{backgroundColor:'color-mix(in srgb,var(--accent) 7%,var(--cell))'}]);
    const focus=$('cgBossMarket').querySelector(`[data-boss-player="${id}"]:not(:disabled)`)||document.querySelector(`[data-boss-position="${cgPosition}"]`);focus?.focus({preventScroll:true});}catch(e){toast(e.message);}
}
$('cgBossMarket').addEventListener('click',e=>{const b=e.target.closest('[data-boss-player]');if(b&&!b.disabled)cgDraftToggle(Number(b.dataset.bossPlayer));});
$('cgBossLineup').addEventListener('click',e=>{const b=e.target.closest('[data-boss-remove]');if(b&&!b.disabled)cgDraftToggle(Number(b.dataset.bossRemove));});
document.querySelectorAll('[data-boss-position]').forEach(b=>b.onclick=()=>{if(game!=='benchboss')return;cgPosition=b.dataset.bossPosition;renderBenchBoss(S.benchboss.target,S.benchboss);});
$('cgBossLock').onclick=()=>{if(game==='benchboss')doGuess('LOCK:'+(S.benchboss.opts.lineup||[]).join(','));};
$('cgBossReveal').onclick=()=>{if(game!=='benchboss'||S.benchboss.over)return;if(mode==='unlimited')return doGuess('END');cgForfeit={target:S.benchboss.target,mode,day:S.benchboss.day};$('cgBossForfeit').showModal();$('cgBossKeep').focus();};
$('cgBossKeep').onclick=()=>{cgForfeit=null;$('cgBossForfeit').close();};
$('cgBossForfeit').addEventListener('cancel',()=>{cgForfeit=null;});
$('cgBossConfirm').onclick=()=>{const pending=cgForfeit;cgForfeit=null;$('cgBossForfeit').close();if(pending&&game==='benchboss'&&!S.benchboss.over&&S.benchboss.target===pending.target&&mode===pending.mode&&S.benchboss.day===pending.day)doGuess('END');};

function cgTrailPath(path){
  return path.map((id,i)=>{const p=cgPlayer(id),proof=i?COMMUNITY_MODEL.link(COMMUNITY_DATA,path[i-1],id):null;return `${proof?`<span class="cg-trail-link"><span class="cg-crest">${cgTeam(proof.team)}</span><small>${cgSeason(proof.year)}</small><span aria-hidden="true">→</span></span>`:''}<div class="cg-trail-person">${cgPhoto(id)}<b>${esc(p.name)}</b></div>`;}).join('');
}
function cgDragCancel(){if(!cgDrag)return;const drag=cgDrag;cgDrag=null;drag.events.abort();cancelAnimationFrame(drag.scroll);drag.ghost?.remove();try{drag.button.releasePointerCapture(drag.pointer);}catch{}$('cgTrailPath').classList.remove('is-dragging','is-over');}
function cgTrailAdd(id,source){if(game!=='teammatetrail'||S.teammatetrail.over)return;const old=S.teammatetrail.guesses.length,media=source?.querySelector('img'),copy=media?.cloneNode(true),box=media?.getBoundingClientRect();doGuess('ADD:'+id);if(S.teammatetrail.guesses.length===old)return;const node=$('cgTrailPath').querySelector(`[data-route-player="${id}"]`),rect=node?.getBoundingClientRect();if(rect&&(rect.top<0||rect.bottom>innerHeight))node.scrollIntoView({block:'nearest',behavior:'auto'});if(copy&&box){copy.getBoundingClientRect=()=>box;cgFly(copy,node?.querySelector('img'));}cgAnimate(node,[{opacity:.5,transform:'translateY(5px)'},{opacity:1,transform:'none'}]);}
function cgDragBegin(e){const button=e.target.closest('[data-trail-player]');if(!button||button.disabled||game!=='teammatetrail'||e.button!==0||(e.pointerType==='touch'&&!e.target.closest('.cg-drag-handle')))return;
  cgDragCancel();const st=S.teammatetrail,state=COMMUNITY_MODEL.trail(st.target,st.guesses,COMMUNITY_DATA),r=state.rounds[state.current],events=new AbortController();
  const drag=cgDrag={button,pointer:e.pointerId,id:Number(button.dataset.trailPlayer),x:e.clientX,y:e.clientY,lastX:e.clientX,lastY:e.clientY,target:st.target,mode,day:st.day,round:state.current,path:r.path.join(','),events,ghost:null,scroll:0};button.setPointerCapture(e.pointerId);
  const live=()=>cgDrag===drag&&game==='teammatetrail'&&!S.teammatetrail.over&&S.teammatetrail.target===drag.target&&mode===drag.mode&&S.teammatetrail.day===drag.day;
  const scroll=()=>{if(!live()||!drag.ghost)return;const over=!!document.elementFromPoint(drag.lastX,drag.lastY)?.closest('[data-trail-drop]');const dy=over?0:drag.lastY<70?-10:drag.lastY>innerHeight-70?10:0;if(dy)window.scrollBy(0,dy);$('cgTrailPath').classList.toggle('is-over',over);drag.scroll=requestAnimationFrame(scroll);};
  window.addEventListener('pointermove',event=>{if(event.pointerId!==drag.pointer||!live())return;if(!drag.ghost&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<7)return;event.preventDefault();
    if(!drag.ghost){const box=button.getBoundingClientRect();drag.ghost=button.cloneNode(true);drag.ghost.className='cg-teammate-choice cg-drag-player';drag.ghost.removeAttribute('data-trail-player');drag.ghost.setAttribute('aria-hidden','true');drag.ghost.style.cssText=`position:fixed;width:${Math.min(box.width,250)}px;pointer-events:none;z-index:90;`;document.body.append(drag.ghost);$('cgTrailPath').classList.add('is-dragging');drag.scroll=requestAnimationFrame(scroll);}
    drag.lastX=event.clientX;drag.lastY=event.clientY;drag.ghost.style.left=`${event.clientX-35}px`;drag.ghost.style.top=`${event.clientY-30}px`;$('cgTrailPath').classList.toggle('is-over',!!document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-trail-drop]'));
  },{signal:events.signal,passive:false});
  window.addEventListener('pointerup',event=>{if(event.pointerId!==drag.pointer)return;const drop=drag.ghost&&document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-trail-drop]'),active=live(),moved=!!drag.ghost;const current=active?COMMUNITY_MODEL.trail(st.target,st.guesses,COMMUNITY_DATA):null;const matches=current&&current.current===drag.round&&current.rounds[current.current].path.join(',')===drag.path;cgDragCancel();if(moved){button.dataset.suppressClick='1';setTimeout(()=>delete button.dataset.suppressClick,0);}if(drop&&active&&matches)cgTrailAdd(drag.id,button);},{signal:events.signal});
  window.addEventListener('pointercancel',()=>cgDragCancel(),{signal:events.signal});
}
function cgTrailBoard(q,r){
  const path=r.done&&!r.won?q.solution:r.path,finished=path.at(-1)===q.end,bridges=path.slice(1,finished?-1:undefined),required=q.solution.length-2,slots=Math.min(q.solution.length-1,Math.max(required,bridges.length+(r.done?0:1)));
  const stop=(id,label,cls='',proof=null)=>`<li class="cg-trail-stop ${cls}"${id?` data-route-player="${id}"`:''}><span class="cg-stop-label">${esc(label)}</span>${id?`<div class="cg-stop-player">${cgPhoto(id)}<b>${esc(cgPlayer(id).name)}</b></div>`:`<button class="cg-trail-drop${cls.includes('is-next')?' is-next':''}" type="button"${cls.includes('is-next')?' data-trail-drop aria-label="Add next teammate: drag a card here or tap a player below"':' disabled'}><span aria-hidden="true">+</span><b>${cls.includes('is-next')?'Add teammate':'Next stop'}</b><small>${cls.includes('is-next')?'Drag here or tap a card':'Build your trail'}</small></button>`}${proof?`<span class="cg-stop-proof"><span class="cg-crest">${cgTeam(proof.team)}</span><span>Teammates<br><b>${esc(teamName(proof.team))} · ${cgSeason(proof.year)}</b></span></span>`:''}</li>`;
  let nodes=stop(q.start,'Start','is-connected');
  for(let i=0;i<slots;i++){const id=bridges[i];nodes+=stop(id,i<required?`Teammate ${i+1}`:'Extra teammate',id?'is-connected':i===bridges.length&&!r.done?'is-next':'is-waiting',id?COMMUNITY_MODEL.link(COMMUNITY_DATA,i?bridges[i-1]:q.start,id):null);}
  nodes+=stop(q.end,finished?'Connected':'Finish',finished?'is-connected':'is-destination',finished?COMMUNITY_MODEL.link(COMMUNITY_DATA,path.at(-2),q.end):null);
  return `<svg class="cg-route-line" viewBox="0 0 1000 80" preserveAspectRatio="none" aria-hidden="true"><path d="M70 40 Q180 6 290 40 T510 40 T730 40 T950 40"/></svg><ol class="cg-trail-track" style="--stops:${slots+2}">${nodes}</ol>`;
}
function cgTrailOptions(t,state){
  const r=state.rounds[state.current],q=t.rounds[state.current],key=`${t.id}:${state.current}:${r.path.join(',')}`;
  if(cgChoiceKey===key)return cgChoices;
  const current=r.path.at(-1),available=COMMUNITY_MODEL.teammates(COMMUNITY_DATA,current).filter(id=>!r.path.includes(id)&&id!==q.end);
  const best=COMMUNITY_MODEL.shortest(COMMUNITY_DATA,current,q.end,r.path.slice(0,-1));
  cgChoices=shuffled([...(best&&best.length>2?[best[1]]:[]),...shuffled(available.filter(id=>id!==best?.[1])).slice(0,3)]);
  cgChoiceKey=key;return cgChoices;
}
function renderTeammateTrail(t,st){
  const state=COMMUNITY_MODEL.trail(t,st.guesses,COMMUNITY_DATA),r=state.rounds[state.current],q=t.rounds[state.current],current=r.path.at(-1),limit=q.solution.length-1;
  const full=r.path.length-1>=limit;cgDragCancel();cgClearSearch('cgTrailGuess','cgTrailOpts');
  paintQuestionProgress('cgTrailDots',3,st.over?-1:state.current,state.rounds.map(r=>r.done?{status:r.won?'ok':'bad'}:null));
  $('cgTrailRound').textContent=`Trail ${state.current+1} / 3`;$('cgTrailScore').textContent=`${state.score} / 30 points`;
  $('cgTrailGoal').innerHTML=`<span class="cg-eyebrow">Find the teammate connection</span><h2>${esc(cgPlayer(q.start).name)} <span aria-hidden="true">→</span> ${esc(cgPlayer(q.end).name)}</h2><p>${r.done?'Your connections are shown on the trail below.':`Build the trail with ${q.solution.length-2} connecting ${q.solution.length===3?'player':'players'}. Drag a card into the highlighted stop, or tap to add.`}</p>`;
  $('cgTrailPath').innerHTML=cgTrailBoard(q,r);
  $('cgTrailSearch').hidden=r.done||full;$('cgTrailGuess').disabled=r.done||full;
  $('cgTrailPrompt').textContent=r.done?'':full?'Undo a step or use the hint to make room for another teammate.':`Choose a teammate of ${cgPlayer(current).name}`;
  $('cgTrailChoices').innerHTML=r.done||full?'':cgTrailOptions(t,state).map(id=>{const proof=COMMUNITY_MODEL.link(COMMUNITY_DATA,current,id);return `<button type="button" class="cg-teammate-choice" data-trail-player="${id}" aria-label="Add ${esc(cgPlayer(id).name)} to your trail">${cgPhoto(id)}<span><b>${esc(cgPlayer(id).name)}</b><small>${esc(teamName(proof.team))} · ${cgSeason(proof.year)}</small></span><span class="cg-drag-handle" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></span></button>`;}).join('');
  $('cgTrailChoices').hidden=r.done||full;
  $('cgTrailUndo').disabled=r.done||r.path.length<=(r.hinted?2:1);$('cgTrailUndo').hidden=r.done;
  $('cgTrailHint').disabled=r.hinted||r.done;$('cgTrailHint').hidden=r.done;
  $('cgTrailReveal').hidden=r.done;$('cgTrailNext').hidden=!r.done||st.over;
  $('cgTrailFeedback').textContent=r.done?r.won?`${r.points} points. ${r.points===10?'Shortest route, first try.':'Connection found.'}`:'One verified route is shown above.':`${r.path.length-1} ${r.path.length===2?'teammate':'teammates'} added · shortest route needs ${q.solution.length-2}. One extra teammate is allowed; Undo or a hint caps this trail at 6 points.`;
}
$('cgTrailChoices').addEventListener('pointerdown',cgDragBegin);
$('cgTrailChoices').addEventListener('click',e=>{const b=e.target.closest('[data-trail-player]');if(b&&game==='teammatetrail'&&!b.dataset.suppressClick)cgTrailAdd(Number(b.dataset.trailPlayer),b);});
$('cgTrailPath').addEventListener('click',e=>{if(e.target.closest('[data-trail-drop]'))$('cgTrailChoices').querySelector('button')?.focus();});
window.addEventListener('blur',cgDragCancel);document.addEventListener('visibilitychange',()=>{if(document.hidden)cgDragCancel();});
for(const [id,action] of [['cgTrailUndo','UNDO'],['cgTrailHint','HINT'],['cgTrailReveal','REVEAL'],['cgTrailNext','NEXT']])$(id).onclick=()=>{if(game==='teammatetrail')doGuess(action);};

function cgSearchPlayers(mode){
  if(mode==='grid')return cgGridPlayers ||= [...COMMUNITY_MODEL.index(COMMUNITY_DATA).players.values()].sort((a,b)=>b.gp-a.gp);
  const st=S.teammatetrail;if(!st.target)return [];
  const state=COMMUNITY_MODEL.trail(st.target,st.guesses,COMMUNITY_DATA),r=state.rounds[state.current],q=st.target.rounds[state.current];
  return COMMUNITY_MODEL.teammates(COMMUNITY_DATA,r.path.at(-1)).filter(id=>!r.path.includes(id)&&id!==q.end).map(cgPlayer).sort((a,b)=>b.gp-a.gp);
}
function cgSearchChoose(mode,p){if(game!==mode||S[mode].over)return;if(mode==='grid')doGuess(`${cgCell}:${p.id}`);else doGuess(`ADD:${p.id}`);}
