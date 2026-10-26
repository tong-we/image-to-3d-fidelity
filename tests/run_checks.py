"""Portable self-tests using generated geometry and textures only."""
import argparse,hashlib,json,shutil,struct,subprocess,sys,zipfile
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blender',default='blender');p.add_argument('--out',required=True);args=p.parse_args();blender=shutil.which(args.blender) or args.blender
    if not Path(blender).is_file():raise FileNotFoundError('Blender not found; pass --blender with the executable path.')
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Test output must be empty.')
    out.mkdir(parents=True,exist_ok=True);results=[]
    def run(name,command,expected=0):
        done=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8',errors='replace');(out/(name+'.log')).write_text(done.stdout,'utf8');row={'test':name,'expected_exit':expected,'actual_exit':done.returncode,'passed':done.returncode==expected};results.append(row);print(name,done.returncode,flush=True)
        if not row['passed']:
            (out/'results.json').write_text(json.dumps({'passed':False,'tests':results},indent=2),'utf8');raise RuntimeError(name+' failed; see its log.\n'+done.stdout[-2500:])
    def b(name,script,values,expected=0):run(name,[blender,'-b','-t','4','--python-exit-code','9','--python',script,'--',*values],expected)
    def py(name,script,values,expected=0):run(name,[sys.executable,'-X','utf8',script,*values],expected)
    b('create_synthetic_scene',ROOT/'tests/create_scene.py',['--out',out])
    b('geometry_positive',ROOT/'scripts/audit_mesh.py',['--blend',out/'scene.blend','--config',out/'config.json','--out',out/'geometry.json','--snapshot-out',out/'baseline.json','--strict'])
    b('protected_change_rejected',ROOT/'scripts/audit_mesh.py',['--blend',out/'changed.blend','--config',out/'protected.json','--out',out/'changed_geometry.json','--strict'],2)
    b('open_solid_rejected',ROOT/'scripts/audit_mesh.py',['--blend',out/'open.blend','--config',out/'open.json','--out',out/'open_geometry.json','--strict'],2)
    b('orthographic_views',ROOT/'scripts/render_views.py',['--blend',out/'scene.blend','--config',out/'config.json','--out',out/'views','--preset','face-direction8','--resolution','256','--samples','4'])
    b('textured_exports',ROOT/'scripts/export_static.py',['--blend',out/'scene.blend','--config',out/'config.json','--out',out/'exports','--formats','blend,glb,fbx,obj','--clay'])
    b('procedural_export_rejected',ROOT/'scripts/export_static.py',['--blend',out/'procedural.blend','--config',out/'config.json','--out',out/'blocked_exports','--formats','blend,glb,fbx,obj'],3)
    for fmt in ['fbx','obj']:b('reimport_'+fmt,ROOT/'tests/reimport_scene.py',['--exports',out/'exports','--format',fmt,'--out',out/('reimport_'+fmt+'.json')])
    image=Image.open(out/'views/raw/01_front.png').convert('RGBA');background=Image.new('RGBA',image.size,'#f8eed8');background.alpha_composite(image);reference=background.convert('RGB');ImageDraw.Draw(reference).rectangle((6,6,25,25),fill='#d24020');reference.save(out/'reference.png')
    py('reference_intake',ROOT/'scripts/project_record.py',['init','--project',out/'project','--reference',out/'reference.png'])
    py('candidate_record',ROOT/'scripts/project_record.py',['record','--project',out/'project','--model',out/'scene.blend','--note','Synthetic test candidate'])
    py('approval_requires_evidence',ROOT/'scripts/project_record.py',['record','--project',out/'project','--model',out/'scene.blend','--status','user-approved','--note','No user feedback'],1)
    py('review_and_package',ROOT/'scripts/make_review.py',['--manifest',out/'views/render_manifest.json','--out',out/'review','--reference',out/'reference.png','--model',out/'exports/model.glb','--clay',out/'exports/model_clay.glb','--export-report',out/'exports/export_report.json','--package',out/'delivery.zip'])
    manifest=json.loads((out/'views/render_manifest.json').read_text('utf8'));stale=out/'stale.blend';shutil.copy2(out/'scene.blend',stale);stale_manifest={**manifest,'source_blend':str(stale)};(out/'views/stale.json').write_text(json.dumps(stale_manifest),'utf8');stale.write_bytes(stale.read_bytes()+b'stale-test')
    py('stale_render_source_rejected',ROOT/'scripts/make_review.py',['--manifest',out/'views/stale.json','--out',out/'stale_review'],1)
    raw=Image.open(out/'views'/manifest['views'][0]['file']).convert('RGBA');box=raw.getchannel('A').point(lambda v:255 if v>16 else 0).getbbox();raw.crop(box).save(out/'views/raw/cropped.png');view={**manifest['views'][0],'file':'raw/cropped.png','sha256':hashlib.sha256((out/'views/raw/cropped.png').read_bytes()).hexdigest()};(out/'views/cropped.json').write_text(json.dumps({**manifest,'views':[view]}),'utf8')
    py('unmarked_crop_rejected',ROOT/'scripts/make_review.py',['--manifest',out/'views/cropped.json','--out',out/'cropped_review'],1)
    binary=(out/'exports/model.glb').read_bytes();n=struct.unpack_from('<I',binary,12)[0];doc=json.loads(binary[20:20+n]);doc['images']=[{'uri':'https://example.invalid/never-requested.png'}];raw=json.dumps(doc,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4);tail=binary[20+n:];data=struct.pack('<4sII',b'glTF',2,20+len(raw)+len(tail))+struct.pack('<II',len(raw),0x4E4F534A)+raw+tail;(out/'remote.glb').write_bytes(data)
    py('remote_texture_rejected',ROOT/'scripts/make_review.py',['--manifest',out/'views/render_manifest.json','--out',out/'remote_review','--model',out/'remote.glb','--export-report',out/'exports/export_report.json'],1)
    assert json.loads((out/'project/project.json').read_text('utf8'))['user_approved_model'] is None
    with zipfile.ZipFile(out/'delivery.zip') as z:assert z.testzip() is None and 'model/model.glb' in z.namelist()
    result={'passed':True,'tests':results,'fixtures':'generated geometry and textures only','manual_browser_check':'open review/review.html and follow references/validation.md'};(out/'results.json').write_text(json.dumps(result,indent=2),'utf8');print('SELF_TESTS_PASSED',len(results),flush=True)
if __name__=='__main__':main()
