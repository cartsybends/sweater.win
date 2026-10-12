"""Read-only cross-check of completed worker clips against official NHL sources."""
import json,datetime,argparse
from pathlib import Path

def audit(work):
    sources={r['id']:r for r in json.loads((work/'goal-expansion/new-sources.json').read_text())}
    live=json.loads((work/'sweater-live/static/who-scored/clips.json').read_text())
    original=[c for c in live if int(c['id'].split('-')[1])<10]
    oldids={c['id'] for c in original};oldpids={c['pid'] for c in original}
    result={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_pool_ids':sorted(oldids),'original_pool_pids':sorted(oldpids),'workers':[],'errors':[]};seen=set()
    for path in sorted((work/'goal-expansion').glob('batch-*.json')):
        batch=json.loads(path.read_text());records={s['id']:s for s in batch['sources']};checks={s['id']:s for s in batch['checks']};items=[]
        for clip in batch['clips']:
            src=records[clip['id']];official=sources[clip['id']];problems=[]
            if clip['id'] in oldids or clip['pid'] in oldpids:problems.append('Overlaps original pool')
            if clip['id'] in seen:problems.append('Duplicate worker clip ID')
            seen.add(clip['id'])
            for key in ['pid','source']:
                if clip[key]!=official[key] or src[key]!=official[key]:problems.append(key+' mismatch')
            for key in ['player','source_video_id','game_id','team','jersey']:
                if src.get(key)!=official[key]:problems.append(key+' mismatch')
            if src.get('sha256')!=official['sha256']:problems.append('Original source SHA mismatch')
            edit=work/'goal-expansion/edits'/(clip['id']+'.json')
            if edit.exists():
                entry=json.loads(edit.read_text())
                if entry['player']!=official['player'] or entry['source_sha256']!=official['sha256']:problems.append('Edit identity/source SHA mismatch')
            if not checks.get(clip['id'],{}).get('correct_scorer'):problems.append('Correct scorer review not recorded')
            for key in ['masked','reveal','poster']:
                if not (work/'sweater-live/static/who-scored'/clip[key]).is_file():problems.append('Missing '+key)
                if not clip[key].startswith(clip['id']+'-'):problems.append('Wrong asset identity for '+key)
            items.append({'id':clip['id'],'pid':clip['pid'],'player':src['player'],'official_goal_scorer':official['source_goal_scorer'],'passed':not problems,'problems':problems})
            result['errors'] += [{'id':clip['id'],'error':error} for error in problems]
        result['workers'].append({'manifest':path.name,'completed':items,'pending':batch.get('pending',[])})
    result['completed_count']=len(seen)
    result['new_pool_scorers_unique']=len({s['pid'] for s in sources.values()})==30
    result['new_pool_original_pid_overlap']=sorted({s['pid'] for s in sources.values()}&oldpids)
    result['passed']=not result['errors'] and result['new_pool_scorers_unique'] and not result['new_pool_original_pid_overlap']
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,default=Path(__file__).resolve().parents[3]);args=parser.parse_args()
    result=audit(args.work);(args.work/'goal-expansion/source-identity-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'completed':result['completed_count'],'passed':result['passed'],'errors':result['errors']}))
