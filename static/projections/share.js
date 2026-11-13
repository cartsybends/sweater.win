const PP_SWEATER_MARK='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#171719"/><path d="M27 11H17a5 5 0 0 0 0 10h6a4 4 0 0 1 0 8H12" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/><path d="M12 35h16" stroke="#8055ff" stroke-width="3"/></svg>';
const ppImageCache=new Map(),ppExportCache=new Map(),ppCrestCache=new Map();
let ppPrepared=null,ppPreviewURL='',ppPreviewSnapshot=null,ppPreviewBlob=null;
$('ppCardBrand').innerHTML=PP_SWEATER_MARK+'<span>sweater.win</span>';

function ppShareSnapshot(){
 const p=ppCurrent();if(!p)return null;
 return ppSharing.normalize({v:1,mode:ppState.mode,player:p,start:ppShared?.start||PROJECTION_DATA.start||2026,asof:ppState.mode==='manual'?null:ppShared?.asof||PROJECTION_DATA.asof||null,checkedAt:ppState.mode==='manual'?null:ppSnapshotChecked(),seasonGames:ppState.seasonGames,rate:ppState.rate,missed:ppState.missed});
}
function ppShareURL(snapshot){const url=new URL(SITE||location.href);url.search='';url.hash=ppSharing.hash(snapshot);return url.href;}
function ppCloseShare(focus=false){$('ppShareMenu').hidden=true;$('ppShareToggle').setAttribute('aria-expanded','false');if(focus)$('ppShareToggle').focus();}
function ppAdjustmentText(snapshot){const rate=snapshot?.rate??100,missed=snapshot?.missed??0,parts=[];if(rate!==100)parts.push(`${Math.abs(rate-100)}% ${rate>100?'more':'less'} scoring from now`);if(missed)parts.push(`${missed} future ${missed===1?'game':'games'} missed`);return parts.join(' · ')||'At the current scoring rate';}
function ppRecordText(p){const values=[p?.gp,p?.goals,p?.assists].map(ppModel.number),point=values[1]+values[2];return [...values,point].map((n,i)=>`${Number.isInteger(n)&&n>=0?n:'—'} ${['GP','G','A','PTS'][i]}`).join(' · ');}
function ppRenderShare(p,r,manual){
 const snapshot=ppShareSnapshot(),start=snapshot?.start||PROJECTION_DATA.start||2026;
 $('ppShareToggle').disabled=!r.valid;$('ppShareStatus').textContent='';if(!r.valid)ppCloseShare();
 $('ppSharedNotice').hidden=!ppShared;$('ppSharedNotice').querySelector('span').textContent=manual?'Viewing shared calculator settings.':'Viewing a shared stat snapshot.';$('ppUseLatest').hidden=manual;
 $('ppCardKicker').textContent=`${start}–${String(start+1).slice(-2)} POINT PROJECTION`;
 $('ppCardTeam').textContent=p?(manual?'Your numbers':p.team?teamFullName(p.team):'NHL skater'):'Choose an NHL skater';$('ppCardRecord').textContent=ppRecordText(p);
 $('ppAdjustment').textContent=ppAdjustmentText(ppState);$('ppAdjustment').classList.toggle('adjusted',ppState.rate!==100||ppState.missed>0);
 const identity=manual?'manual':String(p?.id||'empty');
 if($('ppCardPortrait').dataset.player!==identity){
  $('ppCardPortrait').dataset.player=identity;
  const initials=p?.name.split(' ').map(s=>s[0]).slice(0,2).join('')||'?';
  $('ppCardPortrait').innerHTML=manual?uiIcon('chart'):`<span>${esc(initials)}</span>${p?`<img src="projection-headshots/${p.id}.webp" alt="" onload="this.previousElementSibling.hidden=true" onerror="this.remove()">`:''}`;
 }
 const team=!manual&&p?.team&&Object.hasOwn(TEAMS,p.team)?p.team:null;
 $('ppTeamArt').hidden=!team;if(team&&$('ppTeamArt').dataset.team!==team){$('ppTeamArt').dataset.team=team;$('ppTeamArt').src=`team-logos/${team}.svg`;ppLoadCrest(team).then(img=>{if(img&&$('ppTeamArt').dataset.team===team)$('ppTeamArt').src=img.src;});}
 $('ppCardFootnote').textContent=manual?'Projection estimate · manual calculator':`Projection estimate · ${ppCheckedLabel(snapshot?.checkedAt,snapshot?.asof||'')}`;
 if(!$('ppShareMenu').hidden)ppCloseShare();
}
function ppLoadImage(src){
 if(ppImageCache.has(src))return ppImageCache.get(src);
 const promise=new Promise(resolve=>{
  const img=new Image();let done=false;
  const finish=value=>{if(done)return;done=true;clearTimeout(timer);img.onload=img.onerror=null;resolve(value);};
  const timer=setTimeout(()=>finish(null),8000);img.crossOrigin='anonymous';img.onload=()=>finish(img);img.onerror=()=>finish(null);img.src=src;
 });
 ppImageCache.set(src,promise);if(ppImageCache.size>32)ppImageCache.delete(ppImageCache.keys().next().value);return promise;
}
function ppLoadCrest(team){
 if(ppCrestCache.has(team))return ppCrestCache.get(team);
 const promise=ppLoadImage(`team-logos/${team}.svg`).then(image=>{
  if(!image)return null;
  // Remove only transparent padding from the official SVG, keeping the full crest.
  const c=document.createElement('canvas');c.width=960;c.height=640;const ctx=c.getContext('2d');ctx.drawImage(image,0,0,960,640);
  const pixels=ctx.getImageData(0,0,960,640).data;let left=960,top=640,right=-1,bottom=-1;
  for(let y=0;y<640;y++)for(let x=0;x<960;x++)if(pixels[(y*960+x)*4+3]){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
  if(right<left)return image;
  const cropped=document.createElement('canvas');cropped.width=right-left+1;cropped.height=bottom-top+1;cropped.getContext('2d').drawImage(c,left,top,cropped.width,cropped.height,0,0,cropped.width,cropped.height);
  return ppLoadImage(cropped.toDataURL('image/png'));
 }).catch(()=>null);
 ppCrestCache.set(team,promise);if(ppCrestCache.size>12)ppCrestCache.delete(ppCrestCache.keys().next().value);return promise;
}
function ppRoundRect(ctx,x,y,w,h,r,fill){ctx.beginPath();if(ctx.roundRect)ctx.roundRect(x,y,w,h,r);else ctx.rect(x,y,w,h);if(fill){ctx.fillStyle=fill;ctx.fill();}}
function ppDrawContain(ctx,img,x,y,w,h,center=false){if(!img)return;const scale=Math.min(w/img.width,h/img.height),dw=img.width*scale,dh=img.height*scale;ctx.drawImage(img,x+(w-dw)/2,y+(center?(h-dh)/2:h-dh),dw,dh);}
function ppPalette(){const card=getComputedStyle($('ppScorecard')),tile=$('ppScorecard').querySelector('.pp-projected-stats>div');return {background:card.backgroundColor,foreground:card.color,muted:getComputedStyle($('ppCardTeam')).color,accent:getComputedStyle(tile.querySelector('span')).color,cell:getComputedStyle(tile).backgroundColor,portrait:getComputedStyle($('ppCardPortrait')).backgroundColor,dark:isDark()};}
const ppExportKey=(snapshot,palette=ppPalette())=>JSON.stringify({snapshot,palette});
async function ppDrawExport(snapshot,palette=ppPalette()){
 const p=snapshot.player,r=ppModel.calculate({...p,...snapshot}),manual=snapshot.mode==='manual',height=920;
 const [portrait,crest,mark]=await Promise.all([manual?null:ppLoadImage(`projection-headshots/${p.id}.webp`),p.team?ppLoadCrest(p.team):null,ppLoadImage('data:image/svg+xml,'+encodeURIComponent(PP_SWEATER_MARK.replace('#8055ff',palette.accent)))]);
 const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=height;const ctx=canvas.getContext('2d');
 ppRoundRect(ctx,0,0,1200,height,36,palette.background);ctx.save();ctx.clip();
 if(crest){ctx.globalAlpha=palette.dark ? 0.045 : 0.05;ppDrawContain(ctx,crest,60,45,1080,height-90,true);ctx.globalAlpha=1;}
 ctx.restore();
 const text=(value,x,y,size=22,color=palette.foreground,weight=500,align='left')=>{ctx.font=`${weight} ${size}px Arial, sans-serif`;ctx.textAlign=align;ctx.fillStyle=color;ctx.fillText(String(value),x,y);};
 const fit=(value,max,size,min=24)=>{for(;size>min;size--){ctx.font=`750 ${size}px Arial, sans-serif`;if(ctx.measureText(value).width<=max)break;}return size;};
 ppRoundRect(ctx,60,70,156,156,78,palette.portrait);ctx.save();ctx.clip();
 if(portrait)ppDrawContain(ctx,portrait,60,70,156,156);else if(manual){ctx.strokeStyle=palette.accent;ctx.lineWidth=9;[47,75,105].forEach((v,i)=>{ctx.beginPath();ctx.moveTo(104+i*30,188);ctx.lineTo(104+i*30,188-v);ctx.stroke();});}else text(p.name.split(' ').map(v=>v[0]).slice(0,2).join(''),138,166,50,palette.accent,700,'center');
 ctx.restore();
 text(`${snapshot.start}–${String(snapshot.start+1).slice(-2)}  ·  POINT PROJECTION`,244,92,20,palette.accent,600);
 text(p.name,242,155,fit(p.name,900,58),palette.foreground,750);
 text(manual?'Your numbers':p.team?teamFullName(p.team):'NHL skater',244,197,26,palette.muted);
 text(ppRecordText(p),244,238,25,palette.muted);
 text(`${r.seasonGames}-game projection`,62,326,28,palette.foreground,600);
 text(ppAdjustmentText(snapshot),62,369,24,snapshot.rate!==100||snapshot.missed?palette.accent:palette.muted);
 const points=ppFmt(r.finish.points),size=fit(points,750,190,80);text(points,54,555,size,palette.foreground,750);
 ctx.font=`750 ${size}px Arial, sans-serif`;const pw=ctx.measureText(points).width;text('POINTS',Math.min(830,70+pw),550,22,palette.muted,600);
 text(ppRate(r.ppg),1138,519,40,palette.foreground,650,'right');text('CURRENT P/GP',1138,552,19,palette.muted,500,'right');
 [['Projected goals',r.finish.goals],['Projected assists',r.finish.assists]].forEach(([label,n],i)=>{const x=60+i*552;ppRoundRect(ctx,x,605,528,155,16,palette.cell);text(label,x+26,649,27,palette.accent,600);text(ppFmt(n),x+26,731,fit(ppFmt(n),475,72),palette.foreground,650);});
 if(mark)ctx.drawImage(mark,60,826,44,44);text('sweater.win',116,858,30,palette.foreground,700);
 text('PROJECTION ESTIMATE · REGULAR SEASON',1138,839,15,palette.muted,500,'right');text(manual?'Manual calculator':`Stats checked · ${ppCheckedLabel(snapshot.checkedAt,snapshot.asof||'date unavailable')}`,1138,869,16,palette.muted,500,'right');
 return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Image export failed')),'image/png'));
}
function ppGetExport(snapshot){const palette=ppPalette(),key=ppExportKey(snapshot,palette);if(!ppExportCache.has(key)){ppExportCache.set(key,ppDrawExport(snapshot,palette));if(ppExportCache.size>2)ppExportCache.delete(ppExportCache.keys().next().value);}return ppExportCache.get(key);}
function ppWarmExport(snapshot){
 const key=ppExportKey(snapshot);$('ppNativeShare').disabled=true;
 ppGetExport(snapshot).then(blob=>{if(ppExportKey(ppShareSnapshot())===key){ppPrepared={key,blob};$('ppNativeShare').disabled=false;}}).catch(()=>{});
}
function ppSaveImage(blob,snapshot){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=ppSharing.filename(snapshot);document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
function ppShowImage(blob,snapshot,message){
 if(ppPreviewURL)URL.revokeObjectURL(ppPreviewURL);ppPreviewURL=URL.createObjectURL(blob);ppPreviewSnapshot=snapshot;ppPreviewBlob=blob;
 $('ppImagePreview').src=ppPreviewURL;$('ppImageMessage').textContent=message;if(!$('ppImageDialog').open)$('ppImageDialog').showModal();
}
async function ppShareAction(action){
 const snapshot=ppShareSnapshot();if(!snapshot)return;
 ppCloseShare();
 if(action==='link'){await copyToClipboard(ppShareURL(snapshot),'Projection link copied');return;}
 if(action==='native'){
  if(ppPrepared?.key!==ppExportKey(snapshot)){$('ppShareStatus').textContent='The image is preparing. Open Share and try again in a moment.';return;}
  try{await navigator.share({files:[new File([ppPrepared.blob],ppSharing.filename(snapshot),{type:'image/png'})],title:`${snapshot.player.name} · Point Projections`});}catch(error){if(error.name!=='AbortError')ppShowImage(ppPrepared.blob,snapshot,'Save this image to share it with your friends.');}return;
 }
 const image=ppGetExport(snapshot);$('ppShareStatus').textContent='Preparing your image…';
 try{
  if(action==='copy'&&navigator.clipboard?.write&&globalThis.ClipboardItem){
   // Start the clipboard write during the click, before awaiting image loading (Safari).
   try{await navigator.clipboard.write([new ClipboardItem({'image/png':image})]);$('ppShareStatus').textContent='';toast('Projection image copied');return;}catch{}
  }
  const blob=await image;$('ppShareStatus').textContent='';
  if(action==='save'){ppSaveImage(blob,snapshot);toast('Projection image ready to save');}else ppShowImage(blob,snapshot,'Image copy isn’t available here. Save the image, or touch and hold it to send it to a friend.');
 }catch{$('ppShareStatus').textContent='The image could not be prepared. Please try again.';}
}
$('ppShareToggle').onclick=e=>{
 const open=$('ppShareMenu').hidden;$('ppShareMenu').hidden=!open;$('ppShareToggle').setAttribute('aria-expanded',String(open));
 if(open){const snapshot=ppShareSnapshot();if(snapshot)ppWarmExport(snapshot);if(e.detail===0)$('ppShareMenu').querySelector('button').focus();}
};
$('ppShareMenu').onclick=e=>{const b=e.target.closest('[data-pp-share]');if(b)ppShareAction(b.dataset.ppShare);};
document.addEventListener('click',e=>{if(!e.target.closest('.pp-share-wrap'))ppCloseShare();});
$('ppShareMenu').parentElement.addEventListener('keydown',e=>{
 if(e.key==='Escape'){e.preventDefault();e.stopPropagation();ppCloseShare(true);return;}
 if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;e.preventDefault();
 $('ppShareMenu').hidden=false;$('ppShareToggle').setAttribute('aria-expanded','true');
 const buttons=[...$('ppShareMenu').querySelectorAll('button')].filter(b=>!b.hidden&&!b.disabled),index=buttons.indexOf(document.activeElement);
 const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowUp'?-1:1)+buttons.length)%buttons.length;buttons[next]?.focus();
});
try{$('ppNativeShare').hidden=!(navigator.share&&navigator.canShare?.({files:[new File([''], 'projection.png',{type:'image/png'})]}));}catch{$('ppNativeShare').hidden=true;}
$('ppImageClose').onclick=()=>$('ppImageDialog').close();$('ppImageSave').onclick=()=>{if(ppPreviewBlob&&ppPreviewSnapshot)ppSaveImage(ppPreviewBlob,ppPreviewSnapshot);};
$('ppImageDialog').addEventListener('close',()=>{if(ppPreviewURL)URL.revokeObjectURL(ppPreviewURL);ppPreviewURL='';ppPreviewSnapshot=null;ppPreviewBlob=null;$('ppImagePreview').removeAttribute('src');$('ppShareToggle').focus();});
$('ppUseLatest').onclick=()=>{if(ppShared&&!ppPlayers.has(ppShared.player.id)){toast('Current-season stats are unavailable for this player. Choose another skater above.');return;}ppDropShared();ppRender();ppSave();};

const ppSliderStops=[];
function ppStopSliderDrags(){ppSliderStops.forEach(stop=>stop());}
// Drag from anywhere on either scenario track, including touch. Native keys still work.
for(const id of ['ppRate','ppMissed']){
 const range=$(id);let pointer=null;
 const stop=()=>{const active=pointer;pointer=null;if(active!==null&&range.hasPointerCapture(active))range.releasePointerCapture(active);};
 ppSliderStops.push(stop);
 const update=e=>{const rect=range.getBoundingClientRect(),inset=8,ratio=Math.max(0,Math.min(1,(e.clientX-rect.left-inset)/(rect.width-2*inset))),step=Number(range.step)||1;range.value=Number(range.min)+Math.round(ratio*(Number(range.max)-Number(range.min))/step)*step;range.dispatchEvent(new Event('input',{bubbles:true}));};
 range.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();stop();pointer=e.pointerId;range.focus({preventScroll:true});range.setPointerCapture(pointer);update(e);});
 range.addEventListener('pointermove',e=>{if(e.pointerId!==pointer)return;if(!range.hasPointerCapture(pointer)||e.pointerType!=='touch'&&!(e.buttons&1)){stop();return;}update(e);});
 for(const event of ['pointerup','pointercancel','lostpointercapture'])range.addEventListener(event,e=>{if(e.pointerId===pointer)stop();});
 for(const event of ['pointerup','pointercancel'])window.addEventListener(event,e=>{if(e.pointerId===pointer)stop();},true);
 window.addEventListener('blur',stop);document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
}
