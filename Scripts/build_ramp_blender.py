"""Continuous editable ribbon surface; dimensions come from explicit fit hypotheses."""
import bpy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
pts=json.loads((ROOT/'Data/ramp_dense.json').read_text());params=json.loads((ROOT/'Data/ramp_parameters.json').read_text())
verts=[];faces=[];indices=[]
def strip(ya,yb,offset,slot):
    start=len(verts)
    for p in pts:
        a=math.radians(p['pitch']);x,y,z=p['p']
        for yy in [ya,yb]:verts.append(((x-math.sin(a)*offset)/100,-yy/100,(z+math.cos(a)*offset)/100))
    for i in range(len(pts)-1):
        k=start+i*2;faces.append((k,k+2,k+3,k+1) if slot==1 else (k,k+1,k+3,k+2));indices.append(slot)
w=params['width_cm'];th=params['surface_thickness_cm']
strip(-w/2,w/2,0,0);strip(-w/2,w/2,-th,1)
strip(-3,3,.8,2);strip(-w/2,-w/2+3,1,3);strip(w/2-3,w/2,1,3)
mesh=bpy.data.meshes.new('RampRibbon_Continuous');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('SM_Ramp_Ribbon',mesh);bpy.context.collection.objects.link(obj)
for name,color in [('RampSurface',(.32,.34,.36,1)),('TrussSteel',(.14,.17,.2,1)),('LaneStripe',(.65,.68,.7,1)),('RampEdge',(.7,.008,.005,1))]:
    m=bpy.data.materials.new(name);m.diffuse_color=color;obj.data.materials.append(m)
for p,slot in zip(mesh.polygons,indices):p.material_index=slot;p.use_smooth=True
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(60));bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'AssetsSource/Ramp_Editable.blend'))
# Same explicit Blender-right-handed to Unreal-left-handed export policy as vehicle.
bpy.ops.export_scene.fbx(filepath=str(ROOT/'AssetsSource/FBX/SM_Ramp_Ribbon.fbx'),use_selection=True,use_metadata=False,global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='Y',axis_up='Z',bake_space_transform=False,use_mesh_modifiers=True,mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False)
