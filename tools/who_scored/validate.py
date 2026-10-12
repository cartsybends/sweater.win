"""Check shipped matching goal media; --decode verifies all encoded frames."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--decode',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parents[2]/'static'/'who-scored'
clips=json.loads((root/'clips.json').read_text());sources={s['id']:s for s in json.loads((root/'sources.json').read_text())}
assert len({c['id'] for c in clips})==len(clips) and len({c['pid'] for c in clips})==len(clips)
for c in clips:
    assert c['id'] in sources and c['source']==sources[c['id']]['source']
    pair=[]
    for kind in ['masked','reveal']:
        path=root/c[kind]
        streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']
        assert len(streams)==1,(c['id'],'unexpected audio/data')
        v=streams[0]
        assert (v['codec_name'],v['pix_fmt'],v['width'],v['height'],v['r_frame_rate'])==('h264','yuv420p',960,540,'24/1'),(c['id'],kind)
        pair.append((v['nb_frames'],v['duration']))
        raw=path.read_bytes();assert raw.index(b'moov')<raw.index(b'mdat')
        if args.decode:subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(path),'-f','null','-'],check=True)
    assert pair[0]==pair[1],(c['id'],'mismatched reveal')
    assert (root/c['poster']).is_file()
print(f'{len(clips)} distinct scorers: silent matching H.264 960x540/24fps video pairs and fast-start headers verified'+('; all frames decoded.' if args.decode else '.'))
