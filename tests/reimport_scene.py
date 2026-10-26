"""Re-import only generated test exports into a fresh Blender scene."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exports',required=True);p.add_argument('--format',choices=['fbx','obj'],required=True);p.add_argument('--out',required=True);args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.exports).resolve();data=json.loads((root/'export_report.json').read_text('utf8'));expected=data['geometry_snapshot'];bpy.ops.wm.read_factory_settings(use_empty=True)
    if args.format=='fbx':bpy.ops.import_scene.fbx(filepath=str(root/'model.fbx'),use_image_search=False)
    else:bpy.ops.wm.obj_import(filepath=str(root/'model.obj'),forward_axis='NEGATIVE_Z',up_axis='Y')
    objects=[ob for ob in bpy.context.scene.objects if ob.type=='MESH'];assert {ob.name for ob in objects}==set(expected);images=set();max_error=0
    for ob in objects:
        ob.data.calc_loop_triangles();assert len(ob.data.loop_triangles)==expected[ob.name]['triangles'];points=np.array([ob.matrix_world@v.co for v in ob.data.vertices]);err=float(abs(np.array([points.min(0),points.max(0)])-np.array(expected[ob.name]['bounds'])).max());assert err<1e-5;max_error=max(max_error,err)
        for mat in ob.data.materials:
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type=='TEX_IMAGE' and node.image:images.add(node.image)
    assert images
    for image in images:
        assert min(image.size)>0,('Missing texture',image.filepath)
        sample=float(image.pixels[0])
        assert image.has_data,('Texture pixels unavailable',image.filepath)
    Path(args.out).write_text(json.dumps({'passed':True,'format':args.format,'mesh_parts':len(objects),'texture_images':len(images),'max_world_bounds_error':max_error},indent=2),'utf8');print('SYNTHETIC_REIMPORT_PASSED',args.format)
if __name__=='__main__':main()
