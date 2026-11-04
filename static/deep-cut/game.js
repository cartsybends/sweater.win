const DEEP_CUT_DATA = /*__DEEP_CUT_DATA__*/{};
const dcModel = DEEP_CUT_MODEL;
const dcIndex = () => dcModel.index(DEEP_CUT_DATA);
let dcTimer=0,dcFrame=0,dcAudio=null,dcAnimation=null,dcLastFrame=0,dcOffset=0,dcVisualDistance=0,dcBurstTimer=0;
const dcReduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const dcActive=()=>game==='deepcut'&&!onHub&&!$('view-deepcut').hidden;
const dcSession=()=>S.deepcut.opts.dcRun;
const dcCurrentPrompt=()=>dcIndex().prompts.get(S.deepcut.target.prompts[S.deepcut.guesses.length]);
const dcSoundOn=()=>store.get('sweater-deepcut-sound')===true;
function dcSoundPaint(){const b=$('dcSound'),on=dcSoundOn();b.textContent=on?'SOUND ON':'SOUND OFF';b.setAttribute('aria-pressed',String(on));b.setAttribute('aria-label',`Turn game sound ${on?'off':'on'}`);}
function dcPlay(score){
  if(!dcSoundOn()||!dcAudio)return;
  dcAudio.resume().catch(()=>{});
  const notes=score>=85?[440,554.37,659.25,880]:score>=30?[329.63,440,554.37]:score?[261.63,329.63]:[164.81,130.81];
  notes.forEach((frequency,i)=>{const at=dcAudio.currentTime+i*.09,o=dcAudio.createOscillator(),g=dcAudio.createGain();o.type='triangle';o.frequency.value=frequency;g.gain.setValueAtTime(0,at);g.gain.linearRampToValueAtTime(.045,at+.012);g.gain.exponentialRampToValueAtTime(.001,at+.18);o.connect(g);g.connect(dcAudio.destination);o.start(at);o.stop(at+.2);});
}
function dcCleanup(){clearInterval(dcTimer);dcTimer=0;cancelAnimationFrame(dcFrame);dcFrame=0;clearTimeout(dcBurstTimer);$('dcBurst').classList.remove('on');dcAnimation=null;}

G.deepcut={
  kind:'score',repeat:true,title:'Deep Cut',share:'Sweater Deep Cut',view:'view-deepcut',max:7,
  next:'Another shift',hideReveal:true,quietFinish:true,persistUnlimited:true,
  pool:()=>DEEP_CUT_DATA.runs,
  daily(day){return dcIndex().runs.get(DAILY.deepcut?.[day]?.id)||this.pool()[hash(`sweater-deepcut-${day}`)%this.pool().length];},
  random(){return pick(this.pool());},tid:t=>t.id,player:()=>null,meta:()=>'',
  prepareTarget(t,opts){const s=opts.dcRun;if(s?.target!==t.id||!['ready','preview','ask','reveal'].includes(s.phase)||!Number.isInteger(s.index)||s.index<0||s.index>7||['preview','ask'].includes(s.phase)&&(!Number.isFinite(s.deadline)||!Number.isFinite(s.previewUntil)))opts.dcRun={target:t.id,index:0,phase:'ready'};return t;},
  reset(){dcCleanup();dcSoundPaint();},
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
  $('dcDots').innerHTML=Array.from({length:7},(_,i)=>{const r=state.rounds[i],current=!state.over&&i===state.rounds.length&&['preview','ask'].includes(session.phase);return `<i${current?' class="is-current"':''}${r?` style="background:${r.tier.color};border-color:${r.tier.color}"`:''} title="${r?`Round ${i+1}: ${r.score} points`:`Round ${i+1}${current?': current prompt':''}`}" aria-label="${r?`Round ${i+1}: ${r.score} points`:`Round ${i+1}${current?': current prompt':''}`}"></i>`;}).join('');
  $('dcTrackFill').style.width=`${state.distance/7000*100}%`;$('dcTrack').setAttribute('aria-valuenow',state.distance);
  const zones=['THE NEIGHBOURHOOD RINK','THE COMMUNITY ARENA','THE BIG LEAGUES','UP IN THE RAFTERS','LEGENDS ONLY'];
  $('dcArenaTag').textContent=`0${Math.min(5,1+Math.floor(state.distance/1500))} / ${zones[Math.min(4,Math.floor(state.distance/1500))]}`;
}
function dcRender(t,st){
  const state=dcModel.state(t,st.guesses,DEEP_CUT_DATA),session=dcSession(),board=$('dcBoard');
  dcHud(state);dcSoundPaint();
  $('dcTiers').innerHTML=dcModel.tiers.slice(1).map(t=>`<div class="dc-tier" style="--tier-color:${t.color}"><i aria-hidden="true"></i><b>${t.score}</b><span>${t.name}</span></div>`).join('');
  if(state.over){clearInterval(dcTimer);dcTimer=0;dcResults(state);}
  else if(session.phase==='ready'&&!st.guesses.length){
    board.innerHTML=`<p class="dc-eyebrow"><span>THE NHL RARITY GAME</span><span>${mode==='unlimited'?'UNRANKED PRACTICE':mode==='archive'?'ARCHIVE SHIFT':`DAILY #${dailyNumber('deepcut',st.day)}`}</span></p><div class="dc-intro-head"><h3>You know the stars.<br>Who else have you got?</h3><i class="dc-pixel-puck" aria-hidden="true"></i></div><p class="dc-copy">Seven hockey prompts. Name anyone who fits.<br>The less obvious your answer, the farther you skate.</p><div class="dc-actions"><button type="button" class="dc-primary" data-dc-start>▶ ${mode==='unlimited'?'START PRACTICE':'TAKE THE ICE'}</button><button type="button" class="dc-secondary" data-dc-variant="${mode==='unlimited'?'daily':'unlimited'}">${mode==='unlimited'?'DAILY SHIFT':'PRACTICE'}</button></div><p class="dc-fineprint">35 seconds per prompt · No answer suggestions · ${mode==='unlimited'?'Fresh sets. No daily stats affected.':mode==='archive'?'Replay a previous day’s seven prompts.':'One shared daily set. Your progress saves automatically.'}</p>`;
  } else if(session.index!==st.guesses.length||session.phase==='reveal')dcReveal(state);
  else {
    const p=dcCurrentPrompt();
    board.innerHTML=`<p class="dc-eyebrow"><span>${esc(p.family.toUpperCase())}</span><span>PROMPT ${st.guesses.length+1} / 7</span></p><h3 id="dcPrompt">${esc(p.text)}</h3><p class="dc-prompt-note">${esc(p.note)}</p><div class="dc-clock-row"><span id="dcClockLabel">READ THE PROMPT</span><strong id="dcClockText">3</strong></div><div class="dc-clock" id="dcClock"><i id="dcClockFill"></i></div><form class="dc-answer-form" id="dcForm"><input id="dcAnswer" type="text" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" maxlength="80" aria-label="Name an NHL player" aria-describedby="dcPrompt dcFeedback" placeholder="Think beyond the first line…" disabled><button type="submit" class="dc-primary" id="dcSubmit" disabled>LOCK IT IN ↵</button></form><p class="dc-feedback" id="dcFeedback" role="status" aria-live="polite">${session.phase==='preview'?'Get ready. Your clock starts in a moment.':'One valid player. Make it a good pull.'}</p><button type="button" class="dc-pass" data-dc-pass>Pass this prompt · 0 points</button>`;
    dcPulse();if(!dcTimer&&['preview','ask'].includes(session.phase))dcTimer=setInterval(dcPulse,100);
  }
  if(!dcAnimation)dcVisualDistance=state.distance;
  dcDraw(performance.now());if(dcActive()&&!dcReduced()&&!document.hidden&&!dcFrame)dcFrame=requestAnimationFrame(dcAnimate);
}
function dcReveal(state){
  const r=state.rounds.at(-1);
  if(!r){dcSession().phase='ready';return dcRender(S.deepcut.target,S.deepcut);}
  $('dcBoard').innerHTML=`<p class="dc-eyebrow"><span>PROMPT ${state.rounds.length} / 7</span><span>SHIFT IN PROGRESS</span></p><div class="dc-reveal" style="--dc-result:${r.tier.color}"><p class="dc-reveal-tag">${r.tier.name.toUpperCase()}</p><h3>${r.id?esc(r.name):'This one got away.'}</h3><div class="dc-reveal-score"><strong>+${r.score}</strong><span>${r.score?`${(r.score*10).toLocaleString()} metres of fresh ice`:'Shake it off. There’s more ice ahead.'}</span></div><p class="dc-copy">${esc(r.prompt.text)}</p></div><div class="dc-actions"><button type="button" class="dc-primary" data-dc-start>NEXT PROMPT →</button></div>`;
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
  $('dcClockText').textContent=preview?Math.ceil(left/1000):`${(Math.max(0,left)/1000).toFixed(1)}s`;
  $('dcClockLabel').textContent=preview?'READ THE PROMPT':'TIME ON THE CLOCK';
  $('dcClockFill').style.width=`${Math.max(0,Math.min(100,left/(preview?3000:35000)*100))}%`;
  $('dcClock').classList.toggle('urgent',!preview&&left<=8000);
  if(!preview&&$('dcAnswer').disabled){$('dcAnswer').disabled=false;$('dcSubmit').disabled=false;}
}
function dcLand(action){
  const st=S.deepcut;if(!dcActive()||st.over||!['preview','ask'].includes(dcSession().phase))return;
  clearInterval(dcTimer);dcTimer=0;const before=dcModel.state(st.target,st.guesses,DEEP_CUT_DATA).distance;
  dcSession().phase='reveal';doGuess(action);
  const after=dcModel.state(st.target,st.guesses,DEEP_CUT_DATA),r=after.rounds.at(-1);
  dcVisualDistance=before;dcAnimation={start:performance.now(),duration:dcReduced()?0:1500+r.score*8,from:before,to:after.distance,score:r.score};
  dcPlay(r.score);if(r.score){$('dcBurst').textContent=`+${(r.score*10).toLocaleString()} m`;$('dcBurst').classList.add('on');clearTimeout(dcBurstTimer);dcBurstTimer=setTimeout(()=>$('dcBurst').classList.remove('on'),2200);}
  if(dcReduced()){dcVisualDistance=after.distance;dcAnimation=null;dcDraw(performance.now());}
}
function dcSubmit(event){
  event.preventDefault();dcPulse();if(!dcActive()||S.deepcut.over||dcSession().phase!=='ask')return;
  const input=$('dcAnswer'),value=input.value.trim();if(!value){input.focus();return;}
  const result=dcModel.match(value,dcCurrentPrompt().id,DEEP_CUT_DATA);
  if(result.status==='accepted')return dcLand(String(result.id));
  if(result.status==='ambiguous'){$('dcFeedback').textContent='More than one player fits that name. Use a full name; add a birth year if needed.';$('dcFeedback').classList.add('error');input.focus();return;}
  dcSession().deadline-=3000;saveProgress();
  $('dcFeedback').textContent=result.status==='wrong'?'That player doesn’t fit this prompt. −3 seconds. Try another.':'Name not recognized. Check the spelling or try another player. −3 seconds.';
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
$('dcSound').onclick=()=>{const on=!dcSoundOn();if(on){try{dcAudio ||= new (window.AudioContext||window.webkitAudioContext)();dcAudio.resume().catch(()=>{});}catch{toast('Sound is unavailable in this browser');return;}}store.set('sweater-deepcut-sound',on);dcSoundPaint();if(on)dcPlay(30);};
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(dcFrame);dcFrame=0;}else if(dcActive()){dcPulse();if(!dcFrame&&!dcReduced())dcFrame=requestAnimationFrame(dcAnimate);}});
window.addEventListener('pagehide',()=>{if(dcActive()){saveProgress();dcCleanup();}});

// Original procedural pixel scenery and skater; no third-party game art.
function dcAnimate(time){dcFrame=0;if(!dcActive()||document.hidden)return;if(time-dcLastFrame>32){dcLastFrame=time;dcDraw(time);}if(!dcReduced())dcFrame=requestAnimationFrame(dcAnimate);}
function dcDraw(time){
  const canvas=$('dcCanvas'),c=canvas.getContext('2d');if(!c)return;
  if(canvas.width!==480||canvas.height!==102){canvas.width=480;canvas.height=102;}c.imageSmoothingEnabled=false;
  let moving=false,speed=.12;
  if(dcAnimation){const k=dcAnimation.duration?Math.min(1,(time-dcAnimation.start)/dcAnimation.duration):1;dcVisualDistance=dcAnimation.from+(dcAnimation.to-dcAnimation.from)*(1-(1-k)**3);moving=k<1&&dcAnimation.score>0;speed=moving?2+dcAnimation.score/18:.12;if(k>=1)dcAnimation=null;}
  if(!dcReduced())dcOffset+=speed;
  const zone=Math.min(4,Math.floor(dcVisualDistance/1500)),gold=zone>=4,sky=gold?'#171b35':zone>=2?'#0b1b32':'#102938',snow='#afdddf';
  c.fillStyle=sky;c.fillRect(0,0,480,102);
  // Light pillars, stars, distant apartments, and snow-covered spruce trees.
  for(let i=0;i<8;i++){const x=(i*73+30-dcOffset*.04+960)%540-30;c.fillStyle=gold?'#ffdb8209':'#81f2df09';c.fillRect(x,0,15,48);c.fillRect(x+4,0,7,48);}
  for(let i=0;i<42;i++){c.fillStyle=i%5===0?'#b5e1dc':'#6d9ca780';c.fillRect((i*97+23)%480,(i*31+7)%42,1,i%7===0?2:1);}
  for(let i=0;i<15;i++){const x=(i*41-dcOffset*.09+960)%550-35,h=10+(i*17)%22;c.fillStyle=i%2?'#193d47':'#173440';c.fillRect(x,52-h,27,h);c.fillStyle='#e7d7a966';for(let j=0;j<3;j++)for(let k=0;k<4;k++)if((i+j+k)%3)c.fillRect(x+4+j*7,55-h+k*5,2,2);}
  for(let i=0;i<12;i++){const x=(i*59-dcOffset*.22+1200)%580-40,h=12+(i*7)%17;c.fillStyle='#0c2732';for(let j=0;j<5;j++)c.fillRect(x-j*2,47-h+j*4,3+j*4,4);c.fillStyle='#51808a';c.fillRect(x-2,47-h+1,5,2);c.fillRect(x-6,47-h+9,7,1);}
  if(zone>=2){c.fillStyle='#31495d';c.fillRect(0,36,480,5);for(let i=0;i<40;i++){const x=(i*15-dcOffset*.4+1000)%510-15;c.fillStyle=['#506679','#718999','#918a85','#3f6871'][i%4];c.fillRect(x,42,3,3);c.fillRect(x+5,47,3,3);}}
  for(let i=0;i<4;i++){const x=(i*160+30-dcOffset*.3+900)%600-60;c.fillStyle='#557783';c.fillRect(x,23,2,38);c.fillRect(x-5,22,12,2);c.fillStyle='#ebefd6';c.fillRect(x-4,24,10,2);c.fillStyle='#d7f3d609';c.fillRect(x-12,28,26,30);}
  c.fillStyle='#a9c9cb';c.fillRect(0,57,480,2);c.fillStyle='#d4e0d6';c.fillRect(0,59,480,9);c.fillStyle='#587780';c.fillRect(0,68,480,2);c.fillStyle='#d09d4c';c.fillRect(0,67,480,1);
  for(let i=0;i<8;i++){const x=(i*80-dcOffset*.7+1000)%600-60;c.fillStyle=['#61828d','#a57873','#497779','#77939b'][i%4];c.fillRect(x,61,20,2);c.fillRect(x+3,64,14,1);}
  c.fillStyle=gold?'#b5cece':'#a6ced3';c.fillRect(0,70,480,32);c.fillStyle='#c5e0de';c.fillRect(0,71,480,1);c.fillStyle='#93bcc7';c.fillRect(0,94,480,8);
  for(let i=0;i<35;i++){const x=(i*73-dcOffset*1.2+2000)%540-30,y=75+i*7%25;c.fillStyle=i%2?'#d6e9df55':'#669ba733';c.fillRect(x,y,5+i%12,1);}
  for(let i=0;i<4;i++){const x=(i*210-dcOffset*1.2+4000)%840-150;c.fillStyle=i%2?'#cd737a77':'#5c8fc577';c.fillRect(x,70,3,32);if(i%2===0){c.fillStyle='#a4657155';c.fillRect(x+28,77,23,1);c.fillRect(x+23,80,1,8);c.fillRect(x+52,80,1,8);c.fillRect(x+28,91,23,1);}}
  // Skater is built on a 1px grid. A two-frame stride drives legs and stick.
  const stride=moving?Math.floor(time/100)%2:Math.floor(time/750)%2,x=142,y=52,bob=moving?stride:0;
  c.fillStyle='#315a6a55';c.fillRect(x-6,91,32,3);
  if(moving){c.fillStyle='#e7f9ee99';for(let i=0;i<7;i++)c.fillRect(x-7-i*5,90+(i%3),2,1);c.fillStyle='#74a6b966';c.fillRect(x-42,80,21,1);c.fillRect(x-30,85,11,1);}
  const px=(dx,dy,w,h,color)=>{c.fillStyle=color;c.fillRect(x+dx,y+dy+bob,w,h);};
  px(3,0,9,2,'#ece9ce');px(1,2,13,6,'#e4e7cf');px(3,3,8,2,'#f7f3d7');px(12,5,3,5,'#d7ad8d');px(11,5,2,2,'#24384d');px(12,10,2,2,'#c89f81');
  px(2,8,9,4,'#233c50');px(-1,12,15,12,gold?'#e5b861':'#64c9c2');px(2,13,8,9,gold?'#ffdb82':'#8ce3d0');px(0,18,13,2,'#eef1d8');px(3,15,3,4,'#244c54');px(7,15,2,4,'#244c54');
  px(-5,13,5,5,'#5ab9b6');px(-7,18,6,4,'#253c50');px(12,13,6,5,'#7bd5c6');px(16,17,5,5,'#263d51');px(18,18,4,2,'#e4ddc2');
  px(0,24,13,5,'#233e53');px(stride?-3:0,29,5,6,'#20394e');px(stride?10:8,28,5,7,'#29455a');px(stride?-6:-2,35,8,2,'#e9ebd4');px(stride?10:9,35,8,2,'#e9ebd4');px(stride?-7:-3,38,10,1,'#243b4c');px(stride?9:8,38,11,1,'#243b4c');
  for(let i=0;i<17;i++)px(20+i,22+i,2,2,'#b49d76');px(34,39,10,2,'#233b4d');px(40,41,5,1,'#162c3c');px(47,40,5,2,'#152c3e');
  if(!dcReduced())for(let i=0;i<24;i++){const sx=(i*113+time*.009*(1+i%3))%480,sy=(i*17+time*.006)%67;c.fillStyle='#d7f1ec70';c.fillRect(Math.floor(sx),Math.floor(sy),1,1);}
}
