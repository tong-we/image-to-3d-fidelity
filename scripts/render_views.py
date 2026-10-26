"""Render real subject meshes with one camera range; never overwrite source."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,numpy as np
from mathutils import Vector
from _blender_utils import arguments,read_config,write_json,sha,subjects,evaluated_arrays,snapshot

PRESETS={
 'review8':[('front','正面',0,0),('left45','左前45°',-45,0),('right45','右前45°',45,0),('right','右侧',90,0),('left','左侧',-90,0),('back45','右后45°',135,0),('back','背面',180,0),('back_left45','左后45°',-135,0)],
 'orthographic8':[('front','正面',0,0),('left45','左前45°',-45,0),('right45','右前45°',45,0),('left','左侧',-90,0),('right','右侧',90,0),('back','背面',180,0),('top','顶面',0,90),('bottom','底面',0,-90)],
 'face-direction8':[('front','正面',0,0),('left45','左朝向45°',45,0),('right45','右朝向45°',-45,0),('left','左朝向侧面',90,0),('right','右朝向侧面',-90,0),('back','背面',180,0),('top','顶面',0,90),('bottom','底面',0,-90)]}

def camera_rotation(yaw,elevation):
    a,e=map(math.radians,(yaw,elevation));direction=Vector((math.sin(a)*math.cos(e),-math.cos(a)*math.cos(e),math.sin(e)))
    if abs(elevation-90)<1e-8:rotation=Vector((0,0,0))
    elif abs(elevation+90)<1e-8:rotation=Vector((math.pi,0,0))
    else:rotation=(-direction).to_track_quat('-Z','Y').to_euler()
    return direction,rotation

def studio(scene,center,span):
    for ob in scene.objects:
        if ob.type=='LIGHT':ob.hide_render=True
    world=bpy.data.worlds.new('QA_Local_Studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35;scene.world=world
    for name,offset,power in [('key',(-2,-2,3),500),('fill',(2,-1,1.2),250),('rim',(0,2,2),350)]:
        light=bpy.data.lights.new('QA_'+name,'AREA');light.energy=power*span*span;light.shape='DISK';light.size=2*span;ob=bpy.data.objects.new('QA_'+name,light);scene.collection.objects.link(ob);ob.location=Vector(center)+Vector(offset)*span;ob.rotation_euler=(Vector(center)-ob.location).to_track_quat('-Z','Y').to_euler()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blend',required=True);p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--preset',choices=list(PRESETS),default='review8');p.add_argument('--resolution',type=int,default=1024);p.add_argument('--samples',type=int,default=16);p.add_argument('--clay',action='store_true');args=arguments(p)
    source=Path(args.blend).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'render_manifest.json').exists():raise FileExistsError('Use a fresh review directory; old renders must not be relabelled.')
    original_hash=sha(source);bpy.ops.wm.open_mainfile(filepath=str(source));cfg=read_config(args.config);scene=bpy.context.scene;objects=subjects(cfg)
    if cfg.get('frame') is not None:scene.frame_set(int(cfg['frame']))
    initial=snapshot(objects)
    for ob in scene.objects:
        if ob.type=='MESH':ob.hide_render=ob not in objects
    for ob in objects:ob.hide_render=False
    points=np.vstack([evaluated_arrays(ob)[0] for ob in objects]);lo,hi=points.min(0),points.max(0);dims=hi-lo;span=max(float(dims.max()),1e-4);center=(lo+hi)/2
    camera_cfg=cfg.get('camera',{});target=Vector(camera_cfg.get('target',center.tolist()));offset=float(camera_cfg.get('front_yaw_degrees',0));definitions=cfg.get('views') or [{'id':a,'label':b,'yaw':c,'elevation':d} for a,b,c,d in PRESETS[args.preset]]
    if not definitions:raise ValueError('No camera views.')
    max_projection=0
    for view in definitions:
        direction,rot=camera_rotation(float(view['yaw'])+offset,float(view.get('elevation',0)));matrix=rot.to_matrix() if hasattr(rot,'to_matrix') else __import__('mathutils').Euler(rot).to_matrix();right=matrix@Vector((1,0,0));up=matrix@Vector((0,1,0));max_projection=max(max_projection,float(np.sum(abs(np.array(right))*dims)),float(np.sum(abs(np.array(up))*dims)))
    fill=float(camera_cfg.get('fill_fraction',.88))
    if not .1<fill<1:raise ValueError('fill_fraction must be between .1 and 1.')
    scale=float(camera_cfg.get('ortho_scale',max_projection/fill));distance=float(camera_cfg.get('distance',span*4));camdata=bpy.data.cameras.new('QA_Orthographic');cam=bpy.data.objects.new('QA_Orthographic',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.type='ORTHO';camdata.ortho_scale=scale;camdata.clip_start=max(span*.001,1e-6);camdata.clip_end=max(distance+span*100,1);camdata.dof.use_dof=False
    lighting=cfg.get('lighting','studio')
    if lighting=='studio':studio(scene,center,span)
    elif lighting!='existing':raise ValueError('lighting must be studio or existing.')
    scene.render.engine='CYCLES';scene.cycles.samples=args.samples;scene.render.resolution_x=scene.render.resolution_y=args.resolution;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8';scene.render.use_persistent_data=True
    if args.clay:
        material=bpy.data.materials.new('QA_Clay');material.use_nodes=True;bs=material.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.42,.42,.42,1);bs.inputs['Roughness'].default_value=.95
        for ob in objects:
            ob.data=ob.data.copy();ob.data.materials.clear();ob.data.materials.append(material)
            for attribute in list(ob.data.color_attributes):ob.data.color_attributes.remove(attribute)
            for face in ob.data.polygons:face.material_index=0
    raw=out/'raw';raw.mkdir(exist_ok=True);records=[]
    for i,view in enumerate(definitions):
        key=str(view['id'])
        if not key.replace('_','').replace('-','').isalnum():raise ValueError('View id must be a filename-safe word.')
        yaw=float(view['yaw'])+offset;elevation=float(view.get('elevation',0));direction,rot=camera_rotation(yaw,elevation);cam.location=target+direction*distance;cam.rotation_euler=rot;scene.render.filepath=str(raw/f'{i+1:02d}_{key}.png');bpy.ops.render.render(write_still=True);path=Path(scene.render.filepath);records.append({'id':key,'label':view.get('label',key),'file':path.relative_to(out).as_posix(),'yaw':yaw,'elevation':elevation,'camera_location':list(cam.location),'camera_rotation_euler':list(cam.rotation_euler),'allow_crop':bool(view.get('allow_crop',False)),'sha256':sha(path)})
    unchanged=initial==snapshot(objects)
    if not unchanged:raise AssertionError('Subject geometry changed or depends on the camera. Inspect before using these views as reconstruction evidence.')
    assert sha(source)==original_hash
    result={'schema':1,'source_blend':str(source),'source_sha256':original_hash,'subject_objects':[ob.name for ob in objects],'geometry_snapshot':initial,'subject_geometry_unchanged':True,'view_profile':args.preset,'profile_note':'Review and face-direction profiles use different left/right conventions; match the target application explicitly.','resolution':[args.resolution,args.resolution],'projection':'ORTHO','target':list(target),'ortho_scale':scale,'lighting':lighting,'clay':args.clay,'views':records,'visual_review':'not performed by this script'};write_json(out/'render_manifest.json',result);print('REAL_MODEL_VIEWS_READY',json.dumps({'views':len(records),'out':str(out),'source_sha256':original_hash}))
if __name__=='__main__':main()
