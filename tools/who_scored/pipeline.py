"""Prepare, track and render one manually verified scorer. Work dirs are immutable.

Usage: python pipeline.py prepare EDIT.json
       python pipeline.py track EDIT.json --checkpoint MODEL.pt --threads 2
       python pipeline.py render EDIT.json --output static/who-scored
"""
import argparse, hashlib, json, subprocess
from pathlib import Path

def frame_count(edit):
    return edit.get('export_frames', round(edit['duration'] * 24))

def work_dir(path, edit):
    # A changed source, trim or crop gets fresh paths; old tracked frames cannot
    # reappear in a revised export or be overwritten by an unfinished job.
    key = {k: edit.get(k) for k in ['id','original','start','duration','crop','source_sha256']}
    tag = hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()[:12]
    return path.parent / (edit['id']+'-'+tag)

def prepare(path, edit):
    from PIL import Image, ImageDraw
    work=work_dir(path,edit);frames=work/'frames';frames.mkdir(parents=True,exist_ok=True)
    count=frame_count(edit)
    vf='fps=24,scale=960:540'
    if 'crop' in edit:
        x,y,w,h=edit['crop']
        assert all(isinstance(v,int) for v in [x,y,w,h]) and x>=0 and y>=0 and w>0 and h>0 and x+w<=960 and y+h<=540
        vf+=f',crop={w}:{h}:{x}:{y},scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2'
    subprocess.run(['ffmpeg','-v','error','-threads','1','-ss',str(edit['start']),'-i',edit['original'],
        '-t',str(edit['duration']+1/24),'-frames:v',str(count),'-vf',vf,'-start_number','0',
        '-threads','1','-q:v','2','-y',str(frames/'%05d.jpg')],check=True)
    files=sorted(frames.glob('*.jpg'))[:count];assert len(files)==count
    indices=sorted(set([0,count-1]+list(range(0,count,12))))
    canvas=Image.new('RGB',(1440,((len(indices)+2)//3)*290),'#eee');draw=ImageDraw.Draw(canvas)
    for j,i in enumerate(indices):
        x,y=j%3*480,j//3*290
        canvas.paste(Image.open(files[i]).resize((480,270)),(x,y+20))
        draw.text((x+4,y+3),f'{edit["id"]} {edit["player"]}: {i} / {i/24:.2f}s',fill='black')
    canvas.save(work/'anchors.jpg')
    print(json.dumps({'work':str(work),'frames':count,'sheet':str(work/'anchors.jpg')}),flush=True)

def track(path,edit,args):
    import numpy as np
    import torch,time
    from PIL import Image
    from sam2.build_sam import build_sam2_video_predictor
    torch.set_num_threads(args.threads);torch.set_num_interop_threads(1)
    work=work_dir(path,edit);out=work/'masks';out.mkdir(exist_ok=True)
    predictor=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_t.yaml',args.checkpoint,
        device='cpu',apply_postprocessing=False,
        hydra_overrides_extra=['++model.image_size=512','++model.fill_hole_area=0'])
    count=frame_count(edit);start=time.time()
    with torch.inference_mode():
        state=predictor.init_state(str(work/'frames'),offload_video_to_cpu=True,offload_state_to_cpu=True)
        for a in edit['anchors']:
            assert 0<=a['frame']<count
            kw=dict(frame_idx=a['frame'],obj_id=1,points=np.array(a['points'],dtype=np.float32),
                labels=np.array(a.get('labels',[1]*len(a['points'])),dtype=np.int32))
            if 'box' in a:kw['box']=np.array(a['box'],dtype=np.float32)
            predictor.add_new_points_or_box(state,**kw)
        seed=edit.get('seed',edit['anchors'][0]['frame']);assert 0<=seed<count
        records={}
        for reverse in [False,True]:
            if reverse and seed==0:continue
            limit=seed if reverse else count-seed-1
            for i,ids,logits in predictor.propagate_in_video(state,start_frame_idx=seed,reverse=reverse,max_frame_num_to_track=limit):
                mask=logits[0,0].cpu().numpy()>0
                # Empty frames are permitted only after a manually verified exit.
                if i in edit.get('allow_empty',[]):mask[:]=False
                Image.fromarray(mask.astype(np.uint8)*255).save(out/f'{i:05d}.png')
                ys,xs=np.where(mask)
                records[i]={'frame':i,'area':int(mask.sum()),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())] if len(xs) else None}
                if i%24==0:print(edit['id'],i,records[i]['area'],round(time.time()-start,1),flush=True)
        assert len(records)==count
        (work/'mask-stats.json').write_text(json.dumps([records[i] for i in sorted(records)],indent=2)+'\n')
    print(edit['id'],count,'tracked',round(time.time()-start,1),'seconds',flush=True)

def render(path,edit,args):
    import cv2,numpy as np
    from PIL import Image,ImageDraw
    cv2.setNumThreads(1)
    work=work_dir(path,edit);count=frame_count(edit)
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    rendered=work/'rendered';rendered.mkdir(exist_ok=True)
    review=work/'review';review.mkdir(exist_ok=True)
    frames=sorted((work/'frames').glob('*.jpg'))[:count];assert len(frames)==count
    for old in review.glob('*.jpg'):old.unlink()
    records=[]
    for i,f in enumerate(frames):
        original=cv2.imread(str(f));mask=cv2.imread(str(work/'masks'/f'{i:05d}.png'),0)
        assert mask is not None
        if i in edit.get('allow_empty',[]):mask[:]=0
        for poly in edit.get('manual_clear_polygons',{}).get(str(i),[]):
            cv2.fillPoly(mask,[np.asarray(poly,dtype=np.int32)],0)
        for poly in edit.get('manual_fill_polygons',{}).get(str(i),[]):
            cv2.fillPoly(mask,[np.asarray(poly,dtype=np.int32)],255)
        for patch in edit.get('mask_patch_ellipses',[]):
            if patch['frame']==i:
                x,y,rx,ry=patch['ellipse'];cv2.ellipse(mask,(x,y),(rx,ry),0,0,360,255,-1)
        for patch in edit.get('mask_patch_lines',[]):
            if patch['frame']==i:
                x0,y0,x1,y1,width=patch['line'];cv2.line(mask,(x0,y0),(x1,y1),255,width)
        cv2.imwrite(str(work/'masks'/f'{i:05d}.png'),mask)
        assert mask.any() or i in edit.get('allow_empty',[]),(edit['id'],i,'empty matte')
        n,labels,stats,_=cv2.connectedComponentsWithStats((mask==0).astype(np.uint8),8)
        for c in range(1,n):
            x,y,w,h,area=stats[c]
            if area<50 and x>0 and y>0 and x+w<960 and y+h<540:mask[labels==c]=255
        mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
        alpha=cv2.GaussianBlur(mask.astype(np.float32)/255,(3,3),.45);alpha[mask==255]=1
        result=np.rint(original*(1-alpha[...,None])).astype(np.uint8)
        for x,y,w,h in edit.get('hide_rects',[]):result[y:y+h,x:x+w]=0
        assert (result[mask==255]==0).all()
        cv2.imwrite(str(rendered/f'{i:05d}.png'),result)
        records.append({'frame':i,'pixels':int((mask>0).sum()),'black_core':True})
    version=edit.get('version','v1');slug=edit['id']
    masked=out/f'{slug}-masked-{version}.mp4';reveal=out/f'{slug}-original-{version}.mp4';poster=out/f'{slug}-{version}.jpg'
    encode=['-an','-c:v','libx264','-threads','1','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart']
    for src,dest in [(rendered/'%05d.png',masked),(work/'frames'/'%05d.jpg',reveal)]:
        subprocess.run(['ffmpeg','-v','error','-framerate','24','-i',str(src),'-frames:v',str(count),*encode,'-y',str(dest)],check=True)
        subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(dest),'-f','null','-'],check=True)
        v=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(dest)]))['streams']
        assert len(v)==1 and int(v[0]['nb_frames'])==count
    cv2.imwrite(str(poster),cv2.imread(str(rendered/f'{edit.get("poster_frame",0):05d}.png')),[cv2.IMWRITE_JPEG_QUALITY,90])
    for batch in range((count+19)//20):
        canvas=Image.new('RGB',(1920,1024),'#eee');draw=ImageDraw.Draw(canvas)
        for j,i in enumerate(range(batch*20,min((batch+1)*20,count))):
            original=Image.open(frames[i]);silhouette=Image.open(rendered/f'{i:05d}.png')
            mask=cv2.imread(str(work/'masks'/f'{i:05d}.png'),0);ys,xs=np.where(mask)
            b=(max(0,int(xs.min())-30),max(0,int(ys.min())-24),min(960,int(xs.max())+31),min(540,int(ys.max())+25)) if len(xs) else (0,0,960,540)
            x,y=j%5*384,j//5*256;draw.text((x+4,y+3),f'{slug} {i}',fill='black')
            for k,im in enumerate([original,silhouette]):
                crop=im.crop(b);crop.thumbnail((188,144));canvas.paste(crop,(x+k*192+(192-crop.width)//2,y+20))
            silhouette.thumbnail((192,108));canvas.paste(silhouette,(x+96,y+148))
        canvas.save(review/f'{batch:02d}.jpg',quality=90)
    checks={'id':slug,'frames':count,'fps':24,'dimensions':[960,540],'audio':False,'frame_checks':records}
    (work/'render-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps({'id':slug,'frames':count,'seconds':count/24,'review':str(review),'masked':masked.name,'reveal':reveal.name,'poster':poster.name}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','track','render']);p.add_argument('edit')
    p.add_argument('--checkpoint');p.add_argument('--threads',type=int,default=2);p.add_argument('--output')
    args=p.parse_args();path=Path(args.edit).resolve();edit=json.loads(path.read_text())
    if args.action=='prepare':prepare(path,edit)
    elif args.action=='track':track(path,edit,args)
    else:render(path,edit,args)
