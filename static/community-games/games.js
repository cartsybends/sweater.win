const COMMUNITY_DATA = /*__COMMUNITY_DATA__*/{};
const cgPlayer = id => COMMUNITY_MODEL.index(COMMUNITY_DATA).players.get(id);
const cgPhoto = (id, cls = '') => `<img class="${cls}" src="https://assets.nhle.com/mugs/nhl/latest/${id}.png" alt="" decoding="async" onerror="this.onerror=null;this.src=FALLBACK">`;
const cgTeam = team => `<img src="${logo(team)}" alt="${esc(teamName(team))}">`;
const cgSeason = year => `${year}–${String(year+1).slice(-2)}`;
const cgSearchMeta = p => `${p.pos} · born ${p.birthYear} · ${p.gp.toLocaleString()} career GP`;
const cgState = (id,t,guesses) => COMMUNITY_MODEL[id==='teammatetrail'?'trail':id==='benchboss'?'boss':'grid'](t,guesses,COMMUNITY_DATA);
let cgCell = 0, cgPosition = 'F', cgChoiceKey = '', cgChoices = [];
let cgGridPlayers;
function cgClearSearch(inputId,listId){$(inputId).value='';$(inputId).setAttribute('aria-expanded','false');$(listId).hidden=true;}

for(const [id,title,next] of [['grid','Sweater Grid','Next grid'],['benchboss','Bench Boss','Next market'],['teammatetrail','Teammate Trail','Next trails']]){
  G[id]={kind:'score',repeat:id==='teammatetrail',title,share:`Sweater ${title}`,view:`view-${id}`,max:id==='grid'?12:id==='benchboss'?1:100,
    next,hideReveal:true,quietFinish:true,persistUnlimited:true,
    pool:()=>COMMUNITY_DATA[id]||[],
    daily(k){const ref=DAILY[id]?.[k];return this.pool().find(t=>t.id===ref?.id)||this.pool()[hash(`sweater-${id}-${k}`)%this.pool().length];},
    random(){return pick(this.pool());},tid:t=>t.id,player:()=>null,meta:()=>'',reset(){cgCell=0;cgPosition='F';cgChoiceKey='';cgChoices=[];},
    guess(t,x,fresh){try{return cgState(id,t,[...S[id].guesses,x]).won;}catch(e){if(fresh)toast(e.message);return null;}},
    right(t,x,i){if(id==='grid'&&x!=='END')return cgState(id,t,S[id].guesses.slice(0,i+1)).last?.correct;if(id==='teammatetrail'&&String(x).startsWith('ADD:'))return true;},
    isDone:(t,g)=>cgState(id,t,g).over,wonGame:(t,g)=>cgState(id,t,g).won,score:(t,g)=>cgState(id,t,g).score,
    archiveStatus:h=>`${h.s} pts`,celebrate:(t,g,won)=>won,
    onFinish(st){const score=this.score(st.target,st.guesses),key=`sweater-${id}-best`;store.set(key,Math.max(score,Number(store.get(key))||0));},
    endText(t,g){const state=cgState(id,t,g);return id==='grid'?{result:state.won?'Grid complete':`${state.used.size} of 9 filled`,cheer:`${state.score} points · ${state.won?'Every connection found':'See the remaining connections below'}`}:
      id==='benchboss'?{result:state.perfect?'Perfect lineup':state.won?'Strong lineup':'Lineup revealed',cheer:`${state.score}/10 · ${state.points} season points · best possible ${t.par}`}:
      {result:`${state.rounds.filter(r=>r.won).length} of 3 trails connected`,cheer:`${state.score}/30 points · each link backed by NHL appearances`};},
    shareText(t,saved,num,link){const state=cgState(id,t,saved.guesses),marks=id==='grid'?[0,3,6].map(i=>state.cells.slice(i,i+3).map(x=>x?'🟩':'⬛').join('')).join('\n'):id==='teammatetrail'?state.rounds.map(r=>r.won?'🟩':'⬛').join(''):'🏒';return `Sweater ${title} #${num}\n${marks}\n${state.score}${id==='benchboss'?'/10':id==='teammatetrail'?'/30':' points'}${link}`;},
    render(t,st){if(id==='grid')renderSweaterGrid(t,st);else if(id==='benchboss')renderBenchBoss(t,st);else renderTeammateTrail(t,st);},
  };
}

function cgClue(clue){
  return clue.kind==='team'?`<span class="cg-crest">${cgTeam(clue.value)}</span><b>${esc(teamName(clue.value))}</b>`:
    `<b>${clue.kind==='country'?`Born in ${esc(countryName(clue.value))}`:clue.kind==='position'?{F:'Forward',D:'Defenseman',G:'Goalie'}[clue.value]:clue.kind==='games'?`${clue.value.toLocaleString()}+ career GP`:'Hall of Famer'}</b>`;
}
function renderSweaterGrid(t,st){
  const state=COMMUNITY_MODEL.grid(t,st.guesses,COMMUNITY_DATA),display=st.over?COMMUNITY_MODEL.fillGrid(t,state,COMMUNITY_DATA):state.cells;
  cgClearSearch('cgGridGuess','cgGridOpts');
  if(state.cells[cgCell]!==null)cgCell=state.cells.findIndex(id=>id===null);
  $('cgGrid').innerHTML='<div class="cg-corner" aria-hidden="true"></div>'+t.cols.map(c=>`<div class="cg-grid-heading">${cgClue(c)}</div>`).join('')+t.rows.map((team,row)=>
    `<div class="cg-grid-heading">${cgClue({kind:'team',value:team})}</div>`+t.cols.map((clue,col)=>{
      const cell=row*3+col,id=display[cell],p=id&&cgPlayer(id),filled=state.cells[cell]!==null;
      return `<button type="button" class="cg-square${filled?' is-filled':id?' is-revealed':''}${cgCell===cell&&!st.over?' is-active':''}" data-grid-cell="${cell}" aria-label="${esc(`${teamName(team)} · ${cgClue(clue).replace(/<[^>]*>/g,'')} ${p?': '+p.name:': choose a player'}`)}" aria-pressed="${cgCell===cell&&!st.over}"${filled||st.over?' disabled':''}>${p?cgPhoto(id)+`<b>${esc(p.name)}</b>${filled?`<small>+${10+COMMUNITY_MODEL.bonus(t,cell,p)}</small>`:'<small>One possible answer</small>'}`:'<span aria-hidden="true">+</span><small>Choose player</small>'}</button>`;
    }).join('')).join('');
  $('cgGridScore').textContent=`${state.used.size} / 9 filled · ${state.score} points`;
  $('cgGridTries').textContent=st.over?'':`${12-state.tried.size} guesses left`;
  $('cgGridSearch').hidden=st.over;
  $('cgGridGuess').disabled=st.over;
  $('cgGridPrompt').textContent=st.over?'':`${teamName(t.rows[Math.floor(cgCell/3)])} · ${cgClue(t.cols[cgCell%3]).replace(/<[^>]*>/g,'')}`;
  const last=state.last;
  $('cgGridFeedback').textContent=st.over?'Highlighted answers are yours; muted cards show other valid connections.':last?last.correct?`${cgPlayer(last.id).name} fits. +${10+COMMUNITY_MODEL.bonus(t,last.cell,cgPlayer(last.id))} points.`:`${cgPlayer(last.id).name} doesn’t match that square. Try another connection.`:'Select a square, then search for a player.';
  $('cgGridReveal').hidden=st.over;
}
$('cgGrid').addEventListener('click',e=>{const b=e.target.closest('[data-grid-cell]');if(!b||b.disabled||game!=='grid')return;cgCell=Number(b.dataset.gridCell);renderSweaterGrid(S.grid.target,S.grid);$('cgGridGuess').value='';$('cgGridGuess').focus();});
$('cgGridReveal').onclick=()=>{if(game==='grid')doGuess('END');};

function renderBenchBoss(t,st){
  const state=COMMUNITY_MODEL.boss(t,st.guesses,COMMUNITY_DATA),saved=Array.isArray(st.opts?.lineup)?st.opts.lineup:[];
  let ids=st.over?state.ids:saved;
  try{COMMUNITY_MODEL.draft(t,ids,COMMUNITY_DATA);}catch{ids=[];st.opts={...st.opts,lineup:[]};}
  const selected=new Set(ids),draft=COMMUNITY_MODEL.draft(t,ids,COMMUNITY_DATA),cards=new Map(t.cards.map(c=>[c[0],c]));
  $('cgBossYear').textContent=cgSeason(t.year)+' NHL season';
  $('cgBossBudget').textContent=`${draft.cost} / ${t.budget} credits`;
  $('cgBossRemaining').textContent=st.over?'':` · ${t.budget-draft.cost} credits remaining`;
  $('cgBossBudgetBar').style.width=`${draft.cost/t.budget*100}%`;
  const slots=['F','F','F','D','D','G'],buckets={F:[],D:[],G:[]};for(const id of ids)buckets[COMMUNITY_MODEL.group(cards.get(id)[8])].push(id);
  $('cgBossLineup').innerHTML=slots.map((pos,i)=>{const id=buckets[pos].shift(),p=id&&cgPlayer(id);return `<button type="button" class="cg-lineup-slot${id?' is-picked':''}" style="--slot:${i}" data-boss-remove="${id||''}" aria-label="${p?`Remove ${esc(p.name)}`:`Empty ${pos} slot`}"${!id||st.over?' disabled':''}><small>${pos}</small>${p?cgPhoto(id)+`<b>${esc(p.name)}</b><span>${cards.get(id)[1]} cr${st.over?` · ${cards.get(id)[2]} pts`:''}</span>`:'<span class="cg-slot-empty">Choose player</span>'}</button>`;}).join('');
  document.querySelectorAll('[data-boss-position]').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.bossPosition===cgPosition);});
  $('cgBossMarket').innerHTML=t.cards.filter(c=>COMMUNITY_MODEL.group(c[8])===cgPosition).map(c=>{
    const p=cgPlayer(c[0]),hit=selected.has(c[0]);let eligible=true;try{if(!hit)COMMUNITY_MODEL.draft(t,[...ids,c[0]],COMMUNITY_DATA);}catch{eligible=false;}
    return `<button type="button" class="cg-market-card${hit?' is-picked':''}" data-boss-player="${c[0]}" aria-pressed="${hit}" aria-label="${esc(p.name)}, ${c[1]} credits${hit?', selected':''}"${st.over||!eligible?' disabled':''}>${cgPhoto(c[0])}<span><b>${esc(p.name)}</b><small>${esc(teamName(c[6]))} · ${c[8]}</small>${st.over?`<em>${COMMUNITY_MODEL.group(c[8])==='G'?`${c[5]} wins`:`${c[3]} goals · ${c[4]} assists`} · ${c[2]} pts</em>`:''}</span><strong>${c[1]}<small>cr</small></strong></button>`;
  }).join('');
  $('cgBossLock').disabled=st.over||!draft.complete;$('cgBossLock').hidden=st.over;$('cgBossReveal').hidden=st.over;
  $('cgBossFeedback').textContent=st.over?`${state.points} season points. Best possible: ${t.par}. ${state.perfect?'You found an optimal lineup.':'The best lineup is shown below.'}`:`${ids.length} / 6 slots filled · statistics reveal when you lock your lineup`;
  $('cgBossOptimal').hidden=!st.over;
  if(st.over)$('cgBossOptimal').innerHTML=`<h3>Best lineup · ${t.par} season points</h3><div class="cg-optimal-list">${t.optimal.map(id=>{const p=cgPlayer(id),c=cards.get(id);return `<div>${cgPhoto(id)}<span><b>${esc(p.name)}</b><small>${c[8]} · ${c[1]} credits</small></span><strong>${c[2]} pts</strong></div>`;}).join('')}</div>`;
}
function cgDraftToggle(id){
  const st=S.benchboss;if(game!=='benchboss'||st.over)return;
  const ids=(st.opts.lineup||[]).slice(),at=ids.indexOf(id);if(at>=0)ids.splice(at,1);else ids.push(id);
  try{COMMUNITY_MODEL.draft(st.target,ids,COMMUNITY_DATA);st.opts={...st.opts,lineup:ids};saveProgress();renderBenchBoss(st.target,st);const focus=$('cgBossMarket').querySelector(`[data-boss-player="${id}"]:not(:disabled)`)||document.querySelector(`[data-boss-position="${cgPosition}"]`);focus?.focus({preventScroll:true});}catch(e){toast(e.message);}
}
$('cgBossMarket').addEventListener('click',e=>{const b=e.target.closest('[data-boss-player]');if(b&&!b.disabled)cgDraftToggle(Number(b.dataset.bossPlayer));});
$('cgBossLineup').addEventListener('click',e=>{const b=e.target.closest('[data-boss-remove]');if(b&&!b.disabled)cgDraftToggle(Number(b.dataset.bossRemove));});
document.querySelectorAll('[data-boss-position]').forEach(b=>b.onclick=()=>{if(game!=='benchboss')return;cgPosition=b.dataset.bossPosition;renderBenchBoss(S.benchboss.target,S.benchboss);});
$('cgBossLock').onclick=()=>{if(game==='benchboss')doGuess('LOCK:'+(S.benchboss.opts.lineup||[]).join(','));};
$('cgBossReveal').onclick=()=>{if(game==='benchboss')doGuess('END');};

function cgTrailPath(path){
  return path.map((id,i)=>{const p=cgPlayer(id),proof=i?COMMUNITY_MODEL.link(COMMUNITY_DATA,path[i-1],id):null;return `${proof?`<span class="cg-trail-link"><span class="cg-crest">${cgTeam(proof.team)}</span><small>${cgSeason(proof.year)}</small><span aria-hidden="true">→</span></span>`:''}<div class="cg-trail-person">${cgPhoto(id)}<b>${esc(p.name)}</b></div>`;}).join('');
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
  const full=r.path.length-1>=limit;cgClearSearch('cgTrailGuess','cgTrailOpts');
  paintQuestionProgress('cgTrailDots',3,st.over?-1:state.current,state.rounds.map(r=>r.done?{status:r.won?'ok':'bad'}:null));
  $('cgTrailRound').textContent=`Trail ${state.current+1} / 3`;$('cgTrailScore').textContent=`${state.score} / 30 points`;
  $('cgTrailGoal').innerHTML=`${cgPhoto(q.end)}<span><small>Connect to</small><b>${esc(cgPlayer(q.end).name)}</b></span>`;
  $('cgTrailPath').innerHTML=cgTrailPath(r.done&&!r.won?q.solution:r.path);
  $('cgTrailSearch').hidden=r.done||full;$('cgTrailGuess').disabled=r.done||full;
  $('cgTrailPrompt').textContent=r.done?'':full?'Undo a step or use the hint to make room for another teammate.':`Choose a teammate of ${cgPlayer(current).name}`;
  $('cgTrailChoices').innerHTML=r.done||full?'':cgTrailOptions(t,state).map(id=>`<button type="button" class="cg-teammate-choice" data-trail-player="${id}">${cgPhoto(id)}<span><b>${esc(cgPlayer(id).name)}</b><small>${cgPlayer(id).pos} · ${cgPlayer(id).gp.toLocaleString()} career GP</small></span></button>`).join('');
  $('cgTrailChoices').hidden=r.done||full;
  $('cgTrailUndo').disabled=r.done||r.path.length<=(r.hinted?2:1);$('cgTrailUndo').hidden=r.done;
  $('cgTrailHint').disabled=r.hinted||r.done;$('cgTrailHint').hidden=r.done;
  $('cgTrailReveal').hidden=r.done;$('cgTrailNext').hidden=!r.done||st.over;
  $('cgTrailFeedback').textContent=r.done?r.won?`${r.points} points. ${r.points===10?'Shortest route, first try.':'Connection found.'}`:'One verified route is shown above.':`${r.path.length-1} / ${limit} connecting players · shortest route uses ${q.solution.length-2} · Undo or hint caps this trail at 6 points`;
}
$('cgTrailChoices').addEventListener('click',e=>{const b=e.target.closest('[data-trail-player]');if(b&&game==='teammatetrail')doGuess('ADD:'+b.dataset.trailPlayer);});
for(const [id,action] of [['cgTrailUndo','UNDO'],['cgTrailHint','HINT'],['cgTrailReveal','REVEAL'],['cgTrailNext','NEXT']])$(id).onclick=()=>{if(game==='teammatetrail')doGuess(action);};

function cgSearchPlayers(mode){
  if(mode==='grid')return cgGridPlayers ||= [...COMMUNITY_MODEL.index(COMMUNITY_DATA).players.values()].sort((a,b)=>b.gp-a.gp);
  const st=S.teammatetrail;if(!st.target)return [];
  const state=COMMUNITY_MODEL.trail(st.target,st.guesses,COMMUNITY_DATA),r=state.rounds[state.current],q=st.target.rounds[state.current];
  return COMMUNITY_MODEL.teammates(COMMUNITY_DATA,r.path.at(-1)).filter(id=>!r.path.includes(id)&&id!==q.end).map(cgPlayer).sort((a,b)=>b.gp-a.gp);
}
function cgSearchChoose(mode,p){if(game!==mode||S[mode].over)return;if(mode==='grid')doGuess(`${cgCell}:${p.id}`);else doGuess(`ADD:${p.id}`);}
