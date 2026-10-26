"""Pillow review sheets, lossless reference comparison and offline GLB viewer."""
import argparse,base64,hashlib,html,json,mimetypes,os,re,shutil,struct,zipfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text('utf-8-sig'))
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
def uri(path):return 'data:'+(mimetypes.guess_type(str(path))[0] or 'application/octet-stream')+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()
def js_json(value):return json.dumps(value).replace('<','\\u003c')
def contained_file(root,relative):
    root=Path(root).resolve();path=(root/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):raise ValueError('Artifact path escaped its declared directory: '+str(relative))
    return path

def check_glb(path):
    data=Path(path).read_bytes()
    if data[:4]!=b'glTF':raise ValueError('Not a GLB.')
    size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);compression={'KHR_draco_mesh_compression','EXT_meshopt_compression','KHR_texture_basisu'}&set(doc.get('extensionsUsed',[]))
    if compression:raise ValueError('Local decoder not bundled for '+repr(compression)+'; export a plain GLB first.')
    if any('uri' in b for b in doc.get('buffers',[])):raise ValueError('GLB has an external buffer.')
    if any('uri' in i and not i['uri'].startswith('data:') for i in doc.get('images',[])):raise ValueError('GLB has external/remote textures; embed them first.')
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'parts':len(doc.get('meshes',[])),'skins':len(doc.get('skins',[])),'animations':len(doc.get('animations',[]))}

def font_choice(path,size):
    system_root=os.environ.get('WINDIR') or os.environ.get('SystemRoot')
    system_fonts=[str(Path(system_root)/'Fonts/msyh.ttc')] if system_root else []
    candidates=[path] if path else system_fonts+['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for item in candidates:
        if item and Path(item).is_file():return ImageFont.truetype(item,size),bool(path or 'msyh' in item or 'CJK' in item)
    return ImageFont.load_default(),False

SCRIPT=r'''const canvas=document.getElementById('compare'),ctx=canvas.getContext('2d'),range=document.getElementById('blendRange'),status=document.getElementById('blendStatus');const src=new Image(),model=new Image();let ready=false,mode='fade',playing=false,raf=0,start=0;let region=[0,0,canvas.width,canvas.height];function stop(){playing=false;cancelAnimationFrame(raf);document.getElementById('play').textContent='自动渐变'}function draw(){if(!ready)return;const p=Number(range.value),[x,y,w,h]=region,z=Math.min(canvas.width/w,canvas.height/h),dw=w*z,dh=h*z,dx=(canvas.width-dw)/2,dy=(canvas.height-dh)/2;ctx.globalAlpha=1;ctx.fillStyle=BACKGROUND;ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(src,x,y,w,h,dx,dy,dw,dh);if(mode==='fade'){ctx.globalAlpha=p/100;ctx.drawImage(model,x,y,w,h,dx,dy,dw,dh);ctx.globalAlpha=1}else{ctx.save();ctx.beginPath();ctx.rect(dx,dy,dw*p/100,dh);ctx.clip();ctx.drawImage(model,x,y,w,h,dx,dy,dw,dh);ctx.restore();ctx.strokeStyle='#416335';ctx.beginPath();ctx.moveTo(dx+dw*p/100,dy);ctx.lineTo(dx+dw*p/100,dy+dh);ctx.stroke()}status.textContent=(100-p)+'% 原图 · '+p+'% 模型';canvas.dataset.percent=p;canvas.dataset.mode=mode}function loaded(){if(src.naturalWidth&&model.naturalWidth){ready=true;canvas.dataset.ready='true';draw()}}range.oninput=()=>{stop();draw()};document.querySelectorAll('[data-blend]').forEach(b=>b.onclick=()=>{stop();mode='fade';range.value=b.dataset.blend;draw()});document.getElementById('wipe').onclick=()=>{stop();mode=mode==='fade'?'wipe':'fade';draw()};document.getElementById('play').onclick=()=>{if(playing){stop();return}playing=true;mode='fade';start=performance.now();document.getElementById('play').textContent='暂停渐变';function tick(t){if(!playing)return;range.value=Math.round((1-Math.cos((t-start)*2*Math.PI/5000))*50);draw();raf=requestAnimationFrame(tick)}raf=requestAnimationFrame(tick)};const regions=REGIONS;document.getElementById('region').onchange=e=>{region=regions[e.target.value];draw()};document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});src.onload=loaded;model.onload=loaded;src.src=SOURCE;model.src=MODEL;'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--reference');p.add_argument('--config');p.add_argument('--model');p.add_argument('--clay');p.add_argument('--export-report');p.add_argument('--background',default='#f8eed8');p.add_argument('--font');p.add_argument('--title',default='真实模型多视角核对');p.add_argument('--model-label',default='');p.add_argument('--package');args=p.parse_args();manifest_path=Path(args.manifest).resolve();manifest=load(manifest_path);root=manifest_path.parent;out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Review output must be a fresh directory.')
    source=Path(manifest['source_blend'])
    if not source.is_file() or sha(source)!=manifest['source_sha256']:raise ValueError('Render source is missing or changed. Re-render the current candidate.')
    cfg=load(args.config) if args.config else {};export=load(args.export_report) if args.export_report else None;model_info=None;clay_info=None
    if args.model:
        model_info=check_glb(args.model)
        if not export or export['source_sha256']!=manifest['source_sha256'] or model_info['sha256'] not in [q['sha256'] for q in export['files']]:raise ValueError('Cannot bind this GLB to the rendered source. Supply its matching export_report.json.')
    if args.clay:
        if not args.model:raise ValueError('Clay viewer requires a main GLB.')
        clay_info=check_glb(args.clay)
        if clay_info['sha256'] not in [q['sha256'] for q in export['files']]:raise ValueError('Clay GLB is not bound to the same source.')
    image_dir=out/'images';image_dir.mkdir();images=[]
    for view in manifest['views']:
        path=contained_file(root,view['file'])
        if sha(path)!=view['sha256']:raise ValueError('A rendered frame changed: '+str(path))
        rgba=Image.open(path).convert('RGBA');alpha=rgba.getchannel('A');mask=alpha.point(lambda value:255 if value>16 else 0);box=mask.getbbox()
        if box is None:raise ValueError('Empty render: '+str(path))
        w,h=rgba.size
        if min(box[0],box[1],w-box[2],h-box[3])<2 and not view.get('allow_crop',False):raise ValueError('A whole-view render reaches the border. Increase range; do not silently crop: '+str(path))
        bg=Image.new('RGBA',rgba.size,args.background);bg.alpha_composite(rgba);dest=image_dir/path.name;bg.convert('RGB').save(dest,optimize=True);images.append((dest,view,rgba))
    font,cjk=font_choice(args.font,22);heading,_=font_choice(args.font,30);cell=360;rows=(len(images)+3)//4;header=96 if args.model_label else 64;sheet=Image.new('RGB',(1440,header+rows*408),'#f6f2e8');draw=ImageDraw.Draw(sheet);draw.text((20,12),args.model_label or args.title,font=heading,fill='#344734')
    if args.model_label:draw.text((20,54),args.title,font=font,fill='#52644b')
    for i,(path,view,_) in enumerate(images):
        image=Image.open(path);image.thumbnail((348,348),Image.Resampling.LANCZOS);x=i%4*cell+(cell-image.width)//2;y=header+i//4*408;sheet.paste(image,(x,y));draw.text((i%4*cell+8,y+362),view['label'] if cjk else view['id'],font=font,fill='#344734')
    sheet.save(out/'contact_sheet.jpg',quality=96)
    ref_info=None;comparison='';compare_js=''
    if args.reference:
        reference=Path(args.reference).resolve();copy=out/('reference'+reference.suffix.lower());shutil.copy2(reference,copy);assert sha(copy)==sha(reference);ref=Image.open(reference).convert('RGBA');front=next((q for q in images if q[1]['id']=='front'),None)
        if not front:raise ValueError('Reference comparison requires a view with id front.')
        rendered=front[2];alignment=cfg.get('reference_alignment',{});base=min(ref.width/rendered.width,ref.height/rendered.height);factor=float(alignment.get('scale',1));offset=alignment.get('offset_xy_px',[0,0]);size=(round(rendered.width*base*factor),round(rendered.height*base*factor));fitted=rendered.resize(size,Image.Resampling.LANCZOS);x=round((ref.width-size[0])/2+float(offset[0]));y=round((ref.height-size[1])/2+float(offset[1]));plate=Image.new('RGBA',ref.size,args.background);plate.alpha_composite(fitted,(x,y));plate=plate.convert('RGB');plate.save(out/'aligned_model.png');bbox=fitted.getchannel('A').point(lambda v:255 if v>16 else 0).getbbox()
        if bbox and (x+bbox[0]<0 or y+bbox[1]<0 or x+bbox[2]>ref.width or y+bbox[3]>ref.height):raise ValueError('Global alignment cropped the model. Repair camera or explicitly review the framing.')
        regions={'all':[0,0,ref.width,ref.height],**cfg.get('comparison_regions',{})}
        for region in regions.values():
            if len(region)!=4 or min(region[2:])<=0 or min(region[:2])<0 or region[0]+region[2]>ref.width or region[1]+region[3]>ref.height:raise ValueError('Invalid source-canvas comparison region.')
        opts=''.join('<option value="'+html.escape(k)+'">'+html.escape(k)+'</option>' for k in regions);comparison=f'<section><h2>原图同坐标核对</h2><canvas id="compare" width="{ref.width}" height="{ref.height}" aria-label="原图与当前真实模型渐变对照"></canvas><div class="controls"><label for="blendRange">原图 → 模型</label><input id="blendRange" type="range" min="0" max="100" value="50" aria-label="原图到模型渐变"><span id="blendStatus" role="status">正在加载</span></div><div class="controls"><button data-blend="0">仅原图</button><button data-blend="50">半透明叠图</button><button data-blend="100">仅模型</button><button id="wipe">分界对照</button><button id="play">自动渐变</button><select id="region" aria-label="同画布核对区域">{opts}</select></div><p>只改变透明度、分界或观察窗口。全局对齐参数：{html.escape(json.dumps(alignment,ensure_ascii=False))}；不对单个部件独立变形。</p></section>'
        compare_js=SCRIPT.replace('BACKGROUND',js_json(args.background)).replace('SOURCE',js_json(uri(copy))).replace('MODEL',js_json(uri(out/'aligned_model.png'))).replace('REGIONS',js_json(regions));ref_info={'source_sha256':sha(reference),'copy_sha256':sha(copy),'aligned_model_sha256':sha(out/'aligned_model.png'),'global_uniform_alignment':alignment,'individual_part_warps':False}
    three='';viewer_script=''
    if args.model:
        asset=Path(__file__).resolve().parents[1]/'assets/model-viewer.min.js'
        if not asset.is_file():raise FileNotFoundError('Bundled local viewer is missing.')
        modes={'main':base64.b64encode(Path(args.model).read_bytes()).decode()}
        if args.clay:modes['clay']=base64.b64encode(Path(args.clay).read_bytes()).decode()
        controls=''.join(f'<button data-angle="{angle}">{label}</button>' for label,angle in [('正面',0),('左前45°',-45),('右前45°',45),('左侧',-90),('右侧',90),('背面',180)])
        if args.clay:controls+='<button id="mode">无花纹白模</button>'
        three=f'<section><h2>实际GLB旋转模型</h2><model-viewer id="mv" camera-controls loading="eager" reveal="auto" interaction-prompt="none" environment-image="neutral" camera-orbit="0deg 90deg auto" style="width:100%;height:65vh;background:{args.background}"></model-viewer><p id="loadStatus" role="status">正在加载真实GLB</p><div class="controls">{controls}<button id="reset">复位</button></div><p>拖动旋转、滚轮缩放。这里是交互式透视查看器；原图核对使用上方真实正交渲染。</p></section>'
        setup="const assets="+json.dumps(modes)+";const mv=document.getElementById('mv'),loadStatus=document.getElementById('loadStatus');let current='main',url='';function use(key){loadStatus.textContent='正在加载真实GLB';if(url)URL.revokeObjectURL(url);const binary=atob(assets[key]),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);url=URL.createObjectURL(new Blob([bytes],{type:'model/gltf-binary'}));mv.src=url;current=key}mv.addEventListener('load',()=>{loadStatus.textContent='真实GLB已加载 · 可以拖动旋转';document.body.dataset.modelLoaded='true'});mv.addEventListener('error',()=>{loadStatus.textContent='模型加载失败，请检查GLB与浏览器';document.body.dataset.modelLoaded='error'});document.querySelectorAll('[data-angle]').forEach(b=>b.onclick=()=>{mv.cameraOrbit=b.dataset.angle+'deg 90deg auto'});document.getElementById('reset').onclick=()=>{mv.cameraOrbit='0deg 90deg auto';mv.cameraTarget='auto auto auto'};const modeButton=document.getElementById('mode');if(modeButton)modeButton.onclick=()=>{const key=current==='main'?'clay':'main';use(key);modeButton.textContent=key==='main'?'无花纹白模':'原图材质'};use('main');"
        library=asset.read_text('utf8').replace('</script','<\\/script');viewer_script='<script type="module">'+library+'\n(()=>{'+setup+'})();</script>'
    else:three='<p class="note">本页只包含真实渲染图和原图核对，没有装入交互式三维模型。</p>'
    license_html=''
    if args.model:
        asset_root=Path(__file__).resolve().parents[1]/'assets';notice=(asset_root/'THIRD_PARTY_NOTICES.txt').read_text('utf8');notice+='\n\n'+'\n\n'.join(path.read_text('utf8') for path in sorted((asset_root/'licenses').glob('*.txt')));license_html='<details><summary>本地查看器许可</summary><pre style="white-space:pre-wrap">'+html.escape(notice)+'</pre></details>'
    panes=[]
    if comparison:
        comparison=comparison.replace('<section>','<section id="comparePane" data-pane hidden>',1);panes.append(('comparePane','原图渐变'))
    if args.model:
        three=three.replace('<section>','<section id="viewerPane" data-pane hidden>',1).replace('height:65vh','height:60vh');panes.append(('viewerPane','旋转模型'))
    panes.append(('galleryPane','多视角'))
    gallery='<section id="galleryPane" data-pane hidden><h2>整模多视角</h2><img src="'+uri(out/'contact_sheet.jpg')+'" alt="当前真实模型多视角核对拼图"></section>'
    nav=''.join('<button data-pane-target="'+key+'">'+label+'</button>' for key,label in panes)
    initial_pane='viewerPane' if args.model else ('comparePane' if comparison else 'galleryPane')
    nav_js="(()=>{const buttons=document.querySelectorAll('[data-pane-target]');function show(id){document.querySelectorAll('[data-pane]').forEach(p=>p.hidden=p.id!==id);buttons.forEach(b=>b.classList.toggle('active',b.dataset.paneTarget===id));document.dispatchEvent(new Event('review-pane-change'))}buttons.forEach(b=>b.onclick=()=>show(b.dataset.paneTarget));show("+js_json(initial_pane)+");})();"
    comparison_script='(()=>{'+compare_js+"document.addEventListener('review-pane-change',stop);"+'})();' if compare_js else ''
    source_info='<p>当前渲染源SHA256：<code>'+manifest['source_sha256']+'</code></p><p>机器检查、页面加载与外观验收分别记录，不能互相代替。旋转页采用交互透视；原图核对采用真实正交渲染。</p>'
    body=(Path(__file__).resolve().parents[1]/'assets/review_shell.html').read_text('utf8')
    for token,value in {'TITLE':html.escape(args.title),'SOURCE_INFO':source_info,'NAV':nav,'COMPARISON':comparison,'MODEL_VIEW':three,'GALLERY':gallery,'LICENSES':license_html,'SCRIPTS':'<script>'+comparison_script+nav_js+'</script>'+viewer_script}.items():body=body.replace('@@'+token+'@@',value)
    (out/'review.html').write_text(body,'utf8');(out/'使用说明.txt').write_text('images目录中的PNG是独立无字视图。用于图生三维时请逐张选择这些文件，不要上传contact_sheet拼图、原图渐变页或其它说明。\nreview.html可离线打开；有装入GLB时支持真实拖动，未装入时只显示图像核对。当前生成的是检查材料，仍需实际观察与交互验证，不代表用户已认可。\n左右视角以render_manifest记录的相机定义为准，平台输入请先核对其示意方向。\n','utf8');result={'schema':1,'render_source_sha256':manifest['source_sha256'],'model_render_binding_verified':bool(args.model),'model':model_info,'clay':clay_info,'reference':ref_info,'view_count':len(images),'background':args.background,'local_viewer_asset_sha256':sha(Path(__file__).resolve().parents[1]/'assets/model-viewer.min.js') if args.model else None,'external_asset_urls':[],'visual_review':'required, not performed by this script','interactive_rotation_test':'required when model provided, not performed by this script','user_approval':'not inferred'};write(out/'review_record.json',result)
    if args.package:
        package=Path(args.package).resolve()
        if package.is_relative_to(out):raise ValueError('Package must be outside the directory being archived.')
        package.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
            for path in out.rglob('*'):
                if path.is_file():z.write(path,'review/'+path.relative_to(out).as_posix())
            if export:
                for record in export['files']:
                    path=contained_file(Path(args.export_report).resolve().parent,record['file'])
                    if sha(path)!=record['sha256']:raise ValueError('Export asset changed after its report.')
                    z.write(path,'model/'+record['file'])
                z.write(args.export_report,'model/export_report.json')
        with zipfile.ZipFile(package) as z:assert z.testzip() is None
        write(out/'package_record.json',{'file':str(package),'sha256':sha(package),'bytes':package.stat().st_size,'zip_crc_passed':True})
    print('REVIEW_BUNDLE_READY',json.dumps({'out':str(out),'views':len(images),'model_loaded_in_bundle':bool(args.model),'manual_review_still_required':True}))
if __name__=='__main__':main()
