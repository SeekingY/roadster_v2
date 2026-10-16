"""Public-copy metadata cleanup using Blender APIs; preserves evaluated geometry."""
import bpy,json,hashlib,re,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
assert ROOT.name=='roadster_v2_public','Run only inside the public copy'
REPORT=Path(os.environ.get('ROADSTER_PUBLIC_AUDIT_DIR',str(ROOT/'Saved')))/'PublicBlenderMetadata.json';REPORT.parent.mkdir(parents=True,exist_ok=True)
def signature():
    deps=bpy.context.evaluated_depsgraph_get();items=[]
    for ob in sorted(bpy.data.objects,key=lambda o:o.name):
        if ob.type!='MESH':continue
        ev=ob.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles()
        items.append({'name':ob.name,'world_matrix':[list(row) for row in ev.matrix_world],
          'vertices':[list(v.co) for v in me.vertices],'triangles':[list(t.vertices) for t in me.loop_triangles],
          'triangle_materials':[t.material_index for t in me.loop_triangles],'materials':[m.name if m else None for m in me.materials]})
        ev.to_mesh_clear()
    return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
def clean_string(v):
    if re.search(r'[A-Za-z]:[\\/]',v) or '/Users/' in v or '\\Users\\' in v:
        v=v.replace('\\','/')
        return '//'+v.rsplit('/',1)[-1]
    return v
report={'scope':'Public-copy metadata only; no new image-fidelity claim','files':[]}
for filename in ['Roadster_Exterior_Blockout.blend','Ramp_Editable.blend']:
    path=ROOT/'AssetsSource'/filename;bpy.ops.wm.open_mainfile(filepath=str(path));before=signature();changes=[]
    bpy.context.preferences.filepaths.save_version=0
    for collection in ['scenes','objects','meshes','materials','collections','worlds','cameras','lights','actions']:
        for block in getattr(bpy.data,collection):
            for key in list(block.keys()):
                value=block[key]
                if isinstance(value,str) and clean_string(value)!=value:
                    block[key]=clean_string(value);changes.append({'data_block':block.name,'property':key,'replacement':block[key]})
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type=='FILE_BROWSER' and space.params is not None:
                    # RNA writes a C string; overwrite its old fixed buffer first so
                    # shortened values do not retain private bytes past the terminator.
                    space.params.directory=b'/'*1000
                    space.params.directory=b'//';changes.append({'screen':screen.name,'property':'FileBrowser.directory','replacement':'//'})
    for img in bpy.data.images:
        if img.filepath and clean_string(img.filepath)!=img.filepath:
            img.filepath=clean_string(img.filepath);changes.append({'image':img.name,'property':'filepath','replacement':img.filepath})
    bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False,relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(path));after=signature();assert before==after
    report['files'].append({'file':'AssetsSource/'+filename,'mesh_signature_before':before,'mesh_signature_after':after,'geometry_unchanged':True,'metadata_changes':changes})
    if filename=='Ramp_Editable.blend':
        original_obj=bpy.data.objects['SM_Ramp_Ribbon'];expected=[list(v.co) for v in original_obj.data.vertices]
        unit_scale=bpy.context.scene.unit_settings.scale_length
        # Blender4.2's exporter still emits ApplicationNativeFile when use_metadata=False.
        # Append the exact saved object to an unsaved scene so bpy.data.filepath is empty.
        bpy.ops.wm.read_factory_settings(use_empty=True)
        with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.objects=['SM_Ramp_Ribbon']
        obj=dst.objects[0];bpy.context.scene.collection.objects.link(obj)
        assert [list(v.co) for v in obj.data.vertices]==expected
        bpy.context.scene.unit_settings.scale_length=unit_scale
        bpy.context.view_layer.objects.active=obj;obj.select_set(True);assert bpy.data.filepath==''
        target=ROOT/'AssetsSource/FBX/SM_Ramp_Ribbon.fbx'
        bpy.ops.export_scene.fbx(filepath=str(target),use_selection=True,global_scale=1,apply_unit_scale=True,
          apply_scale_options='FBX_SCALE_UNITS',axis_forward='Y',axis_up='Z',bake_space_transform=False,
          use_mesh_modifiers=True,mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,use_metadata=False)
        raw=target.read_bytes();assert b'Users' not in raw
        report['ramp_fbx']={'file':'AssetsSource/FBX/SM_Ramp_Ribbon.fbx','source_vertices_identical':True,
          'method':'Append exact object into unsaved scene, export through BlenderFBX API; ApplicationNativeFile empty',
          'sha256':hashlib.sha256(raw).hexdigest()}
REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PUBLIC_BLENDER_METADATA_CLEAN_OK',json.dumps(report))
