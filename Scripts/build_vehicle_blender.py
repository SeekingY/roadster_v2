"""Editable, explicitly approximate exterior blockout; Blender 4.2, CPU only.

Run blender --background --factory-startup --threads 4 --python THIS_FILE
Optional arguments after --: --preview (small CPU Cycles validation views).
No animation, interior engineering, official dimensions, or claimed CAD.
"""
import bpy
import bmesh
import json
import math
import sys
import hashlib
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'AssetsSource'
OUT.mkdir(exist_ok=True)
(OUT / 'FBX').mkdir(exist_ok=True)
(OUT / 'Previews').mkdir(exist_ok=True)

DEFAULTS = {
    'status': 'assumed dimensions for silhouette blockout; not Tesla specifications',
    'length_cm': 460.0, 'width_cm': 200.0, 'height_cm': 115.0,
    'wheelbase_cm': 275.0, 'front_track_cm': 168.0, 'rear_track_cm': 170.0,
    'front_tire_radius_cm': 36.0, 'rear_tire_radius_cm': 36.0,
    'front_tire_width_cm': 27.0, 'rear_tire_width_cm': 30.0,
    'body_clearance_cm': 17.0,
}
PARAM_PATH = OUT / 'vehicle_parameters.json'
if not PARAM_PATH.exists():
    PARAM_PATH.write_text(json.dumps(DEFAULTS, indent=2), encoding='utf-8')
P = dict(DEFAULTS)
P.update(json.loads(PARAM_PATH.read_text(encoding='utf-8')))
SX, SY, SZ = P['length_cm']/460, P['width_cm']/200, P['height_cm']/115

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != 'Collection':
        bpy.data.collections.remove(collection)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .01
scene.unit_settings.length_unit = 'CENTIMETERS'
BODY = bpy.data.collections.new('01_Editable_Exterior_Blockout')
WHEELS = bpy.data.collections.new('02_Independent_Wheels')
CHECK = bpy.data.collections.new('90_Preview_Only_Not_Exported')
for c in [BODY, WHEELS, CHECK]:
    scene.collection.children.link(c)

def move_to(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)

def material(name, color, metallic=0.0, roughness=.4, emission=0.0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Metallic'].default_value=metallic
    bsdf.inputs['Roughness'].default_value=roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value=(*color,1)
        bsdf.inputs['Emission Strength'].default_value=emission
    return m

SILVER=material('M_Blockout_Silver',(.47,.49,.51),.62,.31)
SHADOW=material('M_Blockout_DarkTrim',(.018,.023,.027),.2,.43)
GLASS=material('M_Blockout_BlackGlass',(.012,.022,.029),.18,.16)
RUBBER=material('M_Blockout_Tire',(.015,.018,.020),0,.72)
RIM=material('M_Blockout_Rim',(.19,.22,.24),.75,.3)
RED=material('M_Blockout_RedTail',(.75,.006,.002),.05,.3,2)
WHITE=material('M_Blockout_Headlight',(.76,.86,1),.05,.25,1.5)

def mesh(name, verts, faces, mat, col=BODY, scaled=True):
    verts=[(x*SX,y*SY,z*SZ) for x,y,z in verts] if scaled else verts
    me=bpy.data.meshes.new(name+'_mesh')
    me.from_pydata(verts, [], faces)
    me.update()
    obj=bpy.data.objects.new(name,me)
    col.objects.link(obj)
    if mat: me.materials.append(mat)
    bm=bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return obj

def bevel(obj, width=0.5, segments=2):
    b=obj.modifiers.new('Small edge radius - editable','BEVEL')
    b.width=width; b.segments=segments
    b.limit_method='ANGLE'
    b.angle_limit=.35
    n=obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    n.keep_sharp=True

def cube(name, loc, scale, mat, col=BODY, edge=.3):
    bpy.ops.mesh.primitive_cube_add(size=1,location=(loc[0]*SX,loc[1]*SY,loc[2]*SZ))
    obj=bpy.context.object; obj.name=name
    obj.dimensions=(scale[0]*SX,scale[1]*SY,scale[2]*SZ)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    move_to(obj,col); obj.data.materials.append(mat)
    if edge: bevel(obj,edge)
    return obj

# X stations: front to rear. Each station has width, shoulder, deck and floor.
# Facets capture the visual vocabulary; these are NOT measured section curves.
stations=[
    (230,79,55,49,25), (218,91,65,53,22), (180,98,76,68,21),
    (137.5,100,81,76,19), (92,98,79,75,18), (50,94,75,74,17),
    (-30,92,76,76,17), (-87,96,81,78,17), (-137.5,100,84,78,18),
    (-183,98,82,74,21), (-220,93,77,69,25), (-230,88,71,64,30),
]
verts=[]
for x,w,shoulder,deck,floor in stations:
    ring=[(0,deck),(.66*w,deck+.5),(.89*w,shoulder),(w,shoulder-9),
          (w*.98,37),(w*.89,floor),(0,floor),(-w*.89,floor),
          (-w*.98,37),(-w,shoulder-9),(-w*.89,shoulder),(-.66*w,deck+.5)]
    verts += [(x,y,z) for y,z in ring]
faces=[]; n=12
for i in range(len(stations)-1):
    for j in range(n):
        faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
faces.append(tuple(reversed(range(n))))
faces.append(tuple((len(stations)-1)*n+j for j in range(n)))
shell=mesh('Body_Sculpted_Wedge',verts,faces,SILVER)

# Wheel openings cut the exterior shell. This is silhouette clearance, no suspension.
for label,xc,track,radius in [('F',P['wheelbase_cm']/2,P['front_track_cm'],P['front_tire_radius_cm']),
                             ('R',-P['wheelbase_cm']/2,P['rear_track_cm'],P['rear_tire_radius_cm'])]:
    for sign in [-1,1]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius+3,depth=64*SY,
            location=(xc,sign*100*SY,radius),rotation=(math.pi/2,0,0))
        cutter=bpy.context.object; cutter.name='Temporary_'+label+'_Wheel_Opening'
        bpy.context.view_layer.objects.active=shell
        mod=shell.modifiers.new(label+' wheel arch silhouette','BOOLEAN')
        mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
# Native source frames 264/456 show a dark panelled underside.  Reassign only
# existing downward-facing shell faces; do not alter silhouette vertices.
shell.data.materials.append(SHADOW)
for face in shell.data.polygons:
    if face.normal.z < -.45 and face.center.z < 38*SZ:
        face.material_index=1
bevel(shell,.6,2)

# Black canopy: windshield, low roof, rear glass and side glazing as editable panels.
canopy=[
    (90,61,74), (22,56,113), (-62,55,115), (-145,62,80),
]
roofverts=[]
for x,w,z in canopy:
    roofverts += [(x,-w,z),(x,0,z+(.0 if x==-62 else .5)),(x,w,z)]
rooffaces=[]
for i in range(3):
    rooffaces.extend([(i*3,i*3+1,(i+1)*3+1,(i+1)*3),
                     (i*3+1,i*3+2,(i+1)*3+2,(i+1)*3+1)])
glass=mesh('Canopy_Windscreen_Roof_RearGlass',roofverts,rooffaces,GLASS)
solid=glass.modifiers.new('Glass surface thickness','SOLIDIFY');solid.thickness=.4
for side,sign in [('Left',1),('Right',-1)]:
    sideverts=[(87,sign*63,75),(20,sign*58,110),(-61,sign*57,111),
               (-137,sign*65,80),(-96,sign*80,76),(52,sign*79,73)]
    g=mesh(side+'_Side_Glass',sideverts,[tuple(range(6))],GLASS)
    s=g.modifiers.new('Glass surface thickness','SOLIDIFY');s.thickness=.4
    # Narrow silver shoulder strips flank the black canopy.
    rail=[(91,sign*64,74),(22,sign*58,113),(-62,sign*57,115),(-148,sign*65,80),
          (-151,sign*72,80),(-62,sign*62,114),(22,sign*63,112),(90,sign*71,74)]
    o=mesh(side+'_Canopy_Silver_Edge',rail,[tuple(range(8))],SILVER)
    b=o.modifiers.new('Edge thickness','SOLIDIFY');b.thickness=.7
    # Unmeasured lower sill, kept visually simple.
    sill=mesh(side+'_Lower_Sill',[(97,sign*95,27),(-94,sign*96,27),
         (-101,sign*97,18),(97,sign*95,18)],[(0,1,2,3)],SHADOW)
    s=sill.modifiers.new('Sill thickness','SOLIDIFY');s.thickness=1.5

# Sharply tapered hood facets and front mask, without invented intakes/pipes.
cube('Front_Dark_Mask',(230,0,35),(2,151,18),SHADOW,edge=.8)
cube('Front_Lower_Lip',(226,0,24),(7,160,3),SHADOW,edge=.7)
for sign,label in [(1,'Left'),(-1,'Right')]:
    pts=[(214,sign*62,57),(205,sign*84,64),(184,sign*88,69),(202,sign*68,59)]
    h=mesh(label+'_Recessed_Headlight',pts,[(0,1,2,3)],WHITE)
    s=h.modifiers.new('Light face thickness','SOLIDIFY');s.thickness=.5

# The full-width red rear light is visible in current and legacy browser frames.
cube('Rear_Light_Black_Housing',(-231,0,65),(2.4,177,6),SHADOW,edge=.5)
cube('Full_Width_Red_Taillight',(-232.4,0,65.5),(.7,172,2.0),RED,edge=.25)
cube('Rear_Upper_Integrated_Lip',(-226,0,74),(10,181,2.4),SILVER,edge=.5)
rear_shadow=cube('Rear_Lower_Shadow_Face',(-230,0,43),(3,157,22),SHADOW,edge=1.4)
# Recess only the inner face; the original bevelled perimeter keeps its envelope.
bpy.context.view_layer.objects.active=rear_shadow
for modifier in list(rear_shadow.modifiers):bpy.ops.object.modifier_apply(modifier=modifier.name)
recess=cube('Temporary_Rear_Visible_Recess',(-231.6,0,43),(2.0,153,18),SHADOW,edge=.2)
bpy.context.view_layer.objects.active=rear_shadow
mod=rear_shadow.modifiers.new('Shallow exterior recess only','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=recess
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(recess,do_unlink=True)
plate=cube('Rear_Plate_RDSTR',(-232.3,0,52),(1,24,12),SILVER,edge=.5)
bpy.context.view_layer.objects.active=plate
for modifier in list(plate.modifiers):bpy.ops.object.modifier_apply(modifier=modifier.name)
# Visible exterior detail from native official frame0 and broadcast sample_081.
# These four circular features are modelled as visible apertures, not asserted
# to be a measured nozzle system. Existing shell and tyre vertices are unchanged.
def rear_aperture(name,y,z,r_outer=5.0,r_inner=3.9):
    seg=48; vv=[]; ff=[]
    # Recessed lip and dark wall stay inside the existing rear-most plate plane.
    for x,r in [(-231.40,r_outer),(-231.40,r_inner),(-231.0,r_inner*.96)]:
        for k in range(seg):
            a=k*math.tau/seg;vv.append((x,y+r*math.cos(a),z+r*math.sin(a)))
    for j in range(2):
        for k in range(seg):
            kk=(k+1)%seg;ff.append((j*seg+k,j*seg+kk,(j+1)*seg+kk,(j+1)*seg+k))
    ring=mesh(name+'_Thin_Lip',vv[:seg*2],ff[:seg],RIM)
    wall=mesh(name+'_Dark_Inner_Wall',vv[seg:],
        [(k,(k+1)%seg,seg+(k+1)%seg,seg+k) for k in range(seg)],SHADOW)
    # A black backing directly below the ring is an appearance-only cavity.
    disk=[(-231.05,y+r_inner*math.cos(k*math.tau/seg),z+r_inner*math.sin(k*math.tau/seg)) for k in range(seg)]
    mesh(name+'_Black_Opening',disk,[tuple(range(seg))],RUBBER)
for i,y in enumerate([-42,-14,14,42],1):
    rear_aperture('Rear_Visible_Circular_Aperture_'+str(i),y,43.5)

# Open-looking dark diffuser recess with a shallow raised perimeter.
# It does not imply any unseen fan, pressure vessel or suspension arrangement.
cube('Rear_Diffuser_Upper_Boundary',(-231.35,0,38.0),(.10,130,1.0),SHADOW,edge=.04)
cube('Rear_Diffuser_Lower_Boundary',(-231.15,0,34.6),(.10,128,.8),SHADOW,edge=.04)
cube('Rear_Diffuser_Dark_Opening',(-231.10,0,36.3),(.04,127,3.2),RUBBER,edge=.01)
for y,side in [(-65,'Right'),(65,'Left')]:
    cube('Rear_Diffuser_'+side+'_Boundary',(-231.15,y,36.3),(.10,1.5,4.3),SHADOW,edge=.04)
for y,side in [(-72,'Right'),(72,'Left')]:
    cube('Rear_Outer_'+side+'_Dark_Cheek',(-231.15,y,43),(.10,9,16),SHADOW,edge=.04)

# Recess the actual visible plate lettering into the existing plate face.
# Subtraction preserves the plate perimeter and all silhouette extrema.
def plate_text(name,x,extrude,mat):
    curve=bpy.data.curves.new(name+'_curve','FONT');curve.body='RDSTR'
    curve.align_x='CENTER';curve.align_y='CENTER';curve.size=5.0
    curve.extrude=extrude;curve.resolution_u=4
    obj=bpy.data.objects.new(name,curve);BODY.objects.link(obj)
    obj.location=(x*SX,0,52*SZ)
    obj.rotation_euler=Matrix(((0,0,-1),(-1,0,0),(0,1,0))).to_quaternion().to_euler()
    obj.scale=(SY,SZ,SX)
    if mat:curve.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH')
    return bpy.context.object
cutter=plate_text('Temporary_Plate_Letter_Engraving',-232.6,.4,None)
bpy.context.view_layer.objects.active=plate
mod=plate.modifiers.new('Inset visible RDSTR letters','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(cutter,do_unlink=True)
plate_text('Plate_RDSTR_Dark_Letter_Inlay',-232.60,0,SHADOW)
# No fan blades, pressure vessels, pipes or suspension invented here.
under=mesh('Unmeasured_Simplified_Undertray',[
    (191,-66,17.5),(191,66,17.5),(-194,70,17.5),(-209,53,20),
    (-209,-53,20),(-194,-70,17.5)],[(0,1,2,3,4,5)],SHADOW)
s=under.modifiers.new('Undertray thickness','SOLIDIFY');s.thickness=1
# Appearance-only panel boundaries on the original undertray surface.  All
# cuts interpolate existing triangles, keeping the previous outer envelope.
# Pattern is approximate: the source supports dark panels and seams, not a
# recovered mechanical layout.  No pipes, engine or propulsion internals.
bpy.context.view_layer.objects.active=under
bpy.ops.object.modifier_apply(modifier=s.name)
bm=bmesh.new();bm.from_mesh(under.data)
bmesh.ops.triangulate(bm,faces=list(bm.faces))
for axis,values in [(0,[-163,-160,-94,-91,-8,-5,79,82,158,161]),
                    (1,[-47,-44,-3,3,44,47])]:
    for value in values:
        origin=[0.,0.,0.];normal=[0.,0.,0.]
        origin[axis]=value*(SX if axis==0 else SY);normal[axis]=1
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=1e-5,plane_co=origin,plane_no=normal,clear_outer=False,clear_inner=False)
bm.to_mesh(under.data);bm.free();under.data.update()
under.data.materials.append(RUBBER)
under.data.materials.append(RIM)
for face in under.data.polygons:
    c=face.center;x=c.x/SX;y=c.y/SY
    if face.normal.z < -.5:
        # Narrow contrast bands depict observed surface seams; not structural beams.
        is_cross_seam=any(lo < x < hi for lo,hi in [(-163,-160),(-94,-91),(-8,-5),(79,82),(158,161)])
        is_long_seam=(44 < abs(y) < 47)
        face.material_index=2 if (is_cross_seam or is_long_seam) else (1 if abs(y)<44 else 0)

wheel_centers={}
wheel_groups={}

def tire_mesh(name,r,width):
    # Lathed tire section around local Y; origin exactly at wheel center.
    profile=[(-width/2,r*.78),(-width/2,r*.91),(-width*.43,r*.985),
             (-width*.29,r),(width*.29,r),(width*.43,r*.985),
             (width/2,r*.91),(width/2,r*.78)]
    vv=[]; ff=[]; seg=64
    for y,rad in profile:
        for k in range(seg):
            a=2*math.pi*k/seg;vv.append((rad*math.cos(a),y,rad*math.sin(a)))
    for j in range(len(profile)-1):
        for k in range(seg):
            kk=(k+1)%seg;ff.append((j*seg+k,j*seg+kk,(j+1)*seg+kk,(j+1)*seg+k))
    obj=mesh(name,vv,ff,RUBBER,WHEELS,False)
    for poly in obj.data.polygons:poly.use_smooth=True
    return obj

def annulus(name,r1,r2,y,mat):
    vv=[];ff=[];seg=64
    for rad in [r1,r2]:
        for k in range(seg):
            a=k*math.tau/seg;vv.append((rad*math.cos(a),y,rad*math.sin(a)))
    for k in range(seg):ff.append((k,(k+1)%seg,seg+(k+1)%seg,seg+k))
    return mesh(name,vv,ff,mat,WHEELS,False)

for axle,x,track,r,width in [
    ('F',P['wheelbase_cm']/2,P['front_track_cm'],P['front_tire_radius_cm'],P['front_tire_width_cm']),
    ('R',-P['wheelbase_cm']/2,P['rear_track_cm'],P['rear_tire_radius_cm'],P['rear_tire_width_cm'])]:
    for side,sgn in [('L',1),('R',-1)]:
        tag=axle+side; center=Vector((x,sgn*track/2,r)); group=[]
        group.append(tire_mesh('Wheel_'+tag+'_Tire',r,width))
        y=sgn*(width/2+.25)
        group.append(annulus('Wheel_'+tag+'_Outer_Rim',r*.70,r*.80,y,RIM))
        group.append(annulus('Wheel_'+tag+'_Inner_Dark',0.01,r*.70,y-sgn*.4,SHADOW))
        # Six broad faceted spokes are blockout assumptions, not official geometry.
        for k in range(6):
            a=k*math.tau/6
            pts=[]
            for rr,ang in [(5,a-.22),(r*.71,a+.07),(r*.71,a+.29),(8,a+.22)]:
                pts.append((rr*math.cos(ang),y+sgn*.45,rr*math.sin(ang)))
            group.append(mesh('Wheel_'+tag+'_Spoke_'+str(k+1),pts,[(0,1,2,3)],RIM,WHEELS,False))
        group.append(annulus('Wheel_'+tag+'_Hub',.01,7,y+sgn*.7,RIM))
        # The actual demonstrated wheels show broad solid discs, not exposed spokes.
        # Overlay discs remain behind the pre-existing hub extremum and within tyre radius.
        group.append(annulus('Wheel_'+tag+'_Solid_Disc',.01,r*.695,y+sgn*.10,RIM))
        group.append(annulus('Wheel_'+tag+'_Solid_Disc_Front_Center',.01,r*.635,y+sgn*.44,RIM))
        group.append(annulus('Wheel_'+tag+'_Disc_Edge_Groove',r*.66,r*.675,y+sgn*.11,SHADOW))
        for k in range(24):
            a=k*math.tau/24
            pts=[(rr*math.cos(ang),y+sgn*.01,rr*math.sin(ang)) for rr,ang in
                 [(r*.70,a-.012),(r*.76,a-.012),(r*.76,a+.012),(r*.70,a+.012)]]
            group.append(mesh('Wheel_'+tag+'_Shallow_Rim_Groove_'+str(k+1),pts,[(0,1,2,3)],SHADOW,WHEELS,False))
        for obj in group:obj.location=center
        wheel_groups[tag]=group
        wheel_centers[tag]={'blender_cm':list(center),'unreal_cm':[center.x,-center.y,center.z],
                            'radius_cm':r,'width_cm':width}

def bounds(objects):
    deps=bpy.context.evaluated_depsgraph_get(); points=[]
    for obj in objects:
        evaluated=obj.evaluated_get(deps)
        points += [evaluated.matrix_world@Vector(p) for p in evaluated.bound_box]
    mins=[min(v[i] for v in points) for i in range(3)]
    maxs=[max(v[i] for v in points) for i in range(3)]
    return {'min_cm':mins,'max_cm':maxs,'size_cm':[maxs[i]-mins[i] for i in range(3)]}

body_objects=list(BODY.objects)
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_clearance_geometry import apply_clearance_adjustment
clearance_adjustment=apply_clearance_adjustment(ROOT,body_objects,P)
all_vehicle=body_objects+list(WHEELS.objects)
vehicle_bounds=bounds(all_vehicle)

def export_part(filename,objects,pivot):
    # Export evaluated copies joined into exactly one static mesh.
    deps=bpy.context.evaluated_depsgraph_get()
    copies=[]
    bpy.ops.object.select_all(action='DESELECT')
    for src in objects:
        me=bpy.data.meshes.new_from_object(src.evaluated_get(deps),depsgraph=deps)
        ob=bpy.data.objects.new('Export_'+src.name,me)
        scene.collection.objects.link(ob)
        ob.matrix_world=src.matrix_world.copy()
        ob.location -= Vector(pivot)
        ob.select_set(True);copies.append(ob)
    bpy.context.view_layer.objects.active=copies[0]
    bpy.ops.object.join()
    out=copies[0];out.name=Path(filename).stem
    scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    tri=out.modifiers.new('Explicit deterministic triangles','TRIANGULATE')
    bpy.context.view_layer.objects.active=out
    bpy.ops.object.modifier_apply(modifier=tri.name)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=0.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.export_scene.fbx(filepath=str(OUT/'FBX'/filename),use_selection=True,use_metadata=False,
        object_types={'MESH'},global_scale=1.0,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='Y',axis_up='Z',
        use_space_transform=True,bake_space_transform=False,use_mesh_modifiers=True,
        mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,bake_anim=False,path_mode='AUTO')
    info={'file':'FBX/'+filename,'vertices':len(out.data.vertices),
          'triangles':len(out.data.polygons),'material_slots':[m.name for m in out.data.materials],
          'bounds_local_cm':bounds([out]),'pivot_source_cm':list(pivot)}
    bpy.data.objects.remove(out,do_unlink=True)
    return info

parts={}
parts['body']=export_part('SM_Roadster_Blockout_Body.fbx',body_objects,(0,0,0))
for tag,objects in wheel_groups.items():
    parts[tag]=export_part('SM_Roadster_Wheel_'+tag+'.fbx',objects,wheel_centers[tag]['blender_cm'])

# Preview setup is excluded from every FBX. CPU rendering is opt-in.
floor=cube('Preview_Ground',(0,0,-2),(1300,1100,2),material('M_Preview_Ground',(.075,.085,.095),0,.65),CHECK,0)
world=bpy.data.worlds.new('Preview_World') if not scene.world else scene.world
scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.25,.29,.34,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.45

def area(name,loc,power,size):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new(name,data);CHECK.objects.link(ob);ob.location=loc
    ob.rotation_euler=(Vector((0,0,50))-ob.location).to_track_quat('-Z','Y').to_euler()

area('Preview_Key',(260,-380,650),10000000,450)
area('Preview_Fill',(-150,350,300),7500000,350)
area('Preview_Rear',(-400,-170,300),5000000,250)
camera_data=bpy.data.cameras.new('Blockout_Inspection_Camera')
camera=bpy.data.objects.new('Blockout_Inspection_Camera',camera_data)
CHECK.objects.link(camera);scene.camera=camera
camera_data.type='ORTHO';camera_data.ortho_scale=650
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=4
scene.render.resolution_x=1100;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
camera.location=(600,-700,390)
camera.rotation_euler=(Vector((0,0,53))-camera.location).to_track_quat('-Z','Y').to_euler()
scene['asset_status']='EXTERIOR BLOCKOUT / ASSUMED SCALE / NOT OFFICIAL CAD'
scene['visible_reference']='Native Tesla X The Ramp frames0/300 and official broadcast sample081; see research evidence and vehicle_assumptions.md'
scene['coordinates']='cm; +X front, +Y left, +Z up. UE import settings and mirror in manifest.'
scene['parameter_file']='//vehicle_parameters.json'

bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Roadster_Exterior_Blockout.blend'))
if '--preview' in sys.argv:
    for name,loc,scale in [
        ('front_three_quarter',(600,-700,390),650),
        ('rear_three_quarter',(-620,-700,330),650),
        ('side_orthographic',(0,-950,120),570),
        ('top_orthographic',(0,0,1000),580)]:
        camera.location=loc;camera_data.ortho_scale=scale
        direction=Vector((0,0,53))-camera.location
        camera.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/'Previews'/(name+'.png'))
        bpy.ops.render.render(write_still=True)

manifest={
    'schema_version':1,'blender_version':bpy.app.version_string,
    'status':'editable exterior silhouette blockout; not precision asset, not official CAD',
    'parameters':P,'source_coordinates':'centimeters; +X front +Y left +Z up',
    'unreal_coordinates':'centimeters; +X front +Y right +Z up',
    'source_to_unreal_position':'[x, -y, z]',
    'vehicle_bounds_cm':vehicle_bounds,'wheel_centers':wheel_centers,
    'parameter_semantics':'parameters describe nominal design inputs before the explicitly recorded clearance correction; vehicle_bounds_cm is actual exported geometry',
    'clearance_adjustment':clearance_adjustment,
    'unreal_fbx_import':{'convert_scene':False,'convert_scene_unit':True,
        'force_front_x_axis':False,'import_uniform_scale':1.0,
        'import_rotation':'0,0,0','combine_meshes':True,
        'transform_vertex_to_absolute':True,'auto_generate_collision':False,
        'import_materials':False,'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS'},
    'parts':parts,'render_device':'CPU only; 4 threads; previews if --preview',
    'notes':[
        'body origin: assumed wheelbase midpoint on ground, not measured center of mass',
        'wheel files: origin at own axle center; place using unreal_cm offsets',
        'wheel spin axis is local Y after import; validate sign with forward travel',
        'no animation, fans, plumbing, interior, or physical claims generated; four rear circular apertures are visual observations only',
        'rear plate RDSTR, aperture lips, dark diffuser perimeter and wheel discs are observed appearance details; candidate2 overhang correction changes the previous outer envelope',
        'underside uses dark material slots and approximate panel seams; local floor correction is an explicit scene-consistency hypothesis, not measured mechanics',
        'body FBX includes fixed glazing and lights using editable material slots',
        'FBX axis metadata Y-forward/Z-up with identity export; UE convert_scene intentionally disabled',
    ]}
for part in parts.values():
    f=OUT/part['file'];part['sha256']=hashlib.sha256(f.read_bytes()).hexdigest();part['bytes']=f.stat().st_size
(OUT/'vehicle_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('ROADSTER_BLOCKOUT_GENERATED '+str(OUT/'vehicle_manifest.json'))
