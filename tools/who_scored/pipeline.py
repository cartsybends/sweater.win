"""Prepare, track and render one manually verified scorer. Work dirs are immutable.

Usage: python pipeline.py prepare EDIT.json
       python pipeline.py track EDIT.json --checkpoint MODEL.pt --threads 2
       python pipeline.py render EDIT.json --output static/who-scored
"""
import argparse, hashlib, json, subprocess
from pathlib import Path

def frame_count(edit, full_window=False):
    original=round(edit['duration'] * 24)
    exported=edit.get('export_frames',original)
    if original<1 or type(exported) is not int or not 1<=exported<=original:
        raise ValueError('Export cap must be a positive frame count within the source window')
    finish=edit.get('scoring_play_end_frame')
    if finish is not None:
        if type(finish) is not int or not 0<=finish<original:
            raise ValueError('The reviewed scoring finish must be within the source window')
        if exported<=finish:
            raise ValueError('Export cap would cut off the reviewed scoring finish')
    return original if full_window else exported

def work_dir(path, edit):
    # A changed source, extraction window or crop gets fresh paths. export_frames
    # can shorten an already reviewed sequence; every output respects that cap.
    key = {k: edit.get(k) for k in ['id','original','start','duration','crop','source_sha256']}
    tag = hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()[:12]
    return path.parent / (edit['id']+'-'+tag)

def tracking_signature(edit):
    keys=['id','original','start','duration','crop','source_sha256','anchors','seed','allow_empty','max_cond_frames_in_attn']
    values={k:edit.get(k) for k in keys}
    if 'tracking_image_size' in edit:
        values['tracking_image_size']=edit['tracking_image_size']
    if 'tracking_crop_size' in edit:
        values['tracking_crop_size']=edit['tracking_crop_size']
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def tracking_crops(edit, count):
    """Follow manually identified scorer boxes for tracking, keeping exports full frame.

    A generous square around interpolated anchor centers gives small players enough
    model pixels. Every restored mask still needs the normal full-scene review.
    Off-screen padding keeps the coordinate transform identical at rink edges.
    """
    size=edit.get('tracking_crop_size')
    if size is None:return None
    if type(size) is not int or not 256<=size<=960:
        raise ValueError('Tracking crop size must be an integer between 256 and 960')
    anchors=sorted(edit['anchors'],key=lambda a:a['frame'])
    if not anchors or len({a['frame'] for a in anchors})!=len(anchors):
        raise ValueError('Cropped tracking requires distinct anchor frames')
    centers=[]
    for a in anchors:
        if not 0<=a['frame']<count or 'box' not in a:
            raise ValueError('Cropped tracking requires a scorer box on every anchor')
        x0,y0,x1,y1=a['box']
        if x1<=x0 or y1<=y0 or max(x1-x0,y1-y0)>size-32:
            raise ValueError('Tracking crop must leave room around the scorer box')
        centers.append((a['frame'],(x0+x1)/2,(y0+y1)/2))
    crops=[];right=0
    for frame in range(count):
        while right<len(centers)-1 and centers[right][0]<frame:right+=1
        after=centers[right];before=centers[max(0,right-1)]
        t=max(0,min(1,(frame-before[0])/(after[0]-before[0]))) if after[0]!=before[0] else 0
        cx=before[1]+(after[1]-before[1])*t;cy=before[2]+(after[2]-before[2])*t
        crops.append((round(cx-size/2),round(cy-size/2),size))
    return crops

def cropped_prompt(anchor, crop):
    x,y,size=crop;points=[];labels=[]
    for point,label in zip(anchor['points'],anchor.get('labels',[1]*len(anchor['points']))):
        px,py=point[0]-x,point[1]-y
        if not (0<=px<size and 0<=py<size):
            if label:raise ValueError('Positive scorer prompt is outside its tracking crop')
            continue
        points.append([px,py]);labels.append(label)
    if not any(labels):raise ValueError('Tracking crop needs a positive scorer prompt')
    result={'points':points,'labels':labels}
    if 'box' in anchor:
        x0,y0,x1,y1=anchor['box']
        result['box']=[max(0,x0-x),max(0,y0-y),min(size-1,x1-x),min(size-1,y1-y)]
    return result

def restore_tracking_mask(mask, crop):
    from PIL import Image
    x,y,size=crop
    if mask.size!=(size,size):raise ValueError('Tracking mask dimensions disagree with crop')
    restored=Image.new('L',(960,540));restored.paste(mask,(x,y))
    return restored

def prepare(path, edit):
    from PIL import Image, ImageDraw
    expected = edit.get('source_sha256')
    if not expected or hashlib.sha256(Path(edit['original']).read_bytes()).hexdigest() != expected:
        raise ValueError('Source checksum must match the verified edit before extracting frames')
    work=work_dir(path,edit);frames=work/'frames';frames.mkdir(parents=True,exist_ok=True)
    count=frame_count(edit,full_window=True)
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
    device = 'cuda' if args.device == 'auto' and torch.cuda.is_available() else ('cpu' if args.device == 'auto' else args.device)
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but this runner has no available CUDA device')
    max_conditioning = edit.get('max_cond_frames_in_attn', -1)
    if max_conditioning != -1 and (not isinstance(max_conditioning, int) or max_conditioning < 2):
        raise ValueError('SAM2 requires unlimited or at least two conditioning frames')
    image_size=edit.get('tracking_image_size',512)
    if type(image_size) is not int or image_size not in (512,1024):
        raise ValueError('Tracking image size must be 512 or 1024')
    predictor=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_t.yaml',args.checkpoint,
        device=device,apply_postprocessing=False,
        hydra_overrides_extra=[f'++model.image_size={image_size}','++model.fill_hole_area=0',
                              f'++model.max_cond_frames_in_attn={max_conditioning}'])
    count=frame_count(edit,full_window=True);start=time.time()
    crops=tracking_crops(edit,count);tracking_frames=work/'frames'
    if crops:
        tracking_frames=work/'tracking-frames';tracking_frames.mkdir(exist_ok=True)
        for i,(x,y,size) in enumerate(crops):
            with Image.open(work/'frames'/f'{i:05d}.jpg') as frame:
                frame.crop((x,y,x+size,y+size)).save(tracking_frames/f'{i:05d}.jpg',quality=95)
        (work/'tracking-crops.json').write_text(json.dumps(crops)+'\n')
    for name in ['mask-stats.json','tracking-complete.json']:(work/name).unlink(missing_ok=True)
    with torch.inference_mode():
        state=predictor.init_state(str(tracking_frames),offload_video_to_cpu=True,offload_state_to_cpu=True)
        for a in edit['anchors']:
            assert 0<=a['frame']<count
            prompt=cropped_prompt(a,crops[a['frame']]) if crops else a
            kw=dict(frame_idx=a['frame'],obj_id=1,points=np.array(prompt['points'],dtype=np.float32),
                labels=np.array(prompt.get('labels',[1]*len(prompt['points'])),dtype=np.int32))
            if 'box' in prompt:kw['box']=np.array(prompt['box'],dtype=np.float32)
            predictor.add_new_points_or_box(state,**kw)
        seed=edit.get('seed',edit['anchors'][0]['frame']);assert 0<=seed<count
        records={}
        allowed_empty=set(edit.get('allow_empty',[]))
        last_visible=max(i for i in range(count) if i not in allowed_empty)
        for reverse in [False,True]:
            if reverse and seed==0:continue
            limit=seed if reverse else last_visible-seed
            for i,ids,logits in predictor.propagate_in_video(state,start_frame_idx=seed,reverse=reverse,max_frame_num_to_track=limit):
                mask=logits[0,0].cpu().numpy()>0
                if crops:
                    mask=np.asarray(restore_tracking_mask(Image.fromarray(mask.astype(np.uint8)*255),crops[i]))>0
                # Empty frames are permitted only after a manually verified exit.
                if i in edit.get('allow_empty',[]):mask[:]=False
                Image.fromarray(mask.astype(np.uint8)*255).save(out/f'{i:05d}.png')
                ys,xs=np.where(mask)
                records[i]={'frame':i,'area':int(mask.sum()),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())] if len(xs) else None}
                if i%24==0:print(edit['id'],i,records[i]['area'],round(time.time()-start,1),flush=True)
        # Keep the full scoring finish when the camera follows the puck after
        # the scorer exits. Do not track a different skater in those frames.
        for i in range(last_visible+1,count):
            Image.new('L',(960,540)).save(out/f'{i:05d}.png')
            records[i]={'frame':i,'area':0,'bbox':None}
        assert len(records)==count
        (work/'mask-stats.json').write_text(json.dumps([records[i] for i in sorted(records)],indent=2)+'\n')
        (work/'tracking-complete.json').write_text(json.dumps({
            'tracking_signature':tracking_signature(edit),'frames':count,'device':device,
            'checkpoint_sha256':hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest()},indent=2)+'\n')
    print(edit['id'],count,'tracked',round(time.time()-start,1),'seconds',flush=True)

def render(path,edit,args):
    import cv2,numpy as np
    from PIL import Image,ImageDraw
    cv2.setNumThreads(1)
    work=work_dir(path,edit);count=frame_count(edit)
    stats=work/'mask-stats.json'
    if not stats.exists() or not set(range(count)) <= {row['frame'] for row in json.loads(stats.read_text())}:
        raise ValueError('Tracking must finish for every exported frame before rendering')
    completed=work/'tracking-complete.json'
    if completed.exists() and json.loads(completed.read_text())['tracking_signature']!=tracking_signature(edit):
        raise ValueError('Tracking prompts changed; retrack before rendering')
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
        # Keep the tracked matte pristine so changing a manual correction
        # never leaves a previous fill baked into subsequent renders.
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
    # JPEG inputs carry full-range metadata; explicitly convert and tag the
    # output range so reveals use the same browser format as masked PNGs.
    encode=['-vf','scale=in_range=auto:out_range=tv,format=yuv420p','-an','-c:v','libx264','-threads','1','-preset','medium','-crf','20','-pix_fmt','yuv420p','-color_range','tv','-movflags','+faststart']
    for src,dest in [(rendered/'%05d.png',masked),(work/'frames'/'%05d.jpg',reveal)]:
        subprocess.run(['ffmpeg','-v','error','-framerate','24','-i',str(src),'-frames:v',str(count),*encode,'-y',str(dest)],check=True)
        subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(dest),'-f','null','-'],check=True)
        v=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(dest)]))['streams']
        assert len(v)==1 and int(v[0]['nb_frames'])==count
        assert (v[0]['codec_name'],v[0]['pix_fmt'],v[0]['width'],v[0]['height'],v[0]['r_frame_rate'])==('h264','yuv420p',960,540,'24/1'),dest
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
    p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    args=p.parse_args();path=Path(args.edit).resolve();edit=json.loads(path.read_text())
    if args.action=='prepare':prepare(path,edit)
    elif args.action=='track':track(path,edit,args)
    else:render(path,edit,args)
