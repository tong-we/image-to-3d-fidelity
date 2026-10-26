"""Configurable geometry facts, baseline protection and heuristic contacts."""
import argparse,hashlib,itertools,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from _blender_utils import arguments,read_config,write_json,sha,subjects,evaluated_arrays,snapshot

def components(count,faces):
    parent=np.arange(count)
    def root(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for face in faces:
        a=root(int(face[0]))
        for b in face[1:]:parent[root(int(b))]=a
    return len({root(i) for i in range(count)})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blend',required=True);p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--snapshot-out');p.add_argument('--skip-self',action='store_true');p.add_argument('--strict',action='store_true');args=arguments(p);source=Path(args.blend).resolve();cfg=read_config(args.config);bpy.ops.wm.open_mainfile(filepath=str(source));objects=subjects(cfg);snap=snapshot(objects);warnings=[];errors=[];records=[];trees={};arrays={};open_allowed=set(cfg.get('allowed_open_meshes',[]))
    for ob in objects:
        vertices,faces=evaluated_arrays(ob);arrays[ob.name]=(vertices,faces);trees[ob.name]=BVHTree.FromPolygons(vertices.tolist(),faces.tolist(),all_triangles=True);me=bpy.data.meshes.new('__QA_AUDIT');me.from_pydata(vertices.tolist(),[],faces.tolist());me.update();bm=bmesh.new();bm.from_mesh(me);bm.normal_update()
        area=np.linalg.norm(np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]]),axis=1)*.5;scale=max(float(np.ptp(vertices,axis=0).max()),1e-12);degenerate=int((area<scale*scale*1e-14).sum());angles=np.array([edge.calc_face_angle_signed() for edge in bm.edges if edge.is_manifold]);nonmanifold=sum(not e.is_manifold for e in bm.edges);boundary=sum(e.is_boundary for e in bm.edges);volume=float(bm.calc_volume(signed=True));bm.free();bpy.data.meshes.remove(me)
        self_hits=None
        if not args.skip_self:
            face_sets=[set(q) for q in faces];self_hits=sum(a<b and not face_sets[a].intersection(face_sets[b]) for a,b in trees[ob.name].overlap(trees[ob.name]))
        rec={'part':ob.name,'vertices':len(vertices),'triangles':len(faces),'finite':bool(np.isfinite(vertices).all()),'components':components(len(vertices),faces),'nonmanifold_edges':nonmanifold,'boundary_edges':boundary,'degenerate_triangles':degenerate,'signed_volume_scene_units_cubed':volume,'max_abs_dihedral_degrees':float(np.degrees(abs(angles).max())) if len(angles) else None,'crease_edges_over_90_degrees':int((abs(angles)>np.pi/2+1e-5).sum()),'nonadjacent_BVH_self_candidates':self_hits};records.append(rec)
        if not rec['finite']:errors.append(ob.name+': non-finite coordinates')
        if degenerate and cfg.get('reject_degenerate',True):errors.append(ob.name+': degenerate triangles')
        if nonmanifold:
            (errors if cfg.get('require_closed',False) and ob.name not in open_allowed else warnings).append(ob.name+': open/nonmanifold surface')
        if cfg.get('require_positive_volume',False) and ob.name not in open_allowed and volume<=0:errors.append(ob.name+': nonpositive signed volume')
        if rec['components']>1:(errors if cfg.get('require_single_component',False) else warnings).append(ob.name+': disconnected components')
        if self_hits:(errors if cfg.get('reject_self_intersections',False) else warnings).append(ob.name+': nonadjacent BVH self-overlap candidates')
    expected={frozenset(q) for q in cfg.get('expected_intersections',[])};pairs=[]
    for a,b in itertools.combinations(trees,2):
        hit=len(trees[a].overlap(trees[b]));pairs.append({'parts':[a,b],'surface_BVH_candidates':hit,'expected':frozenset((a,b)) in expected})
        if hit and frozenset((a,b)) not in expected:(errors if cfg.get('reject_unexpected_intersections',False) else warnings).append(a+'/'+b+': unlisted surface intersection')
    for required in cfg.get('require_contact_pairs',[]):
        match=next((q for q in pairs if frozenset(q['parts'])==frozenset(required)),None)
        if not match or match['surface_BVH_candidates']==0:errors.append('/'.join(required)+': required surface crossing absent; fully embedded parts need a contact probe instead')
    protection=[];baseline_path=cfg.get('protected_snapshot')
    if baseline_path:
        bp=Path(baseline_path)
        if not bp.is_absolute():bp=Path(args.config).resolve().parent/bp
        baseline=json.loads(bp.read_text('utf-8-sig'));baseline=baseline.get('objects',baseline)
        for name in cfg.get('protected_objects',[]):
            same=name in snap and name in baseline and all(snap[name][key]==baseline[name][key] for key in ['world_vertices_sha256','triangles_sha256']);protection.append({'part':name,'geometry_exact':same})
            if not same:errors.append(name+': protected geometry changed or missing')
    elif cfg.get('protected_objects'):errors.append('protected_objects configured without protected_snapshot')
    probes=[]
    for probe in cfg.get('contact_probes',[]):
        name=probe['mesh'];point=Vector(probe['inside']);toward=Vector(probe['toward']);record={'mesh':name,'inside':list(point),'toward':list(toward),'method':'nearest-face normal heuristic plus forward exit ray; not certified solid analysis'}
        if name not in trees:errors.append(name+': contact mesh missing');record['passed']=False;probes.append(record);continue
        if next(q for q in records if q['part']==name)['nonmanifold_edges']!=0:errors.append(name+': inside probe on open/nonmanifold mesh');record['passed']=False;probes.append(record);continue
        near,normal,_,distance=trees[name].find_nearest(point);delta=toward-point
        if delta.length<1e-12:raise ValueError('Contact toward equals inside point.')
        hit=trees[name].ray_cast(point,delta.normalized())[0];engagement=float((hit-point).length) if hit is not None else 0;inside=bool((point-near).dot(normal)<0);passed=inside and distance>=float(probe.get('min_depth',0)) and engagement>=float(probe.get('min_engagement',0));record.update(inside_by_heuristic=inside,nearest_surface_depth=distance,exit_length=engagement,passed=passed);probes.append(record)
        if not passed:errors.append(name+': contact probe did not meet configured engagement')
    if args.snapshot_out:write_json(args.snapshot_out,{'source_sha256':sha(source),'objects':snap})
    result={'schema':1,'source_blend':str(source),'source_sha256':sha(source),'configured_data_checks_passed':not errors,'errors':errors,'warnings':warnings,'meshes':records,'pair_intersections':pairs,'protection':protection,'contact_probes':probes,'self_checks_performed':not args.skip_self,'geometry_snapshot':snap,'visual_fidelity_review':'not performed by this script','user_approval':'not inferred'};write_json(args.out,result);print('GEOMETRY_DATA_REPORT',json.dumps({'passed':not errors,'meshes':len(records),'warnings':len(warnings),'errors':errors},ensure_ascii=True))
    if args.strict and errors:raise SystemExit(2)
if __name__=='__main__':main()
