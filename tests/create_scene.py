"""Generate synthetic, redistributable test inputs; no external model assets."""
import argparse,json,math,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from blender_forms import round_sweep

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'scene.blend').exists():raise FileExistsError('Use a fresh test directory.')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0;scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    def mat(name,color):
        m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.85;return m
    blue=mat('CheckerMaterial',(.05,.25,.65));gold=mat('PlainMaterial',(.75,.5,.12));green=mat('SideMaterial',(.08,.45,.2))
    image=bpy.data.images.new('SyntheticChecker',width=64,height=64,alpha=True);pixels=np.empty((64,64,4),np.float32)
    for y in range(64):
        for x in range(64):pixels[y,x]=[.08,.3,.75,1] if ((x//8+y//8)%2==0) else [.2,.55,.9,1]
    image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(out/'checker.png');image.file_format='PNG';image.save();image.pack();tx=blue.node_tree.nodes.new('ShaderNodeTexImage');tx.image=image;blue.node_tree.links.new(tx.outputs['Color'],blue.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(3.2,-1.7,4.9));cap=bpy.context.object;cap.name='Canopy';cap.scale=(.32,.22,.20);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);cap.data.materials.append(blue)
    for face in cap.data.polygons:face.use_smooth=True
    t=np.linspace(0,1,60);centres=np.c_[3.2+.02*np.sin(t*2*math.pi),np.full_like(t,-1.7),4.2+.52*t];round_sweep('Trunk',centres,.12,gold,sides=24,cap_rings=8)
    t=np.linspace(0,1,40);centres=np.c_[3.2+.29*t,-1.7+.1*t,4.45+.17*t];round_sweep('Leaf',centres,.045,green,sides=24,cap_rings=8)
    bpy.ops.mesh.primitive_cube_add(size=20,location=(0,0,2));bpy.context.object.name='ExcludedGround';bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,location=(100,100,100));bpy.context.object.name='ExcludedDistractor'
    rejected=[]
    for points in [[(0,0,0),(0,0,0)],[(0,0,0),(1,0,0),(0,0,0)],[(0,0,0),(1,0,0),(.1,0,0)]]:
        try:round_sweep('InvalidPath',points,.1);rejected.append(False)
        except ValueError:rejected.append(True)
    assert all(rejected)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    cfg={'subject_objects':['Canopy','Trunk','Leaf'],'lighting':'studio','require_closed':True,'require_positive_volume':True,'require_single_component':True,'reject_self_intersections':True,'reject_unexpected_intersections':True,'expected_intersections':[['Canopy','Trunk'],['Trunk','Leaf']],'require_contact_pairs':[['Canopy','Trunk'],['Trunk','Leaf']],'contact_probes':[{'mesh':'Trunk','inside':[3.2,-1.7,4.48],'toward':[3.2,-1.7,5.1],'min_depth':.02,'min_engagement':.05}]}
    (out/'config.json').write_text(json.dumps(cfg,indent=2),'utf8');protected={**cfg,'protected_snapshot':'baseline.json','protected_objects':['Canopy']};(out/'protected.json').write_text(json.dumps(protected,indent=2),'utf8')
    cap.scale.x=1.15;bpy.ops.wm.save_as_mainfile(filepath=str(out/'changed.blend'));cap.scale.x=1
    noise=blue.node_tree.nodes.new('ShaderNodeTexNoise');blue.node_tree.links.new(noise.outputs['Color'],blue.node_tree.nodes['Principled BSDF'].inputs['Base Color']);bpy.ops.wm.save_as_mainfile(filepath=str(out/'procedural.blend'))
    bpy.ops.wm.read_factory_settings(use_empty=True);me=bpy.data.meshes.new('Open');me.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);ob=bpy.data.objects.new('Open',me);bpy.context.scene.collection.objects.link(ob);bpy.ops.wm.save_as_mainfile(filepath=str(out/'open.blend'));(out/'open.json').write_text(json.dumps({'subject_objects':['Open'],'require_closed':True,'require_positive_volume':True}),'utf8')
    print('SYNTHETIC_TEST_SCENES_READY')
if __name__=='__main__':main()
