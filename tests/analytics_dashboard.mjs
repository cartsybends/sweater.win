import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import worker from '../backend/src/index.mjs';
import {insightsBody,insightsScript} from '../backend/src/dashboard-view.mjs';
import {AnalyticsDB} from './helpers/analytics_runtime.mjs';

// Exercise the private UI with actual API aggregates, without a browser dependency.
const db=new AnalyticsDB(),env={DB:db,ALLOWED_ORIGINS:'https://sweater.win',SWEATER_ANALYTICS_PASSWORD:'test-only-dashboard-password-0000000000000'},realNow=Date.now;
Date.now=()=>Date.parse('2026-10-13T19:00:00Z');
const actor={visitor:crypto.randomUUID(),session:crypto.randomUUID(),visit:crypto.randomUUID()},round=crypto.randomUUID();
const event=(kind,extra={})=>({version:2,id:crypto.randomUUID(),...actor,mode:'hub',variant:'hub',kind,device:'mobile',browser:'duckduckgo',os:'ios',source:'instagram',campaign:'hockey-launch',medium:'social',theme:'dark',viewport:'small',build:'138',...extra});
async function call(path,body,cookie){const req=new Request('https://api.sweater.win'+path,{method:body===undefined?'GET':'POST',headers:{Origin:path==='/analytics/login'?'https://api.sweater.win':'https://sweater.win','Content-Type':'application/json',...(cookie?{Cookie:cookie}:{})},...(body===undefined?{}:{body:typeof body==='string'?body:JSON.stringify(body)})});Object.defineProperty(req,'cf',{value:{country:'CA'}});return worker.fetch(req,env,{});}
let report;
try{
  assert.equal((await call('/api/analytics/collect',{events:[event('site_visit'),event('page_view'),event('mode_open',{mode:'shoot',variant:'unlimited',from_mode:'hub'}),event('round_start',{mode:'shoot',variant:'unlimited',round}),event('round_step',{mode:'shoot',variant:'unlimited',round,step:1,correct:true,response_ms:1500})]})).status,200);
  assert.equal((await call('/api/analytics/collect',{events:[event('round_complete',{mode:'shoot',variant:'unlimited',round,won:true,step:1,elapsed_ms:2000,score:1}),event('engagement',{mode:'shoot',variant:'unlimited',active_ms:15000}),event('performance',{load_ms:1000,ttfb_ms:120,lcp_ms:1800,cls:.03}),event('error',{mode:'shoot',variant:'unlimited',action:'javascript',release:'0123456789ab',error_type:'TypeError',error_file:'app.html',error_line:4500,error_column:17,online:false}),event('interaction',{action:'team_select',team:'CGY'})]})).status,200);
  const auth=await call('/analytics/login','password='+encodeURIComponent(env.SWEATER_ANALYTICS_PASSWORD)),cookie=auth.headers.get('Set-Cookie').split(';')[0];
  const response=await call('/api/analytics/report?days=7',undefined,cookie);assert.equal(response.status,200);report=await response.json();
  const page=await call('/analytics',undefined,cookie);assert.equal(page.status,200);const html=await page.text();assert(html.includes('Your website, in detail'));assert(page.headers.get('Content-Security-Policy').includes("script-src 'nonce-"));assert(page.headers.get('Cache-Control').includes('no-store'));assert(!html.includes(env.SWEATER_ANALYTICS_PASSWORD));
}finally{Date.now=realNow;db.sql.close();}

class Element{
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.dataset={};this.style={};this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.checked=false;}
  appendChild(child){this.children.push(child);child.parent=this;return child;}
  removeChild(child){this.children.splice(this.children.indexOf(child),1);}
  replaceChildren(...children){this.children=children;}
  get lastChild(){return this.children.at(-1);}
  get options(){return this.children;}
  setAttribute(k,v){this.attributes[k]=String(v);}
  focus(){this.focused=true;}
  click(){this.onclick?.();}
}
function make(data=report){
  const elements=new Map(),tabs=[],intervals=new Map(),requests=[],downloads=[],clipboard=[],redirects=[];let reply=async()=>({ok:true,status:200,json:async()=>structuredClone(data)});
  for(const match of insightsBody.matchAll(/<(\w+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
    const [,tag,attrs,id]=match,el=new Element(tag);el.id=id;el.hidden=/\bhidden\b/.test(attrs);el.checked=/\bchecked\b/.test(attrs);el.disabled=/\bdisabled\b/.test(attrs);el.value=attrs.match(/\bvalue="([^"]*)"/)?.[1]||'';
    if(tag==='select'){const contents=insightsBody.slice(match.index+match[0].length).split('</select>')[0];for(const option of contents.matchAll(/<option([^>]*)>([^<]*)<\/option>/g)){const o=new Element('option');o.value=option[1].match(/value="([^"]*)"/)?.[1]||'';o.textContent=option[2];el.appendChild(o);if(option[1].includes('selected')||!el.value)el.value=o.value;}}
    const tab=attrs.match(/data-tab="([^"]+)"/)?.[1];if(tab){el.dataset.tab=tab;tabs.push(el);}elements.set(id,el);
  }
  const URLStub=class extends URL{static createObjectURL(blob){downloads.push(blob);return 'blob:test';}static revokeObjectURL(){}};
  const document={visibilityState:'visible',getElementById:id=>{assert(elements.has(id),'Rendered dashboard has control '+id);return elements.get(id);},querySelectorAll:()=>tabs,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  const context=vm.createContext({document,URL:URLStub,URLSearchParams,Blob,Intl,Date,location:{replace:path=>redirects.push(path)},navigator:{clipboard:{writeText:async text=>clipboard.push(text)}},
    setInterval:(fn,ms)=>intervals.set(ms,fn),setTimeout:()=>0,fetch:async(url,opts)=>{requests.push({url,opts});return reply(url);}});
  vm.runInContext(insightsScript,context);
  return {elements,tabs,intervals,requests,downloads,clipboard,redirects,document,context,$:id=>elements.get(id),reply:fn=>reply=fn};
}
const settle=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
const text=el=>el.textContent+el.children.map(text).join(' ');
const c=make();await settle();
assert(text(c.$('error-table')).includes('0123456789ab'));assert(text(c.$('error-table')).includes('TypeError'));assert(text(c.$('error-table')).includes('app.html:4500:17'));assert(text(c.$('error-table')).includes('Browser was offline'));
assert.equal(c.$('message').textContent,'');assert.equal(c.$('export-csv').disabled,false);assert.equal(c.$('refresh').disabled,false);assert.equal(c.$('overview-cards').children.length,4);assert.equal(c.$('secondary-cards').children.length,8);assert(text(c.$('game-table')).includes('Shootout'));assert(text(c.$('performance-table')).includes('120 ms'),'First-byte measurements keep millisecond precision');assert(text(c.$('retention-summary')).includes('Waiting for a full week'));
assert(c.$('date-to').max===report.today);assert(c.$('coverage').textContent==='');assert(c.$('activity-chart').children.filter(el=>el.tagName==='rect').length===7);assert(c.$('activity-heatmap').children.filter(el=>el.tagName==='rect').length===168);
for(const el of [...c.$('activity-chart').children,...c.$('activity-heatmap').children])for(const [key,value]of Object.entries(el.attributes))if(['x','y','width','height','fill-opacity'].includes(key))assert(Number.isFinite(Number(value)),'Chart geometry stays finite');
assert.equal(c.tabs[0].tabIndex,0);assert.equal(c.tabs[1].tabIndex,-1);let prevented=false;c.tabs[0].onkeydown({key:'ArrowRight',preventDefault:()=>prevented=true});assert(prevented);assert.equal(c.tabs[1].attributes['aria-selected'],'true');assert.equal(c.$('panel-games').hidden,false);assert.equal(c.$('panel-overview').hidden,true);assert(c.tabs[1].focused);
c.$('browser').value='duckduckgo';await c.$('browser').onchange();assert(new URL(c.requests.at(-1).url,'https://api.sweater.win').searchParams.get('browser')==='duckduckgo');assert.equal(c.requests.at(-1).opts.credentials,'same-origin');assert.equal(c.requests.at(-1).opts.cache,'no-store');
c.$('country').value='CA';c.reply(async()=>({ok:true,status:200,json:async()=>({...structuredClone(report),countries:[]})}));await c.$('country').onchange();assert.equal(c.$('country').value,'CA','A zero-result query preserves the selected country');
c.reply(async()=>({ok:true,status:200,json:async()=>structuredClone(report)}));const bar=c.$('activity-chart').children.find(el=>el.tagName==='rect');bar.onkeydown({key:'Enter',preventDefault(){}});await settle();assert.equal(c.$('period').value,'custom');assert.equal(c.$('date-from').value,c.$('date-to').value);assert.equal(c.$('from-field').hidden,false);assert(new URL(c.requests.at(-1).url,'https://api.sweater.win').searchParams.has('from'));
await c.$('reset-filters').onclick();assert.equal(c.$('country').value,'all');assert.equal(c.$('browser').value,'all');assert.equal(c.$('period').value,'7');
c.$('link-campaign').value='hockey-reel-october';c.$('link-source').value='instagram';c.$('link-medium').value='social';await c.$('copy-link').onclick();assert.equal(c.clipboard[0],'https://sweater.win/?utm_source=instagram&utm_medium=social&utm_campaign=hockey-reel-october');c.$('link-campaign').value='someone@example.com';await c.$('copy-link').onclick();assert.equal(c.clipboard.length,1,'Unsafe campaign labels cannot produce tracking links');
c.$('export-set').value='modes';c.$('export-csv').onclick();const csv=await c.downloads.at(-1).text();assert(csv.includes('\r\n'));assert(csv.includes('"period_from"'));assert(csv.includes('"Shootout"'));assert(!csv.includes('\\r\\n'));
c.$('export-json').onclick();assert.deepEqual(JSON.parse(await c.downloads.at(-1).text()),report,'JSON export contains the complete aggregate report');
const special=structuredClone(report);special.campaigns=[{campaign:'=HYPERLINK("bad")',source:'instagram',medium:'social',visits:1}];c.reply(async()=>({ok:true,status:200,json:async()=>special}));await c.$('refresh').onclick();c.$('export-set').value='campaigns';c.$('export-csv').onclick();assert((await c.downloads.at(-1).text()).includes('"\'=HYPERLINK(""bad"")"'),'CSV escapes quotes and spreadsheet formulas');
const before=c.requests.length;c.$('auto').checked=false;c.intervals.get(30000)();assert.equal(c.requests.length,before);c.$('auto').checked=true;c.document.visibilityState='hidden';c.intervals.get(30000)();assert.equal(c.requests.length,before);c.document.visibilityState='visible';c.intervals.get(30000)();await settle();assert.equal(c.requests.length,before+1,'Auto refresh runs only when enabled and visible');
c.reply(async()=>({ok:false,status:400,json:async()=>({error:'Invalid date range'})}));await c.$('refresh').onclick();assert.equal(c.$('message').textContent,'Invalid date range');assert.equal(c.$('refresh').disabled,false,'Failed refresh can be retried');
const race=make();await settle();const pending=[];race.reply(()=>new Promise(resolve=>pending.push(resolve)));const earlier=race.$('refresh').onclick(),later=race.$('refresh').onclick();pending[1]({ok:true,status:200,json:async()=>({...structuredClone(report),summary:{...report.summary,opens:99}})});await later;pending[0]({ok:true,status:200,json:async()=>({...structuredClone(report),summary:{...report.summary,opens:12}})});await earlier;assert(text(race.$('overview-cards')).includes('99'));assert(!text(race.$('overview-cards')).includes('12'),'An older response cannot overwrite the latest filters');
c.reply(async()=>({ok:false,status:401}));await c.$('refresh').onclick();assert.equal(c.redirects[0],'/analytics/login','Expired authentication returns to the existing login');

if(process.env.ANALYTICS_QA_DIR){fs.mkdirSync(process.env.ANALYTICS_QA_DIR,{recursive:true});for(const id of ['activity-chart','activity-heatmap']){const serialize=el=>'<'+el.tagName+' '+Object.entries(el.attributes).map(([k,v])=>k+'="'+v+'"').join(' ')+'>'+el.textContent+el.children.map(serialize).join('')+'</'+el.tagName+'>';const svg=c.$(id);svg.attributes.xmlns='http://www.w3.org/2000/svg';svg.attributes.viewBox=id==='activity-chart'?'0 0 1080 220':'0 0 704 226';fs.writeFileSync(process.env.ANALYTICS_QA_DIR+'/'+id+'.svg',serialize(svg));}}
console.log('Private dashboard: authenticated reports, all five sections, filters, date drill-down, accessible tabs, chart geometry, refresh races, campaign links, safe CSV/JSON and expired-session handling passed.');
