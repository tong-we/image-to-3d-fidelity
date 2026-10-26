"""Stable circular/elliptical sweeps with rounded caps; Blender + NumPy.
Call round_sweep(name, centres, radii, material=None, sides=48, cap_rings=10).
Centres are actual path samples, not Bezier controls. Sample a smooth curve
densely before use when a soft limb is intended; a few points form bends.
This constructs a surface, not an anatomy fitter or self-intersection solver.
"""
import math
import bpy,bmesh,numpy as np
from mathutils import Vector

def round_sweep(name,centres,radii,material=None,sides=48,cap_rings=10):
    if name in bpy.data.objects:raise ValueError('Refusing to replace an existing object: '+name)
    c=np.asarray(centres,float);r=np.asarray(radii,float)
    if c.ndim!=2 or c.shape[1]!=3 or len(c)<2:raise ValueError('Need at least two 3D centre points.')
    if r.ndim==0:r=np.full((len(c),2),float(r))
    elif r.ndim==1:
        if len(r)!=len(c):raise ValueError('Radius count must match centre count.')
        r=np.repeat(r[:,None],2,axis=1)
    if r.shape!=(len(c),2) or not np.isfinite(c).all() or not np.isfinite(r).all() or (r<=0).any():raise ValueError('Finite positive radii required.')
    if sides<8 or cap_rings<2:raise ValueError('Need >=8 sides and >=2 cap rings.')
    segments=np.diff(c,axis=0)
    if (np.linalg.norm(segments,axis=1)<1e-10).any():raise ValueError('Repeated centre points produce an undefined frame.')
    t=np.empty_like(c);t[0]=segments[0];t[-1]=segments[-1]
    if len(c)>2:t[1:-1]=c[2:]-c[:-2]
    if (np.linalg.norm(t,axis=1)<1e-10).any():raise ValueError('Centreline cusp has no stable tangent; repair the path.')
    t/=np.linalg.norm(t,axis=1,keepdims=True);normal=np.zeros_like(c);binormal=np.zeros_like(c)
    axis=np.eye(3)[np.argmin(abs(t[0]))];normal[0]=np.cross(t[0],axis);normal[0]/=np.linalg.norm(normal[0]);binormal[0]=np.cross(t[0],normal[0])
    for i in range(1,len(c)):
        if np.dot(t[i-1],t[i])<-.95:raise ValueError('Near-reversing tangent; repair the centreline before sweeping.')
        rotation=Vector(t[i-1]).rotation_difference(Vector(t[i]));n=np.array(rotation@Vector(normal[i-1]));n-=np.dot(n,t[i])*t[i];n/=np.linalg.norm(n);normal[i]=n;binormal[i]=np.cross(t[i],n)
    angles=np.arange(sides)*2*math.pi/sides;vertices=[];rings=[];faces=[]
    def ring(center,rx,ry,n,b):
        start=len(vertices);vertices.extend((center+rx*np.cos(angles)[:,None]*n+ry*np.sin(angles)[:,None]*b).tolist());rings.append(list(range(start,start+sides)))
    # Ellipsoidal half-caps; each pole is a single vertex, never a reversed ring.
    start_pole=c[0]-t[0]*min(r[0]);end_pole=c[-1]+t[-1]*min(r[-1]);vertices.append(start_pole.tolist())
    for phi in np.linspace(0,math.pi/2,cap_rings+1)[1:-1]:ring(c[0]-t[0]*min(r[0])*math.cos(phi),r[0,0]*math.sin(phi),r[0,1]*math.sin(phi),normal[0],binormal[0])
    for i in range(len(c)):ring(c[i],r[i,0],r[i,1],normal[i],binormal[i])
    for phi in np.linspace(0,math.pi/2,cap_rings+1)[1:-1]:ring(c[-1]+t[-1]*min(r[-1])*math.sin(phi),r[-1,0]*math.cos(phi),r[-1,1]*math.cos(phi),normal[-1],binormal[-1])
    end_index=len(vertices);vertices.append(end_pole.tolist())
    for j in range(sides):faces.append((0,rings[0][(j+1)%sides],rings[0][j]))
    for a,b in zip(rings,rings[1:]):
        for j in range(sides):k=(j+1)%sides;faces.append((a[j],a[k],b[k],b[j]))
    for j in range(sides):faces.append((rings[-1][j],rings[-1][(j+1)%sides],end_index))
    me=bpy.data.meshes.new(name);me.from_pydata(vertices,[],faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(me);bm.free();ob=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(ob)
    if material:me.materials.append(material)
    for face in me.polygons:face.use_smooth=True
    return ob
