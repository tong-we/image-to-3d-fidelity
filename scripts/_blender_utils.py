"""Small shared helpers; import only inside Blender. No project-specific names."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np

def arguments(parser):
    return parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

def read_config(path):
    return json.loads(Path(path).read_text('utf-8-sig')) if path else {}

def write_json(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def subjects(config):
    requested=config.get('subject_objects')
    if requested:
        missing=[n for n in requested if n not in bpy.context.scene.objects]
        if missing:raise ValueError('Missing subject objects: '+repr(missing))
        result=[bpy.context.scene.objects[n] for n in requested]
        if any(o.type!='MESH' for o in result):raise ValueError('subject_objects must name mesh objects')
    else:
        result=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render]
    if not result:raise ValueError('No subject mesh. Specify subject_objects in JSON.')
    return result

def evaluated_arrays(ob):
    evaluated=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
    try:
        points=np.array([evaluated.matrix_world@v.co for v in me.vertices],dtype='<f8')
        me.calc_loop_triangles();faces=np.array([q.vertices[:] for q in me.loop_triangles],dtype='<i8').reshape(-1,3)
        return points,faces
    finally:evaluated.to_mesh_clear()

def object_fingerprint(ob):
    p,f=evaluated_arrays(ob)
    return {'vertices':len(p),'triangles':len(f),'world_vertices_sha256':hashlib.sha256(p.tobytes()).hexdigest(),'triangles_sha256':hashlib.sha256(f.tobytes()).hexdigest(),'bounds':[p.min(0).tolist(),p.max(0).tolist()]}

def snapshot(objects):return {o.name:object_fingerprint(o) for o in objects}

def select_only(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.hide_set(False);ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
