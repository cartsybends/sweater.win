"""Check shipped matching goal media; --decode verifies all encoded frames."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--decode',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parents[2]/'static'/'who-scored'
clips=json.loads((root/'clips.json').read_text());source_records=json.loads((root/'sources.json').read_text());sources={s['id']:s for s in source_records}
assert len({c['id'] for c in clips})==len(clips) and len({c['pid'] for c in clips})==len(clips)
assert len(sources)==len(source_records) and set(sources)=={c['id'] for c in clips}
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
    poster=root/c['poster'];assert poster.is_file()
    photo=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(poster)]))['streams'][0]
    assert (photo['width'],photo['height'])==(960,540),(c['id'],'poster dimensions')
    for kind,expected in sources[c['id']].get('exported_sha256',{}).items():
        assert hashlib.sha256((root/c[kind]).read_bytes()).hexdigest()==expected,(c['id'],kind,'checksum mismatch')
print(f'{len(clips)} distinct scorers: silent matching H.264 960x540/24fps video pairs and fast-start headers verified'+('; all frames decoded.' if args.decode else '.'))
