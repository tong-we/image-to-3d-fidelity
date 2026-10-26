"""Immutable reference intake and model-state records. Python + Pillow."""
import argparse,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init');a.add_argument('--project',required=True);a.add_argument('--reference',required=True);a.add_argument('--purpose',default='editable static 3D model');a.add_argument('--identity-notes',default='');a.add_argument('--allow-completion',default='Unobserved surfaces require explicit design assumptions.')
    a=sub.add_parser('record');a.add_argument('--project',required=True);a.add_argument('--model',required=True);a.add_argument('--status',choices=['draft','candidate','user-approved'],default='candidate');a.add_argument('--note',required=True);a.add_argument('--approval-evidence',default='')
    args=p.parse_args();root=Path(args.project).resolve();manifest=root/'project.json'
    if args.command=='init':
        from PIL import Image
        source=Path(args.reference).resolve()
        if not source.is_file():raise FileNotFoundError(source)
        if root.exists() and any(root.iterdir()):raise FileExistsError('Project is not empty; continue its project.json or use a new subdirectory.')
        root.mkdir(parents=True,exist_ok=True)
        for d in ['source','working','review','delivery']:(root/d).mkdir(exist_ok=True)
        dest=root/'source'/('reference'+source.suffix.lower());shutil.copy2(source,dest);assert digest(source)==digest(dest)
        with Image.open(dest) as im:size=list(im.size)
        data={'schema':1,'created_utc':datetime.now(timezone.utc).isoformat(),'reference':{'file':dest.relative_to(root).as_posix(),'sha256':digest(dest),'pixels':size},'contract':{'purpose':args.purpose,'identity_notes':args.identity_notes,'allowed_unobserved_completion':args.allow_completion,'critical_anchors':[],'approved_regions_to_preserve':[]},'models':[],'current_candidate':None,'user_approved_model':None};write(manifest,data)
    else:
        data=json.loads(manifest.read_text('utf-8-sig'));reference=root/data['reference']['file']
        if digest(reference)!=data['reference']['sha256']:raise ValueError('Original reference changed; do not silently relabel it.')
        model=Path(args.model).resolve()
        if not model.is_file():raise FileNotFoundError(model)
        if args.status=='user-approved' and not args.approval_evidence:raise ValueError('user-approved requires the actual user feedback in --approval-evidence.')
        entry={'file':str(model),'sha256':digest(model),'status':args.status,'note':args.note,'approval_evidence':args.approval_evidence,'recorded_utc':datetime.now(timezone.utc).isoformat()};data['models'].append(entry);data['current_candidate']=entry
        if args.status=='user-approved':data['user_approved_model']=entry
        write(manifest,data)
    print(json.dumps({'project':str(root),'record':str(manifest),'reference_sha256':data['reference']['sha256']},ensure_ascii=True))
if __name__=='__main__':main()
