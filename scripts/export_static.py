"""Static explicit-image PBR transport exports. Does not install or download."""
import argparse,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from _blender_utils import arguments,read_config,write_json,sha,subjects,snapshot,select_only

def linked_images(socket,seen=None):
    seen=set() if seen is None else seen
    for link in socket.links:
        node=link.from_node
        if node in seen:continue
        seen.add(node)
        if node.type=='TEX_IMAGE' and node.image:yield node.image
        else:
            for value in node.inputs:yield from linked_images(value,seen)

def material_issues(objects,allow_vertex_color=False):
    issues=[]
    for ob in objects:
        for mat in ob.data.materials:
            if not mat or not mat.use_nodes:continue
            bs=mat.node_tree.nodes.get('Principled BSDF')
            if not bs:issues.append(ob.name+'/'+mat.name+': no simple Principled material; bake a transport copy');continue
            socket=bs.inputs['Base Color']
            allowed={'TEX_IMAGE'}|({'VERTEX_COLOR','ATTRIBUTE'} if allow_vertex_color else set())
            if socket.is_linked and socket.links[0].from_node.type not in allowed:issues.append(ob.name+'/'+mat.name+': Base Color is vertex/procedural/complex; bake or prepare target shader')
            for channel in ['Metallic','Roughness','Alpha','Normal','Emission Color']:
                value=bs.inputs.get(channel)
                if value and value.is_linked:
                    node=value.links[0].from_node
                    if node.type not in ({'NORMAL_MAP'} if channel=='Normal' else {'TEX_IMAGE'}):issues.append(ob.name+'/'+mat.name+': '+channel+' uses unsupported transport nodes; bake it')
                    elif channel=='Normal' and (not node.inputs['Color'].is_linked or node.inputs['Color'].links[0].from_node.type!='TEX_IMAGE'):issues.append(ob.name+'/'+mat.name+': normal map has no explicit image')
            for image in linked_images(socket):
                image_node=next((n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image==image),None)
                if image_node and image_node.inputs['Vector'].is_linked and image_node.inputs['Vector'].links[0].from_node.type not in {'UVMAP','TEX_COORD'}:issues.append(ob.name+'/'+mat.name+': transformed/procedural image coordinates require baking for transport')
            for node in mat.node_tree.nodes:
                if node.type=='UVMAP' and node.uv_map and ob.data.uv_layers:
                    active=next((v for v in ob.data.uv_layers if v.active_render),ob.data.uv_layers.active)
                    if node.uv_map!=active.name:issues.append(ob.name+': explicit material UV differs from active-render UV; consolidate/bake before OBJ/FBX')
    return sorted(set(issues))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blend',required=True);p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--formats',default='blend,glb');p.add_argument('--clay',action='store_true');args=arguments(p);source=Path(args.blend).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Export directory must be empty.')
    formats=set(args.formats.split(','));unknown=formats-{'blend','glb','fbx','obj'}
    if unknown:raise ValueError('Unknown formats: '+repr(unknown))
    src_hash=sha(source);bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.filepaths.save_version=0;objects=subjects(read_config(args.config));initial=snapshot(objects);files=[];notes=[];blocked={}
    def record(path):files.append({'file':path.relative_to(out).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    if 'blend' in formats:
        bpy.ops.file.pack_all();path=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));record(path);notes.append('source.blend is the editable full scene, not just selected meshes.')
    glb_issues=material_issues(objects,allow_vertex_color=True)
    if 'glb' in formats and not glb_issues:
        select_only(objects);path=out/'model.glb';bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_tangents=False);record(path)
    elif 'glb' in formats:blocked['glb']=glb_issues
    issues=material_issues(objects)
    transport=formats&{'fbx','obj'}
    if issues:
        for fmt in transport:blocked[fmt]=issues
    elif transport:
        textures=out/'textures';textures.mkdir();saved={};mats=set()
        for ob in objects:
            if ob.data.uv_layers:
                active=next((v for v in ob.data.uv_layers if v.active_render),ob.data.uv_layers.active);values=[v.uv[:] for v in active.data]
                for layer in list(ob.data.uv_layers):ob.data.uv_layers.remove(layer)
                uv=ob.data.uv_layers.new(name='UVMap');uv.active_render=True;ob.data.uv_layers.active=uv
                for point,value in zip(uv.data,values):point.uv=value
            for mat in ob.data.materials:
                if not mat or mat in mats or not mat.use_nodes:continue
                mats.add(mat)
                for node in mat.node_tree.nodes:
                    if node.type=='UVMAP':node.uv_map='UVMap'
                bs=mat.node_tree.nodes.get('Principled BSDF')
                for name in ['Base Color','Metallic','Roughness','Alpha','Normal','Emission Color']:
                    if name not in bs.inputs:continue
                    for image in linked_images(bs.inputs[name]):
                        if image in saved:continue
                        path=textures/f'texture_{len(saved)+1:03d}.png'
                        if image.packed_file:path.write_bytes(bytes(image.packed_file.data));
                        else:image.filepath_raw=str(path);image.file_format='PNG';image.save()
                        # Packed PNG/JPEG bytes keep their actual file extension.
                        magic=path.read_bytes()[:3]
                        if magic==b'\xff\xd8\xff':new=path.with_suffix('.jpg');path.rename(new);path=new
                        if image.packed_file:image.unpack(method='REMOVE')
                        image.filepath=str(path);image.reload();saved[image]=str(path);record(path)
        if 'fbx' in transport:
            select_only(objects);path=out/'model.fbx';bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',bake_anim=False,add_leaf_bones=False,path_mode='COPY',embed_textures=True,mesh_smooth_type='FACE');record(path)
        if 'obj' in transport:
            select_only(objects);path=out/'model.obj';bpy.ops.wm.obj_export(filepath=str(path),export_selected_objects=True,export_uv=True,export_normals=True,export_colors=False,export_materials=True,export_triangulated_mesh=True,forward_axis='NEGATIVE_Z',up_axis='Y',path_mode='RELATIVE');record(path);record(path.with_suffix('.mtl'))
    if args.clay:
        mat=bpy.data.materials.new('QA_Clay');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.42,.42,.42,1);bs.inputs['Roughness'].default_value=.95
        for ob in objects:
            ob.data=ob.data.copy();ob.data.materials.clear();ob.data.materials.append(mat)
            for attribute in list(ob.data.color_attributes):ob.data.color_attributes.remove(attribute)
            for face in ob.data.polygons:face.material_index=0
        select_only(objects);path=out/'model_clay.glb';bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True);record(path)
    assert initial==snapshot(objects),'Export changed subject geometry';assert sha(source)==src_hash,'Source file changed'
    data={'schema':1,'source_blend':str(source),'source_sha256':src_hash,'subject_objects':[o.name for o in objects],'geometry_snapshot':initial,'source_file_unchanged':True,'subject_geometry_unchanged':True,'unit_system':bpy.context.scene.unit_settings.system,'metres_per_scene_unit':bpy.context.scene.unit_settings.scale_length,'files':files,'blocked_formats':blocked,'notes':notes,'reimport_validation':'not performed by this script','game_engine_runtime':'not tested','rig_or_animation_added':False};write_json(out/'export_report.json',data);print('STATIC_EXPORT_REPORT',json.dumps({'files':len(files),'blocked_formats':list(blocked),'out':str(out)}))
    if blocked:raise SystemExit(3)
if __name__=='__main__':main()
