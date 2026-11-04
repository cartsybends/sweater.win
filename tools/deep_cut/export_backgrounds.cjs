#!/usr/bin/env node
// Render the actual game scenery; Playwright is an optional development tool.
const {chromium}=require(process.env.SWEATER_PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const arg=(name,fallback)=>{const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1];};
const out=path.resolve(arg('--out',path.join(__dirname,'../../static/deep-cut/backgrounds')));
const url=arg('--url','http://127.0.0.1:8765/#deepcut'),origin=new URL(url).origin;
const levels=[['neighbourhood-rink','The neighbourhood rink','0–149 points'],['community-arena','The community arena','150–299 points'],['big-leagues','The big leagues','300–449 points'],['rafters','Up in the rafters','450–599 points'],['legends','Legends only','600–700 points']];
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.SWEATER_CHROMIUM_PATH?{executablePath:process.env.SWEATER_CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
  await page.route('**/*',route=>{const request=route.request().url();return request.startsWith(origin+'/')||request.startsWith('data:')?route.continue():route.abort();});
  await page.addInitScript(()=>localStorage.setItem('sweater-seen-welcome','true'));
  await page.goto(url,{waitUntil:'load'});
  const images=[];
  for(const [zone,[slug,name,points]] of levels.entries()){
   const uri=await page.evaluate(zone=>{
    dcAnimation=null;dcOffset=0;dcVisualDistance=zone*1500;dcClearRinkParticles();dcDraw(0,{backgroundOnly:true});
    const canvas=document.createElement('canvas');canvas.width=1440;canvas.height=900;
    const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(document.getElementById('dcCanvas'),0,0,1440,900);return canvas.toDataURL('image/png');
   },zone);
   fs.writeFileSync(path.join(out,`${zone+1}-${slug}.png`),Buffer.from(uri.split(',')[1],'base64'));images.push({uri,name,points});
  }
  await page.setViewportSize({width:1440,height:1700});
  await page.setContent(`<html><head><style>*{box-sizing:border-box}body{margin:0;background:#071420;color:#e8f6f3;font:16px ui-monospace,monospace;padding:40px}h1{font-size:28px;margin:0 0 12px}header p{color:#9db6c4;margin:0 0 28px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}figure{margin:0;border:1px solid #3d5866;border-radius:4px;overflow:hidden;background:#0d2231}figcaption{padding:16px;display:flex;justify-content:space-between;gap:15px}figcaption span{font-size:14px;color:#9db6c4}img{width:100%;display:block;image-rendering:pixelated}</style></head><body><header><h1>DEEP CUT · THE FIVE RINKS</h1><p>Backgrounds without game controls or the skater · unlocked by total points</p></header><div class="grid">${images.map(({uri,name,points},i)=>`<figure><figcaption><strong>0${i+1} / ${name}</strong><span>${points}</span></figcaption><img src="${uri}" alt="${name}"></figure>`).join('')}</div></body></html>`);
  await page.screenshot({path:path.join(out,'all-five-backgrounds.png'),fullPage:true});
  execFileSync('python3',['-c',`from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys
root=Path(sys.argv[1])
with ZipFile(root/'deep-cut-backgrounds.zip','w',ZIP_DEFLATED) as archive:
 for file in sorted(root.glob('*.png')): archive.write(file,file.name)
 archive.writestr('Background levels.txt','Deep Cut backgrounds\\n\\n1. Neighbourhood rink: 0-149 points\\n2. Community arena: 150-299 points\\n3. Big leagues: 300-449 points\\n4. Rafters: 450-599 points\\n5. Legends: 600-700 points\\n\\nIndividual images are 1440 x 900 pixels. Game controls, the skater and click effects are omitted. Spectators are seated and animations are frozen for these still images.\\n')
`,out]);
  console.log('Exported five 1440×900 backgrounds, labelled overview and ZIP:',out);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
