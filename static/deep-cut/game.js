const DEEP_CUT_DATA = /*__DEEP_CUT_DATA__*/{};
const dcModel = DEEP_CUT_MODEL;
const dcIndex = () => dcModel.index(DEEP_CUT_DATA);
let dcTimer=0,dcFrame=0,dcAudio=null,dcAnimation=null,dcLastFrame=0,dcOffset=0,dcVisualDistance=0,dcBurstTimer=0,dcEffectTimer=0,dcZoneTimer=0;
let dcRinkParticles=[],dcRinkPointer=null,dcRinkLastPoint=null;
let dcCrowdWave=null;
const dcZones=['THE NEIGHBOURHOOD RINK','THE COMMUNITY ARENA','THE BIG LEAGUES','UP IN THE RAFTERS','LEGENDS ONLY'];
const dcZone=distance=>Math.max(0,Math.min(4,Math.floor(distance/1500)));
const dcAnimationLevel=score=>[10,15,30,60,85,100].indexOf(score)+1;
const dcReduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const dcActive=()=>game==='deepcut'&&!onHub&&!$('view-deepcut').hidden;
const dcSession=()=>S.deepcut.opts.dcRun;
const dcCurrentPrompt=()=>dcIndex().prompts.get(S.deepcut.target.prompts[S.deepcut.guesses.length]);
const dcSoundOn=()=>store.get('sweater-deepcut-sound')===true;
const dcCorrectionsOn=()=>store.get('sweater-deepcut-corrections')!==false;
const DC_CORRECTION_LABELS={name:'Name variant recognized',alias:'Nickname recognized',surname:'Surname recognized',spelling:'Spelling corrected',partial:'Partial name completed'};
function dcSoundPaint(){const b=$('dcSound'),on=dcSoundOn();b.textContent=on?'SOUND ON':'SOUND OFF';b.setAttribute('aria-pressed',String(on));b.setAttribute('aria-label',`Turn game sound ${on?'off':'on'}`);}
function dcCorrectionsPaint(){const on=dcCorrectionsOn();$('dcCorrections').checked=on;$('dcCorrectionsState').textContent=on?'ON':'OFF';$('dcCorrectionHelp').textContent=on?'Accepts common nicknames, unique surnames, and close spellings. Ambiguous names need more detail.':'Answer corrections are off. Enter an exact full name.';}
function dcPlay(score){
  if(!dcSoundOn()||!dcAudio)return;
  dcAudio.resume().catch(()=>{});
  const level=dcAnimationLevel(score),notes=score===100?[523.25,659.25,783.99,1046.5,1318.51,1567.98]:score===85?[440,554.37,659.25,880,1108.73]:score===60?[392,523.25,659.25,783.99]:score===30?[329.63,440,523.25]:score===15?[329.63,392,493.88]:score?[261.63,329.63]:[164.81,130.81];
  notes.forEach((frequency,i)=>{const at=dcAudio.currentTime+i*.085,o=dcAudio.createOscillator(),g=dcAudio.createGain();o.type=level>=5&&i%2?'square':'triangle';o.frequency.value=frequency;g.gain.setValueAtTime(0,at);g.gain.linearRampToValueAtTime(level>=5?.025:.035,at+.012);g.gain.exponentialRampToValueAtTime(.001,at+.22);o.connect(g);g.connect(dcAudio.destination);o.start(at);o.stop(at+.24);});
}
function dcEndEffects(){clearTimeout(dcBurstTimer);clearTimeout(dcEffectTimer);clearTimeout(dcZoneTimer);$('dcBurst').classList.remove('on');$('dcZoneAnnouncement').hidden=true;delete $('dcCabinet').dataset.celebration;if(dcAnimation)dcVisualDistance=dcAnimation.to;dcAnimation=null;}
function dcCleanup(){clearInterval(dcTimer);dcTimer=0;cancelAnimationFrame(dcFrame);dcFrame=0;dcEndEffects();dcClearRinkParticles();dcCrowdWave=null;$('dcWave').hidden=true;$('dcWaveStatus').textContent='';document.body?.classList.remove('dc-immersive');}

// Old arena scoreboards light individual seven-segment LEDs, including tenths.
const DC_LED_SEGMENTS={a:'M6 2H26L30 6 26 10H6L2 6Z',b:'M27 11 31 7V27L27 31 23 27V15Z',c:'M27 33 31 37V55L27 59 23 55V37Z',d:'M6 56H22L26 60 22 64H6L2 60Z',e:'M1 37 5 33 9 37V55L5 59 1 55Z',f:'M1 7 5 11 9 15V27L5 31 1 27Z',g:'M7 29H23L27 33 23 37H7L3 33Z'};
const DC_LED_CODES=['abcdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg'];
function dcClockMarkup(){
  const digit=()=>`<svg class="dc-led" viewBox="0 0 32 66" data-clock-digit aria-hidden="true">${Object.entries(DC_LED_SEGMENTS).map(([key,path])=>`<path d="${path}" data-segment="${key}"/>`).join('')}</svg>`;
  return `<div class="dc-jumbotron" id="dcJumbotron" role="timer" aria-live="off" aria-label="Arena clock"><div class="dc-clock-row"><span id="dcClockLabel">GET READY</span><span>TIME REMAINING</span></div><div class="dc-clock-digits" aria-hidden="true">${digit()}<i class="dc-led-colon"></i>${digit()}${digit()}<i class="dc-led-point"></i>${digit()}</div><strong class="dc-sr-only" id="dcClockText">3 seconds</strong><div class="dc-clock" id="dcClock"><i id="dcClockFill"></i></div></div>`;
}
function dcPaintClock(milliseconds,preview){
  const tenths=Math.max(0,Math.ceil(milliseconds/100)),seconds=Math.floor(tenths/10),text=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}.${tenths%10}`;
  $('dcClockText').textContent=text;
  const clock=$('dcJumbotron');if(!clock)return;
  clock.setAttribute('aria-label',`${preview?'Get ready':'Time remaining'}: ${text}`);
  clock.classList.toggle('is-urgent',!preview&&milliseconds<=5000);clock.classList.toggle('is-preview',preview);
  const digits=text.replace(/\D/g,'');clock.querySelectorAll('[data-clock-digit]').forEach((el,i)=>{
    if(el.dataset.value===digits[i])return;el.dataset.value=digits[i];
    el.querySelectorAll('[data-segment]').forEach(segment=>segment.classList.toggle('is-lit',DC_LED_CODES[Number(digits[i])].includes(segment.dataset.segment)));
  });
}

G.deepcut={
  kind:'score',repeat:true,title:'Deep Cut',share:'Sweater Deep Cut',view:'view-deepcut',max:7,
  next:'Another shift',hideReveal:true,quietFinish:true,persistUnlimited:true,
  pool:()=>DEEP_CUT_DATA.runs,
  daily(day){return dcIndex().runs.get(DAILY.deepcut?.[day]?.id)||this.pool()[hash(`sweater-deepcut-${day}`)%this.pool().length];},
  random(){return pick(this.pool());},tid:t=>t.id,player:()=>null,meta:()=>'',
  prepareTarget(t,opts){const s=opts.dcRun;if(s?.target!==t.id||!['ready','preview','ask','reveal'].includes(s.phase)||!Number.isInteger(s.index)||s.index<0||s.index>7||['preview','ask'].includes(s.phase)&&(!Number.isFinite(s.deadline)||!Number.isFinite(s.previewUntil)))opts.dcRun={target:t.id,index:0,phase:'ready'};return t;},
  reset(){dcCleanup();dcSoundPaint();dcCorrectionsPaint();},
  guess(t,x){try{return dcModel.state(t,[...S.deepcut.guesses,x],DEEP_CUT_DATA).won;}catch{return null;}},
  right:(t,x)=>x!=='MISS',
  isDone:(t,g)=>dcModel.state(t,g,DEEP_CUT_DATA).over,
  wonGame:(t,g)=>dcModel.state(t,g,DEEP_CUT_DATA).won,
  score:(t,g)=>dcModel.state(t,g,DEEP_CUT_DATA).score,
  archiveStatus:h=>`${h.s}/700 pts`,celebrate:(t,g)=>dcModel.state(t,g,DEEP_CUT_DATA).score>=450,
  endText(t,g){const s=dcModel.state(t,g,DEEP_CUT_DATA);return {result:dcModel.rank(s.score),cheer:`${s.score}/700 points · ${s.distance.toLocaleString()} metres skated`};},
  shareText(t,saved,num,link){const s=dcModel.state(t,saved.guesses,DEEP_CUT_DATA);return `Sweater Deep Cut #${num}\n${s.rounds.map(r=>r.tier.mark).join('')}\n${s.score}/700 · ${s.distance.toLocaleString()} m\n${dcModel.rank(s.score)}${link}`;},
  render:dcRender,
};

function dcHud(state){
  $('dcPoints').textContent=String(state.score).padStart(3,'0');$('dcDistance').textContent=state.distance.toLocaleString();
  const session=dcSession();
  $('dcDots').innerHTML=Array.from({length:7},(_,i)=>{const r=state.rounds[i],current=!state.over&&i===state.rounds.length&&['preview','ask'].includes(session.phase),label=r?`Round ${i+1}: ${r.score} points, ${r.tier.name}`:`Round ${i+1}${current?': current prompt':': not played'}`;return `<i class="dc-puck${current?' is-current':''}${r?' is-complete':''}${r&&!r.score?' is-missed':''}"${r?` style="--puck-color:${r.tier.color}"`:''} role="img" title="${label}" aria-label="${label}"></i>`;}).join('');
  $('dcTrackFill').style.width=`${state.distance/7000*100}%`;$('dcTrack').setAttribute('aria-valuenow',state.distance);
  const zone=dcZone(state.distance);
  $('dcArenaTag').textContent=`0${zone+1} / ${dcZones[zone]}`;
  $('dcNextZone').textContent=zone<4?`NEXT STOP · ${(zone+1)*150} POINTS`:'THE TOP OF THE GAME · 700 POINTS IS PERFECT';
  $('dcCabinet').dataset.zone=zone;
  $('dcCanvas').setAttribute('aria-label',`Pixel-art hockey scenery: ${dcZones[zone].toLowerCase()}`);
}
function dcRender(t,st){
  const state=dcModel.state(t,st.guesses,DEEP_CUT_DATA),session=dcSession(),board=$('dcBoard');
  document.body?.classList.toggle('dc-immersive',dcActive());$('dcCabinet').dataset.phase=state.over?'complete':session.index!==st.guesses.length?'reveal':session.phase;
  dcHud(state);dcSoundPaint();dcCorrectionsPaint();
  $('dcTiers').innerHTML=dcModel.tiers.slice(1).map(t=>`<div class="dc-tier" style="--tier-color:${t.color}"><i aria-hidden="true"></i><b>${t.score}</b><span>${t.name}</span></div>`).join('');
  if(state.over){clearInterval(dcTimer);dcTimer=0;dcResults(state);}
  else if(session.phase==='ready'&&!st.guesses.length){
    board.innerHTML=`<p class="dc-eyebrow"><span>THE NHL RARITY GAME</span><span>${mode==='unlimited'?'UNRANKED PRACTICE':mode==='archive'?'ARCHIVE SHIFT':`DAILY #${dailyNumber('deepcut',st.day)}`}</span></p><div class="dc-intro-head"><h3>You know the stars.<br>Who else have you got?</h3><i class="dc-pixel-puck" aria-hidden="true"></i></div><p class="dc-copy">Seven hockey prompts. Name anyone who fits.<br>The less obvious your answer, the farther you skate.</p><div class="dc-actions"><button type="button" class="dc-primary" data-dc-start>▶ ${mode==='unlimited'?'START PRACTICE':'TAKE THE ICE'}</button><button type="button" class="dc-secondary" data-dc-variant="${mode==='unlimited'?'daily':'unlimited'}">${mode==='unlimited'?'DAILY SHIFT':'PRACTICE'}</button></div><p class="dc-fineprint">35 seconds per prompt · No answer suggestions · ${mode==='unlimited'?'Fresh sets. No daily stats affected.':mode==='archive'?'Replay a previous day’s seven prompts.':'One shared daily set. Your progress saves automatically.'}</p>`;
  } else if(session.index!==st.guesses.length||session.phase==='reveal')dcReveal(state);
  else {
    const p=dcCurrentPrompt();
    board.innerHTML=`<p class="dc-eyebrow"><span>${esc(p.family.toUpperCase())}</span><span>PROMPT ${st.guesses.length+1} / 7</span></p>${dcClockMarkup()}<h3 id="dcPrompt">${esc(p.text)}</h3><p class="dc-prompt-note">${esc(p.note)}</p><form class="dc-answer-form" id="dcForm"><input id="dcAnswer" type="text" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" maxlength="80" aria-label="Name an NHL player" aria-describedby="dcPrompt dcFeedback dcClockText" placeholder="Think beyond the first line…" disabled><button type="submit" class="dc-primary" id="dcSubmit" disabled>LOCK IT IN ↵</button></form><p class="dc-feedback" id="dcFeedback" role="status" aria-live="polite">${session.phase==='preview'?'Get ready. Your clock starts in a moment.':'One valid player. Make it a good pull.'}</p><button type="button" class="dc-pass" data-dc-pass>Pass this prompt · 0 points</button>`;
    dcPulse();if(dcActive()&&!dcTimer&&['preview','ask'].includes(session.phase))dcTimer=setInterval(dcPulse,100);
  }
  if(!dcAnimation)dcVisualDistance=state.distance;
  dcDraw(performance.now());if(dcActive()&&!dcReduced()&&!document.hidden&&!dcFrame)dcFrame=requestAnimationFrame(dcAnimate);
}
function dcReveal(state){
  const r=state.rounds.at(-1);
  if(!r){dcSession().phase='ready';return dcRender(S.deepcut.target,S.deepcut);}
  const correction=dcSession().lastCorrection,kind=correction?.round===state.rounds.length-1&&correction.kind,label=kind&&Object.hasOwn(DC_CORRECTION_LABELS,kind)?DC_CORRECTION_LABELS[kind]:'';
  $('dcBoard').innerHTML=`<p class="dc-eyebrow"><span>PROMPT ${state.rounds.length} / 7</span><span>SHIFT IN PROGRESS</span></p><div class="dc-reveal" style="--dc-result:${r.tier.color}"><p class="dc-reveal-tag">${r.tier.name.toUpperCase()}</p>${label?`<p class="dc-correction-note">${label} · counted as</p>`:''}<h3>${r.id?esc(r.name):'This one got away.'}</h3><div class="dc-reveal-score"><strong>+${r.score}</strong><span>${r.score?`${(r.score*10).toLocaleString()} metres of fresh ice`:'Shake it off. There’s more ice ahead.'}</span></div><p class="dc-copy">${esc(r.prompt.text)}</p></div><div class="dc-actions"><button type="button" class="dc-primary" data-dc-start>NEXT PROMPT →</button></div>`;
}
function dcResults(state){
  $('dcBoard').innerHTML=`<p class="dc-eyebrow"><span>SHIFT COMPLETE</span><span>${mode==='unlimited'?'PRACTICE':mode==='archive'?'ARCHIVE':'DAILY SHIFT'}</span></p><div class="dc-finish-heading"><h3>${dcModel.rank(state.score)}</h3><strong>${state.score}<small> / 700</small></strong></div><p class="dc-copy">${state.rounds.filter(r=>r.id).length} of 7 answers landed. ${state.rounds.filter(r=>r.score>=60).length} rare pulls. ${state.distance.toLocaleString()} metres on the ice.</p><ol class="dc-round-results">${state.rounds.map((r,i)=>`<li style="--tier-color:${r.tier.color}"><b>${i+1}</b><span>${esc(r.name||'No answer')}<small>${esc(r.tier.name)}</small></span><em>+${r.score}</em></li>`).join('')}</ol><div class="dc-actions"><button type="button" class="dc-primary" data-dc-share>SHARE YOUR SHIFT ↗</button><button type="button" class="dc-secondary" data-dc-variant="unlimited">PLAY PRACTICE</button>${mode!=='daily'?'<button type="button" class="dc-secondary" data-dc-variant="daily">DAILY SHIFT</button>':''}</div><div class="dc-answer-sheets"><p>THE DEEP CUTS YOU COULD HAVE PULLED</p>${state.rounds.map((r,i)=>`<details class="dc-answer-sheet" data-dc-sheet="${r.prompt.id}"><summary>${i+1}. ${esc(r.prompt.text)}</summary><input type="search" data-dc-answer-search aria-label="Search accepted answers for prompt ${i+1}" placeholder="Search all accepted answers…"><div class="dc-answer-list"></div><small></small></details>`).join('')}</div>`;
  $('dcBoard').querySelectorAll('[data-dc-sheet]').forEach(el=>dcAnswerSheet(el,''));
}
function dcAnswerSheet(el,query){
  const p=dcIndex().prompts.get(el.dataset.dcSheet),q=dcModel.normalize(query),answers=p.answers.map(([id,score])=>({...dcIndex().players.get(id),score})).filter(p=>dcModel.normalize(p.name).includes(q)).sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name));
  el.querySelector('.dc-answer-list').innerHTML=answers.slice(0,60).map(p=>`<div><span>${esc(p.name)}</span><b style="color:${dcModel.tier(p.score).color}">+${p.score}</b></div>`).join('')||'<div>No matching answers.</div>';
  el.querySelector('small').textContent=answers.length>60?`Showing 60 of ${answers.length.toLocaleString()} answers. Search to find a name.`:`${answers.length.toLocaleString()} accepted ${answers.length===1?'answer':'answers'} · fixed rarity tiers`;
}
function dcBegin(){
  if(!dcActive()||S.deepcut.over)return;
  const session=dcSession();if(['preview','ask'].includes(session.phase)&&session.index===S.deepcut.guesses.length)return;
  dcEndEffects();
  if(dcSoundOn()&&!dcAudio){try{dcAudio=new (window.AudioContext||window.webkitAudioContext)();}catch{}}
  Object.assign(session,{index:S.deepcut.guesses.length,phase:'preview',previewUntil:Date.now()+3000});
  session.deadline=session.previewUntil+35000;saveProgress();dcRender(S.deepcut.target,S.deepcut);
}
function dcPulse(){
  if(!dcActive()||S.deepcut.over){clearInterval(dcTimer);dcTimer=0;return;}
  const session=dcSession();if(!['preview','ask'].includes(session.phase))return;
  const now=Date.now();
  if(now>=session.deadline)return dcLand('MISS');
  if(session.phase==='preview'&&now>=session.previewUntil){session.phase='ask';saveProgress();const input=$('dcAnswer');if(input){input.disabled=false;$('dcSubmit').disabled=false;input.focus({preventScroll:true});$('dcFeedback').textContent='One valid player. Make it a good pull.';}}
  const preview=session.phase==='preview',left=preview?session.previewUntil-now:session.deadline-now;
  if(!$('dcClockText'))return;
  dcPaintClock(left,preview);
  $('dcClockLabel').textContent=preview?'GET READY':'ARENA CLOCK';
  $('dcClockFill').style.width=`${Math.max(0,Math.min(100,left/(preview?3000:35000)*100))}%`;
  $('dcClock').classList.toggle('urgent',!preview&&left<=8000);
  if(!preview&&$('dcAnswer').disabled){$('dcAnswer').disabled=false;$('dcSubmit').disabled=false;}
}
function dcLand(action){
  const st=S.deepcut;if(!dcActive()||st.over||!['preview','ask'].includes(dcSession().phase))return;
  let after;try{after=dcModel.state(st.target,[...st.guesses,action],DEEP_CUT_DATA);}catch{return;}
  clearInterval(dcTimer);dcTimer=0;const before=dcModel.state(st.target,st.guesses,DEEP_CUT_DATA).distance,r=after.rounds.at(-1),level=dcAnimationLevel(r.score);
  dcEndEffects();dcVisualDistance=before;
  dcAnimation={start:performance.now(),duration:dcReduced()?0:900+level*400,from:before,to:after.distance,score:r.score,level,color:r.tier.color};
  dcSession().phase='reveal';doGuess(action);dcPlay(r.score);
  if(r.score){
    const cabinet=$('dcCabinet');cabinet.dataset.celebration=level;cabinet.style.setProperty?.('--dc-celebration',r.tier.color);
    $('dcBurst').innerHTML=`<small>${r.tier.name.toUpperCase()}</small>+${(r.score*10).toLocaleString()} m`;$('dcBurst').classList.add('on');
    dcBurstTimer=setTimeout(()=>$('dcBurst').classList.remove('on'),900+level*400);dcEffectTimer=setTimeout(()=>delete cabinet.dataset.celebration,900+level*400);
  }
  if(dcZone(before)!==dcZone(after.distance)){
    $('dcZoneAnnouncement').innerHTML=`<small>NEW ARENA UNLOCKED</small><strong>${dcZones[dcZone(after.distance)]}</strong>`;
    $('dcZoneAnnouncement').hidden=false;dcZoneTimer=setTimeout(()=>$('dcZoneAnnouncement').hidden=true,4000);
  }
  if(dcReduced()){dcVisualDistance=after.distance;dcAnimation=null;dcDraw(performance.now());}
}
function dcSubmit(event){
  event.preventDefault();dcPulse();if(!dcActive()||S.deepcut.over||dcSession().phase!=='ask')return;
  const input=$('dcAnswer'),value=input.value.trim();if(!value){input.focus();return;}
  const result=dcModel.match(value,dcCurrentPrompt().id,DEEP_CUT_DATA,{corrections:dcCorrectionsOn()});
  if(result.status==='accepted'){dcSession().lastCorrection={round:S.deepcut.guesses.length,kind:result.correction};return dcLand(String(result.id));}
  if(result.status==='ambiguous'){$('dcFeedback').textContent='More than one player fits that name. Use a full name; add a birth year if needed.';$('dcFeedback').classList.add('error');input.focus();return;}
  dcSession().deadline-=3000;saveProgress();
  $('dcFeedback').textContent=result.status==='wrong'?'That player doesn’t fit this prompt. −3 seconds. Try another.':dcCorrectionsOn()?'Name not recognized. Check the spelling or try another player. −3 seconds.':'Enter the full player name, or enable Answer corrections. −3 seconds.';
  $('dcFeedback').classList.add('error');input.select();dcPulse();
}
$('dcBoard').addEventListener('click',async event=>{
  if(event.target.closest('[data-dc-start]'))return dcBegin();
  if(event.target.closest('[data-dc-pass]')&&['ask','preview'].includes(dcSession().phase))return dcLand('MISS');
  const variant=event.target.closest('[data-dc-variant]');
  if(variant){dcCleanup();mode=variant.dataset.dcVariant;store.set('sweater-mode',mode);if(mode==='unlimited')loadUnlimited(true);else loadDaily();return;}
  if(event.target.closest('[data-dc-share]')){
    const st=S.deepcut,number=mode==='unlimited'?'Practice':dailyNumber('deepcut',st.day),link=SITE&&!/__SITE__/.test(SITE)?`${SITE}share/#deepcut`:location.href;
    const text=G.deepcut.shareText(st.target,{guesses:st.guesses},number,`\n\n${link}`);
    if(await copyToClipboard(text,'Shift copied — send it to your hockey group'))globalThis.SweaterAnalytics?.share?.('deepcut');
  }
});
$('dcBoard').addEventListener('submit',event=>{if(event.target.id==='dcForm')dcSubmit(event);});
$('dcBoard').addEventListener('input',event=>{if(event.target.matches('[data-dc-answer-search]'))dcAnswerSheet(event.target.closest('[data-dc-sheet]'),event.target.value);});
$('dcCorrections').onchange=()=>{
  store.set('sweater-deepcut-corrections',$('dcCorrections').checked);dcCorrectionsPaint();
  if(dcActive()&&dcSession().phase==='ask'&&$('dcFeedback')){$('dcFeedback').textContent=dcCorrectionsOn()?'Corrections on · Surnames, nicknames and close spellings count.':'Corrections off · Enter an exact full name.';$('dcFeedback').classList.remove('error');}
};
$('view-deepcut').addEventListener('click',event=>{
  if(event.target.closest('[data-dc-home]')){if(typeof showHub==='function')showHub();else toast('This is the standalone Deep Cut preview');return;}
  const button=event.target.closest('[data-dc-menu]');if(!button)return;
  if(button.dataset.dcMenu==='archive'&&typeof openArchive==='function')openArchive();
  else if(button.dataset.dcMenu==='stats'&&typeof openModal==='function'){statsGame=null;openModal('statsModal');}
  else toast('Stats and archives are available in the full Sweater site');
});
$('dcSound').onclick=()=>{const on=!dcSoundOn();if(on){try{dcAudio ||= new (window.AudioContext||window.webkitAudioContext)();dcAudio.resume().catch(()=>{});}catch{toast('Sound is unavailable in this browser');return;}}store.set('sweater-deepcut-sound',on);dcSoundPaint();if(on)dcPlay(30);};
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(dcFrame);dcFrame=0;dcClearRinkParticles();}else if(dcActive()){dcPulse();if(!dcFrame&&!dcReduced())dcFrame=requestAnimationFrame(dcAnimate);}});
window.addEventListener('pagehide',()=>{if(dcActive()){saveProgress();dcCleanup();}});
window.addEventListener('resize',()=>{dcClearRinkParticles();if(dcActive())dcDraw(performance.now());});

// Small scenery-only flourishes: a tap makes a puff, and dragging leaves a trail.
// Pointer listeners are passive so touch scrolling and game controls keep working.
function dcClearRinkParticles(){dcRinkParticles=[];dcRinkPointer=null;dcRinkLastPoint=null;}
function dcStartCrowdWave(){
  const zone=dcZone(dcVisualDistance);if(!dcActive()||document.hidden||dcReduced()||zone<2||dcCrowdWave&&performance.now()-dcCrowdWave.start<6200)return;
  dcCrowdWave={start:performance.now(),zone};$('dcWaveStatus').textContent='The crowd is doing the wave.';dcWaveState(performance.now(),zone);
}
function dcWaveState(time,zone){
  if(dcCrowdWave&&(dcCrowdWave.zone!==zone||time-dcCrowdWave.start>=6200||dcReduced())){dcCrowdWave=null;$('dcWaveStatus').textContent='Wave complete.';}
  const button=$('dcWave');button.hidden=zone<2||dcReduced();button.disabled=!!dcCrowdWave;button.textContent=dcCrowdWave?'WAVING…':'WAVE ↝';
  return dcCrowdWave;
}
$('dcWave').onclick=dcStartCrowdWave;
function dcRinkSurface(event){return dcActive()&&!document.hidden&&!dcReduced()&&!event.target.closest('.dc-board,.dc-hud,.dc-masthead,.dc-tier-strip,.dc-footer,button,a,input,summary,details');}
function dcSprinkleRink(clientX,clientY,count=10){
  if(!dcActive()||document.hidden||dcReduced())return;
  const bounds=$('dcCanvas').getBoundingClientRect();
  if(!bounds.width||!bounds.height||clientX<bounds.left||clientX>bounds.right||clientY<bounds.top||clientY>bounds.bottom)return;
  const zone=dcZone(dcVisualDistance),now=performance.now();
  const colors=[['#ecfff7','#bce7ee'],['#d9f9ff','#8ec9db'],['#81f2df','#eeb1ba','#d8e9f4'],['#e6edff','#a6c5ed'],['#ffdc8b','#fff0c4']][zone];
  for(let i=0;i<Math.min(count,10);i++)dcRinkParticles.push({x:(clientX-bounds.left)/bounds.width,y:(clientY-bounds.top)/bounds.height,vx:(Math.random()-.5)*42,vy:-12-Math.random()*28,born:now,life:700+Math.random()*500,zone,color:colors[i%colors.length],size:i%4===0?2:1,turn:Math.random()*Math.PI});
  dcRinkParticles=dcRinkParticles.slice(-120);
}
$('dcCabinet').addEventListener('pointerdown',event=>{
  if(event.button!==0||event.isPrimary===false||!dcRinkSurface(event))return;
  dcRinkPointer=event.pointerId;dcRinkLastPoint={x:event.clientX,y:event.clientY,time:performance.now()};dcSprinkleRink(event.clientX,event.clientY);dcStartCrowdWave();
},{passive:true});
$('dcCabinet').addEventListener('pointermove',event=>{
  if(event.pointerId!==dcRinkPointer||!dcRinkSurface(event))return;
  const last=dcRinkLastPoint,now=performance.now();
  if(last&&(now-last.time<35||Math.hypot(event.clientX-last.x,event.clientY-last.y)<7))return;
  dcRinkLastPoint={x:event.clientX,y:event.clientY,time:now};dcSprinkleRink(event.clientX,event.clientY,3);
},{passive:true});
for(const name of ['pointerup','pointercancel','blur'])window.addEventListener(name,()=>{dcRinkPointer=null;dcRinkLastPoint=null;});
function dcDrawRinkParticles(c,paint,time,W,H,pixel,zone){
  if(dcReduced()){dcClearRinkParticles();return;}
  dcRinkParticles=dcRinkParticles.filter(p=>time-p.born<p.life&&p.zone===zone);
  for(const p of dcRinkParticles){
    const age=Math.max(0,time-p.born),t=age/1000,fade=1-age/p.life,x=p.x*W+p.vx*t/pixel,y=p.y*H+(p.vy*t+(zone<3?32:-8)*t*t)/pixel;
    c.globalAlpha=Math.min(.85,fade*1.3);
    if(zone===0){paint(x-1,y,3,1,p.color);paint(x,y-1,1,3,p.color);if(p.size===2){paint(x-1,y-1,1,1,p.color);paint(x+1,y+1,1,1,p.color);}}
    else if(zone===1)paint(x,y,p.size,1,p.color);
    else if(zone===2)paint(x,y,p.size,Math.sin(p.turn+t*9)>0?2:1,p.color);
    else {paint(x-1,y,3,1,p.color);paint(x,y-1,1,3,p.color);if(zone===4&&p.size===2){paint(x-2,y,5,1,p.color);paint(x,y-2,1,5,p.color);}}
  }
  c.globalAlpha=1;
}

// Original procedural pixel scenery and skater; no third-party game art.
function dcAnimate(time){dcFrame=0;if(!dcActive()||document.hidden)return;if(time-dcLastFrame>32){dcLastFrame=time;dcDraw(time);}if(!dcReduced())dcFrame=requestAnimationFrame(dcAnimate);}
function dcDraw(time,{backgroundOnly=false}={}){
  const canvas=$('dcCanvas'),c=canvas.getContext('2d');if(!c)return;
  const bounds=canvas.getBoundingClientRect(),mobile=bounds.width<620,pixel=mobile?2:3,W=Math.max(160,Math.ceil(bounds.width/pixel)),H=Math.max(160,Math.ceil(bounds.height/pixel));
  if(canvas.width!==W||canvas.height!==H){canvas.width=W;canvas.height=H;}c.imageSmoothingEnabled=false;
  let moving=false,speed=.1,level=0,progress=1,color='#81f2df';
  if(dcAnimation){
    const a=dcAnimation;progress=a.duration?Math.min(1,(time-a.start)/a.duration):1;
    dcVisualDistance=a.from+(a.to-a.from)*(1-(1-progress)**3);moving=progress<1&&a.score>0;level=a.level;color=a.color;
    speed=moving?1.5+level*1.15:.1;
    $('dcDistance').textContent=Math.round(dcVisualDistance).toLocaleString();$('dcPoints').textContent=String(Math.round(dcVisualDistance/10)).padStart(3,'0');
    if(progress>=1)dcAnimation=null;
  }
  if(!dcReduced())dcOffset+=speed;
  const zone=dcZone(dcVisualDistance),gold=zone===4,foot=H-Math.round(108/pixel),ice=Math.min(Math.floor(H*.76),foot-25);
  const wave=dcWaveState(time,zone);
  const paint=(x,y,w,h,fill)=>{c.fillStyle=fill;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));};
  paint(0,0,W,H,['#102535','#102232','#091a31','#131c36','#211b33'][zone]);
  if(zone===0){
    for(let i=0;i<75;i++)paint((i*97+23)%W,(i*31+7)%Math.max(1,ice-40),1,i%7===0?2:1,i%5?'#729dab77':'#c4e7df');
    const ground=ice-5,townBase=ground-9;
    paint(0,townBase-1,W,ice-townBase+1,'#557986');paint(0,townBase,W,3,'#a7c3c7');
    for(let i=0;i<Math.ceil(W/39)+2;i++){
      const x=(i*49-dcOffset*.07+W*20)%(W+90)-45,w=26+i%3*5,h=19+i*17%29,top=townBase-h,roof=7+i%3;
      // Full facades meet the snow: foundations, doors, warm windows and rooflines.
      paint(x,top,w,h,['#345763','#3a5a67','#294a5a'][i%3]);paint(x+1,top+2,2,h-3,'#64828a');paint(x,townBase-3,w,3,'#6d8490');
      paint(x+w-9,townBase-11,5,11,'#183444');paint(x+w-8,townBase-10,3,4,'#b6c7b288');paint(x+w-4,townBase-5,1,1,'#edce8b');
      if(i%3!==1){
        paint(x+5,top-roof-4,3,8,'#506471');paint(x+4,top-roof-5,5,2,'#bed3d0');
        for(let row=0;row<roof;row++){const half=Math.ceil((row+1)/roof*(w/2+2));paint(x+w/2-half,top-roof+row,half*2,1,row<3?'#c4d8d5':'#849da7');}
      }else {paint(x-1,top-3,w+2,3,'#c4d8d5');paint(x+4,top-7,7,4,'#6d8590');paint(x+3,top-8,9,1,'#c4d8d5');}
      paint(x-2,top-1,w+4,2,'#a9c4c8');
      for(let row=0;row<Math.max(1,Math.floor((h-6)/10));row++)for(let col=0;col<2;col++){
        const wx=x+5+col*8,wy=top+5+row*9;if(wy+4>townBase-5||wx+4>x+w-2)continue;
        paint(wx-1,wy-1,6,6,'#203b4a');paint(wx,wy,4,4,(i+row+col)%3?'#e6cd92':'#6d939e');paint(wx+2,wy,1,4,'#55717c');
      }
      paint(x-2,townBase,w+4,2,'#c0d5d4');paint(x+w-10,townBase+2,8,1,'#8baab5');
    }
    for(let i=0;i<Math.ceil(W/55)+2;i++){
      const x=(i*67+19-dcOffset*.2+W*30)%(W+100)-50,h=22+i*7%20,base=ground+(i%2?1:0),top=base-h-9;
      // The canopy ends above a visible trunk rooted in a small snow bank.
      paint(x-6,base,13,2,'#365d6e');paint(x-2,base-15,5,16,'#735c4b');paint(x-1,base-13,2,13,'#a18a69');paint(x-4,base-1,3,2,'#735c4b');paint(x+2,base-1,3,2,'#735c4b');
      for(let row=0;row<h;row++){
        const half=2+Math.floor(row/7)*2+Math.floor(row%7/2);
        paint(x-half,top+row,half*2+1,1,row%7===0?'#74999e':row%7===1?'#416f79':'#163e49');
      }
      paint(x-7,base+1,15,2,'#b6d0d1');paint(x-3,base,3,1,'#cce0dc');
    }
    paint(0,ice-2,W,2,'#c0d8d7');
  }else if(zone===1){
    DEEP_CUT_SCENERY.community(paint,{W,ice,time,still:dcReduced()});
  }else{
    DEEP_CUT_SCENERY.arena(paint,{W,ice,time,still:dcReduced(),zone,wave});
  }
  const lightCount=zone===0?4:zone===1?6:10;
  for(let i=0;i<lightCount;i++){
    const x=((i+.25)*W/lightCount-dcOffset*.03+W*20)%(W+30)-15,top=zone===0?ice-85:35;
    if(zone===0){paint(x,top,2,ice-top,'#597b89');paint(x-2,ice-3,6,3,'#748e96');}
    else {paint(x,29,1,top-29,'#71818e');paint(x-6,top-1,13,3,'#536572');}
    paint(x-5,top,11,2,gold?'#ffdf8f':'#d8e9d9');
    c.fillStyle=gold?'#ffdb820b':'#b1f3ef08';c.beginPath();c.moveTo(x-3,top+2);c.lineTo(x+4,top+2);c.lineTo(x+35,ice);c.lineTo(x-35,ice);c.closePath();c.fill();
  }
  DEEP_CUT_SCENERY.boards(paint,{W,ice,zone,offset:dcOffset});
  DEEP_CUT_SCENERY.iceSurface(paint,{W,H,ice,zone,offset:dcOffset});
  if(zone===0&&!dcReduced())for(let i=0;i<45;i++)paint((i*113+time*.007*(1+i%3))%W,(i*17+time*.004)%ice,1,1,'#d7f1ec66');
  if(backgroundOnly)return;
  const x=Math.max(23,Math.floor(W*(mobile?.14:bounds.height<830?.09:.22))),y=foot-39,stride=moving?Math.floor(time/(125-level*8))%2:0,bob=moving?stride:0;
  paint(x-6,foot,35,3,'#315a6a55');
  if(moving){
    const spray=4+level*4;for(let i=0;i<spray;i++){const t=(progress*3+i*.131)%1;paint(x-3-t*(12+level*9),foot-t*(3+level*3)+i%3,1+i%2,1,'#ecfff1bb');}
    for(let i=0;i<level*2;i++)paint(x-25-i*9,foot-7-i%4*4,10+i%9,1,color+'66');
  }
  const px=(dx,dy,w,h,fill)=>paint(x+dx,y+dy+bob,w,h,fill);
  px(3,0,9,2,'#ece9ce');px(1,2,13,6,'#e4e7cf');px(3,3,8,2,'#f7f3d7');px(12,5,3,5,'#d7ad8d');px(11,5,2,2,'#24384d');px(12,10,2,2,'#c89f81');
  px(2,8,9,4,'#233c50');px(-1,12,15,12,gold?'#e5b861':'#64c9c2');px(2,13,8,9,gold?'#ffdb82':'#8ce3d0');px(0,18,13,2,'#eef1d8');px(3,15,3,4,'#244c54');px(7,15,2,4,'#244c54');
  px(-5,13,5,5,'#5ab9b6');px(-7,18,6,4,'#253c50');px(12,13,6,5,'#7bd5c6');px(16,17,5,5,'#263d51');px(18,18,4,2,'#e4ddc2');
  px(0,24,13,5,'#233e53');px(stride?-3:0,29,5,6,'#20394e');px(stride?10:8,28,5,7,'#29455a');px(stride?-6:-2,35,8,2,'#e9ebd4');px(stride?10:9,35,8,2,'#e9ebd4');px(stride?-7:-3,38,10,1,'#243b4c');px(stride?9:8,38,11,1,'#243b4c');
  // One continuous, taped blade; exactly one puck remains beside its toe.
  for(let i=0;i<15;i++)px(20+i,22+i,2,2,'#b49d76');px(33,36,10,2,'#eee9cd');px(33,38,11,1,'#65717a');px(35,36,1,2,'#83929b');px(39,36,1,2,'#83929b');
  c.fillStyle='#101a24';c.beginPath();c.ellipse(x+46,y+39+bob,3,1.5,0,0,Math.PI*2);c.fill();
  if(moving&&!dcReduced()){
    const count=level<4?level*7:level===4?35:level===5?62:95,fade=Math.sin(Math.PI*progress);
    c.globalAlpha=fade;
    for(let i=0;i<count;i++){
      const angle=i*2.39996,travel=(18+level*18)*progress,originX=level>=5?W*(i%2?.86:.14):x+10,originY=level>=5?H*(.25+i%3*.08):foot-20;
      const sx=originX+Math.cos(angle)*travel*(.5+i%7/7),sy=originY+Math.sin(angle)*travel-progress*(level*8)+progress*progress*35;
      paint(sx,sy,level>=5?2:1,1+(i%3===0?1:0),i%3===0?'#fff4d4':color);
      if(level===6&&i%8===0){paint(sx-2,sy,5,1,'#ffdb82');paint(sx,sy-2,1,5,'#ffdb82');}
    }
    if(level>=4){
      c.globalAlpha=fade*.2;c.fillStyle=color;
      for(let i=0;i<(level===6?5:2);i++){const lx=W*(i+1)/(level===6?6:3);c.beginPath();c.moveTo(lx-2,30);c.lineTo(lx+2,30);c.lineTo(lx+50+Math.sin(time/700+i)*20,ice);c.lineTo(lx-50+Math.sin(time/700+i)*20,ice);c.closePath();c.fill();}
    }
    c.globalAlpha=1;
  }
  dcDrawRinkParticles(c,paint,time,W,H,pixel,zone);
}
