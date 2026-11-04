#!/usr/bin/env python3
"""Export a self-contained, offline-playable Deep Cut preview (no NHL fetch)."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ADAPTER = r"""
const $=id=>document.getElementById(id),G={},S={deepcut:{target:null,guesses:[],opts:{},over:false,day:null}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const store={get(k){try{return JSON.parse(localStorage.getItem('dc-preview:'+k));}catch{return null;}},set(k,v){try{localStorage.setItem('dc-preview:'+k,JSON.stringify(v));}catch{}}};
const pick=a=>a[Math.floor(Math.random()*a.length)];
function hash(str){let h=2166136261;for(const c of str){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
function dayKey(){return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
const SITE='',game='deepcut',onHub=false;let mode='daily';
const dailyNumber=(g,d)=>Math.max(1,Math.round((Date.parse(d+'T12:00:00Z')-Date.parse(START+'T12:00:00Z'))/86400000)+1);
function toast(text){$('previewToast').textContent=text;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('previewToast').textContent='',2400);}
function saveProgress(){const st=S.deepcut;if(st.target)store.set(mode==='daily'?'daily:'+st.day:'practice',{target:st.target.id,guesses:st.guesses,opts:st.opts});}
function doGuess(action){const st=S.deepcut,g=G.deepcut;if(st.over||g.guess(st.target,action)===null)return;st.guesses.push(action);st.over=g.isDone(st.target,st.guesses);saveProgress();g.render(st.target,st);}
function startGame(t,saved){const st=S.deepcut,g=G.deepcut;g.reset();st.target=t;st.guesses=[];st.over=false;st.day=dayKey();st.opts=saved?.target===t.id?saved.opts||{}:{};g.prepareTarget(t,st.opts);if(saved?.target===t.id&&Array.isArray(saved.guesses)){try{DEEP_CUT_MODEL.state(t,saved.guesses,DEEP_CUT_DATA);st.guesses=saved.guesses;st.over=g.isDone(t,st.guesses);}catch{}}g.render(t,st);saveProgress();}
function loadDaily(){mode='daily';startGame(G.deepcut.daily(dayKey()),store.get('daily:'+dayKey()));}
function loadUnlimited(fresh=false){mode='unlimited';const old=store.get('practice'),last=old&&G.deepcut.pool().find(t=>t.id===old.target);let target=last;if(fresh||!target){do{target=G.deepcut.random();}while(last&&target.id===last.id);}startGame(target,fresh?null:old);}
async function copyToClipboard(text,message){if(location.protocol==='file:')text=text.replace(/\n\nfile:[\s\S]*$/,'');try{await navigator.clipboard.writeText(text);toast(message);return true;}catch{const el=document.createElement('textarea');el.value=text;document.body.append(el);el.select();let ok=false;try{ok=document.execCommand('copy');}catch{}el.remove();toast(ok?message:'Copy was unavailable in this browser');return ok;}}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="work/deep-cut.html")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("sweater", ROOT / "build_sweater.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    root = ROOT / "static/deep-cut"
    bank = builder.load_deep_cut_data()
    schedule = json.loads((ROOT / "schedule.json").read_text())
    today = builder.eastern_today()
    days = builder.plan_community_days(schedule.get("deepcut_days", {}), bank["runs"], today, "deepcut")
    start = schedule.get("deepcut_start", today.isoformat())
    data = json.dumps(bank, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css = (root / "styles.css").read_text().replace("deep-cut/pixel.ttf", "data:font/ttf;base64," + base64.b64encode((root / "pixel.ttf").read_bytes()).decode())
    view = (root / "view.html").read_text().replace('id="view-deepcut" hidden', 'id="view-deepcut"')
    model = (root / "model.mjs").read_text().replace("export const DEEP_CUT_MODEL", "const DEEP_CUT_MODEL")
    scenery = (root / "scenery.mjs").read_text().replace("export const DEEP_CUT_SCENERY", "const DEEP_CUT_SCENERY")
    game = (root / "game.js").read_text().replace("/*__DEEP_CUT_DATA__*/{}", data)
    boot = "const START=" + json.dumps(start) + ",DAILY={deepcut:" + json.dumps(days) + "};\n"
    html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Deep Cut · Sweater playable preview</title><meta name="description" content="Seven NHL prompts. Rare names score more. Play Sweater Deep Cut."><style>html{background:#050e17;color:#e9f5ff}body{margin:0;padding:24px 16px;font-family:monospace}*{box-sizing:border-box}[hidden]{display:none!important}.preview-label{max-width:980px;margin:0 auto 16px;font-size:10px;letter-spacing:.08em;color:#9aafc4}.preview-label span{color:#81f2df}.preview-toast{position:fixed;bottom:15px;left:50%;transform:translateX(-50%);color:#e9f5ff;background:#152a3b;font:12px monospace;padding:12px;z-index:10;box-shadow:0 3px 20px #0006;max-width:90vw}.preview-toast:empty{display:none}' + css + '</style></head><body><p class="preview-label"><span>SWEATER / DEEP CUT</span> · PLAYABLE PREVIEW</p>' + view + '<p class="preview-toast" id="previewToast" role="status"></p><script>' + boot + ADAPTER + model + scenery + game + '\nloadDaily();\n</script></body></html>'
    html = html.replace("z-index:10;box-shadow", "z-index:60;box-shadow")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Playable preview: {out} ({len(html):,} characters)")


if __name__ == "__main__": main()
