"""UE 5.4 editor Python: prepare an additional visible-car mask MRQ pass.

Run only when the main reconstruction process has finished. This script never
starts a render, changes project Config, replaces color materials, or changes the
source render preset. It saves stencil flags in the configured map and creates
an owned material plus a copied MRQ preset. The normal color pass is retained.

Optional settings: <project>/Data/mask_pass_settings.json (not created here).
Keys: map, sequence, source_preset, mask_preset, material_path, output_directory,
car_actor_labels, depth_tolerance_cm, require_custom_depth_stencil.
ROOT is resolved from the running Unreal project, not a machine-specific path.

Verified against installed Epic UE 5.4 C++ headers/source:
  MoviePipelineDeferredPasses.h: FMoviePipelinePostProcessPass has only bEnabled
    and Material; there is NO Name property in 5.4.
  MoviePipelineDeferredPasses.cpp: GatherOutputPassesImpl concatenates deferred
    PassIdentifier.Name + Material.GetName(); asset name CarMask gives the suffix.
  MaterialExpressionSceneTexture.h / MaterialSceneTextureId.h: SceneTextureId,
    PPI_CustomStencil, PPI_CustomDepth, PPI_SceneDepth.
  Material.h / BlendableInterface.h: MD_PostProcess, BlendableLocation,
    BL_SceneColorAfterTonemapping (the old BL_AfterTonemapping is deprecated).
  MaterialEditingLibrary.h: GetMaterialExpressionInputNames, connections,
    DeleteAllMaterialExpressions, RecompileMaterial.

Visible mask = (CustomStencil == 1) AND (CustomDepth <= SceneDepth + tolerance).
Depth comparison prevents an opaque occluder from revealing a hidden car.
Fog/translucency visibility and reference-image segmentation remain separate QA
problems. This is a geometric visible-opaque mask, not a smoke segmentation mask.
"""
import json
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OWNER = 'RoadsterV2_CarMask_v1'
CONFIG = {
    'map': '/Game/Maps/Ramp_Reconstruction_Draft',
    'sequence': '/Game/Sequences/SEQ_Ramp_Draft',
    'source_preset': '/Game/Render/Ramp_Smoke',
    'mask_preset': '/Game/Render/Ramp_Smoke_CarMask',
    'material_path': '/Game/Render/Masks/CarMask',
    'output_directory': '{project_dir}Renders/mask_validation',
    'car_actor_labels': ['Roadster_Draft_Kinematic','Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR'],
    'depth_tolerance_cm': 2.0,
    'require_custom_depth_stencil': True,
}
settings = ROOT / 'Data' / 'mask_pass_settings.json'
if settings.exists():
    overrides = json.loads(settings.read_text(encoding='utf-8-sig'))
    unknown = set(overrides) - set(CONFIG)
    if unknown:
        raise RuntimeError('Unknown mask settings: ' + ', '.join(sorted(unknown)))
    CONFIG.update(overrides)

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def enum_value(enum_class, *names):
    for name in names:
        if hasattr(enum_class, name):
            return getattr(enum_class, name)
    raise RuntimeError('Required enum missing: ' + str(enum_class) + ': ' + ', '.join(names))

def checked_asset(path, expected_class):
    asset = unreal.load_asset(path)
    if not asset or not isinstance(asset, expected_class):
        raise RuntimeError('Expected ' + str(expected_class) + ' asset: ' + path)
    return asset

def owned_existing(path, expected_class):
    if not EAL.does_asset_exist(path):
        return None
    asset = checked_asset(path, expected_class)
    if str(EAL.get_metadata_tag(asset, 'RoadsterMaskOwner')) != OWNER:
        raise RuntimeError('Refusing to overwrite an unowned asset: ' + path)
    return asset

def expression(material, cls, x, y):
    result = MEL.create_material_expression(material, cls, x, y)
    if not result:
        raise RuntimeError('Could not create material expression: ' + str(cls))
    return result

def connect(source, destination, *input_names, output=''):
    available = list(MEL.get_material_expression_input_names(destination))
    canonical = lambda s: ''.join(str(s).lower().split()).replace('_','')
    selected = next((actual for alias in input_names for actual in available
                     if canonical(actual) == canonical(alias)), None)
    if selected is None and len(available)==1 and str(available[0])=='None':
        selected=''
    if selected is None:
        raise RuntimeError('Material input not found: ' + str(input_names) + '; actual=' + str(available))
    if not MEL.connect_material_expressions(source, output, destination, selected):
        raise RuntimeError('Material connection failed: ' + str(selected))

def constant(material, value, x, y):
    e = expression(material, unreal.MaterialExpressionConstant, x, y)
    e.set_editor_property('r', float(value))
    return e

def scene_scalar(material, scene_id, x, y):
    tex = expression(material, unreal.MaterialExpressionSceneTexture, x, y)
    tex.set_editor_property('scene_texture_id', scene_id)
    tex.set_editor_property('filtered', False)
    channel = expression(material, unreal.MaterialExpressionComponentMask, x+180, y)
    for name, value in [('r',True),('g',False),('b',False),('a',False)]:
        channel.set_editor_property(name,value)
    connect(tex,channel,'Input',output='Color')
    return channel

def compare(material, a, b, greater, equal, less, x, y):
    e = expression(material, unreal.MaterialExpressionIf, x, y)
    e.set_editor_property('equals_threshold', 0.00001)
    connect(a,e,'A'); connect(b,e,'B')
    connect(greater,e,'A > B','AGreaterThanB')
    connect(equal,e,'A == B','AEqualsB')
    connect(less,e,'A < B','ALessThanB')
    return e

def create_mask_material():
    path = CONFIG['material_path']
    material = owned_existing(path,unreal.Material)
    if not material:
        folder,name = path.rsplit('/',1)
        EAL.make_directory(folder)
        material = ASSETS.create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError('Could not create mask material')
    EAL.set_metadata_tag(material,'RoadsterMaskOwner',OWNER)
    MEL.delete_all_material_expressions(material)
    material.set_editor_property('material_domain',unreal.MaterialDomain.MD_POST_PROCESS)
    material.set_editor_property('blendable_location',enum_value(unreal.BlendableLocation,
        'BL_SCENE_COLOR_AFTER_TONEMAPPING','BL_AFTER_TONEMAPPING'))
    # Run over every pixel: hardware stencil test would retain scene color outside.
    material.set_editor_property('enable_stencil_test',False)
    zero = constant(material,0,-700,500)
    one = constant(material,1,-700,600)
    tolerance = constant(material,CONFIG['depth_tolerance_cm'],-700,700)
    stencil = scene_scalar(material,unreal.SceneTextureId.PPI_CUSTOM_STENCIL,-1100,-100)
    custom_depth = scene_scalar(material,unreal.SceneTextureId.PPI_CUSTOM_DEPTH,-1100,150)
    scene_depth = scene_scalar(material,unreal.SceneTextureId.PPI_SCENE_DEPTH,-1100,350)
    selected = compare(material,stencil,one,zero,one,zero,-400,-100)
    depth_limit = expression(material,unreal.MaterialExpressionAdd,-400,350)
    connect(scene_depth,depth_limit,'A');connect(tolerance,depth_limit,'B')
    visible = compare(material,custom_depth,depth_limit,zero,one,one,-150,200)
    final = expression(material,unreal.MaterialExpressionMultiply,100,0)
    connect(selected,final,'A');connect(visible,final,'B')
    if not MEL.connect_material_property(final,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError('Failed to connect mask to EmissiveColor')
    MEL.layout_material_expressions(material)
    MEL.recompile_material(material)
    if not EAL.save_loaded_asset(material):
        raise RuntimeError('Could not save mask material')
    return material

def create_preset(source,material):
    target = CONFIG['mask_preset']
    if target == CONFIG['source_preset']:
        raise RuntimeError('Mask preset must differ from source color preset')
    preset = owned_existing(target,unreal.MoviePipelinePrimaryConfig)
    if not preset:
        folder,name = target.rsplit('/',1)
        EAL.make_directory(folder)
        preset = ASSETS.create_asset(name,folder,unreal.MoviePipelinePrimaryConfig,
                                    unreal.MoviePipelinePrimaryConfigFactory())
    preset.copy_from(source)
    EAL.set_metadata_tag(preset,'RoadsterMaskOwner',OWNER)
    deferred = preset.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    deferred.set_editor_property('render_main_pass',True)
    deferred.set_editor_property('disable_multisample_effects',True)
    # Do not let MRQ actor-layer passes temporarily rewrite our stencil ids.
    deferred.set_editor_property('actor_layers',[])
    deferred.set_editor_property('data_layers',[])
    deferred.set_editor_property('add_default_layer',False)
    pass_entry = unreal.MoviePipelinePostProcessPass()
    pass_entry.set_editor_property('enabled',True)
    pass_entry.set_editor_property('material',material)
    # 5.4 has NO name member. Asset name is the render-pass suffix.
    deferred.set_editor_property('additional_post_process_materials',[pass_entry])
    aa = preset.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property('spatial_sample_count',1)
    aa.set_editor_property('temporal_sample_count',1)
    aa.set_editor_property('override_anti_aliasing',True)
    aa.set_editor_property('anti_aliasing_method',unreal.AntiAliasingMethod.AAM_NONE)
    output = preset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    output.set_editor_property('output_directory',unreal.DirectoryPath(CONFIG['output_directory']))
    output.set_editor_property('file_name_format','{sequence_name}.{render_pass}.{frame_number}')
    preset.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    if not EAL.save_loaded_asset(preset):
        raise RuntimeError('Could not save derived mask preset')
    return preset

def main():
    for key in ('map','sequence','source_preset','mask_preset','material_path'):
        if not str(CONFIG[key]).startswith('/Game/'):
            raise RuntimeError(key + ' must be a project /Game asset path')
    if not 0<=float(CONFIG['depth_tolerance_cm'])<=5:
        raise RuntimeError('Depth tolerance must be between0 and5cm; do not mask fitting errors with a large tolerance')
    custom_depth = unreal.SystemLibrary.get_console_variable_int_value('r.CustomDepth')
    if custom_depth != 3:
        message = ('Car mask requires r.CustomDepth=3 (Enabled with Stencil). '
                   'Set it for the eventual render process/project before rendering. '
                   'This script does not modify Config or console variables; current value=' + str(custom_depth))
        if CONFIG['require_custom_depth_stencil']:
            raise RuntimeError(message)
        unreal.log_warning(message)
    source = checked_asset(CONFIG['source_preset'],unreal.MoviePipelinePrimaryConfig)
    sequence = checked_asset(CONFIG['sequence'],unreal.LevelSequence)
    if not LEVELS.load_level(CONFIG['map']):
        raise RuntimeError('Could not load configured map')
    labels = set(CONFIG['car_actor_labels'])
    found = {label:[] for label in labels}
    primitives = []
    for actor in ACTORS.get_all_level_actors():
        label = actor.get_actor_label()
        if label in found:
            found[label].append(actor)
        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            primitives.append((actor,component,label in labels))
    bad = {label:len(actors) for label,actors in found.items() if len(actors)!=1}
    if bad:
        raise RuntimeError('Expected exactly one actor for each car part: ' + str(bad))
    selected = [(a,c) for a,c,is_car in primitives if is_car and isinstance(c,unreal.MeshComponent)]
    if len(selected)!=5:
        raise RuntimeError('Expected five car mesh components (body+four wheels), got ' + str(len(selected)))
    material = create_mask_material()
    preset = create_preset(source,material)
    snapshot = []
    try:
        for actor,component,is_car in primitives:
            snapshot.append((component,
                component.get_editor_property('render_custom_depth'),
                component.get_editor_property('custom_depth_stencil_value'),
                component.get_editor_property('custom_depth_stencil_write_mask')))
            component.set_custom_depth_stencil_value(1 if is_car else 0)
            component.set_custom_depth_stencil_write_mask(unreal.RendererStencilMask.ERSM_DEFAULT)
            component.set_render_custom_depth(is_car)
        if not LEVELS.save_current_level():
            raise RuntimeError('Could not save map stencil flags')
    except Exception:
        for component,enabled,value,write_mask in snapshot:
            component.set_custom_depth_stencil_value(value)
            component.set_custom_depth_stencil_write_mask(write_mask)
            component.set_render_custom_depth(enabled)
        raise
    report = dict(status='setup_saved_render_not_run',map=CONFIG['map'],
        sequence=sequence.get_path_name(),source_color_preset=CONFIG['source_preset'],
        derived_mask_preset=preset.get_path_name(),material=material.get_path_name(),
        render_main_pass=True,car_stencil_id=1,other_stencil_id=0,
        expected_mask_pass_suffix=material.get_name(),
        expected_default_pass_names=['FinalImage','FinalImage'+material.get_name()],
        filename_format='{sequence_name}.{render_pass}.{frame_number}',
        custom_depth_cvar_at_setup=custom_depth,render_process_requires_custom_depth_3=True,
        car_components=[dict(actor=a.get_actor_label(),component=c.get_path_name()) for a,c in selected],
        other_primitive_count=len(primitives)-len(selected),depth_tolerance_cm=CONFIG['depth_tolerance_cm'],
        color_preset_unchanged=True,color_materials_unchanged=True,
        derived_preset_multisample_effects_disabled=True,
        mask_semantics='binary car stencil with opaque-scene depth occlusion; no fog/translucency segmentation',
        validation='Not rendered or measured by this setup. Check black/white nonempty mask, alignment and labels before IoU/center metrics.')
    out = ROOT/'Validation'/'mask_pass_setup.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('ROADSTER_MASK_PASS_SETUP_SAVED ' + json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    main()
