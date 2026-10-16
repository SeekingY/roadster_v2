import unreal, math
from pathlib import Path
ASSETS=unreal.AssetToolsHelpers.get_asset_tools()
EAL=unreal.EditorAssetLibrary
ACTORS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def load_if(path):
    return EAL.load_asset(path) if EAL.does_asset_exist(path) else None

def material(name,color,metallic=0.0,roughness=0.5,emissive=0.0):
    m=load_if('/Game/Materials/'+name)
    if m:return m
    m=ASSETS.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    c=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionConstant3Vector)
    c.set_editor_property('constant',unreal.LinearColor(*color,1))
    unreal.MaterialEditingLibrary.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
    for value,prop in [(metallic,unreal.MaterialProperty.MP_METALLIC),(roughness,unreal.MaterialProperty.MP_ROUGHNESS)]:
        e=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionConstant)
        e.set_editor_property('r',value)
        unreal.MaterialEditingLibrary.connect_material_property(e,'',prop)
    if emissive:
        e=unreal.MaterialEditingLibrary.create_material_expression(m,unreal.MaterialExpressionConstant3Vector)
        e.set_editor_property('constant',unreal.LinearColor(*(v*emissive for v in color),1))
        unreal.MaterialEditingLibrary.connect_material_property(e,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m

def mesh_actor(label,mesh,loc=(0,0,0),rotation=None,scale=(1,1,1),mat=None):
    a=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*loc),rotation or unreal.Rotator())
    a.set_actor_label(label)
    a.static_mesh_component.set_static_mesh(mesh)
    a.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    a.static_mesh_component.set_simulate_physics(False)
    a.set_actor_scale3d(unreal.Vector(*scale))
    if mat:a.static_mesh_component.set_material(0,mat)
    return a

def beam(label,p0,p1,width,mat,cube):
    a,b=unreal.Vector(*p0),unreal.Vector(*p1)
    d=(b-a).length()
    return mesh_actor(label,cube,tuple((p0[i]+p1[i])/2 for i in range(3)),unreal.MathLibrary.find_look_at_rotation(a,b),(d/100,width/100,width/100),mat)

def transform_track(seq,actor,frames,values):
    bind=seq.add_possessable(actor)
    section=bind.add_track(unreal.MovieScene3DTransformTrack).add_section()
    section.set_range(frames[0],frames[-1]+1)
    channels=section.get_channels_by_type(unreal.MovieSceneScriptingDoubleChannel)
    by_name={str(c.get_editor_property('channel_name')):c for c in channels}
    names=['Location.X','Location.Y','Location.Z','Rotation.X','Rotation.Y','Rotation.Z','Scale.X','Scale.Y','Scale.Z']
    ch=[by_name[n] for n in names]
    for i in range(9):
        ch[i].set_default(values[0][i])
        for frame,value in zip(frames,values):
            ch[i].add_key(unreal.FrameNumber(frame),value[i],interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    section.set_editor_property('use_quaternion_interpolation',False)
    return bind

def camera(label,loc,target,focal=35):
    pos=unreal.Vector(*loc)
    a=ACTORS.spawn_actor_from_class(unreal.CineCameraActor,pos,unreal.MathLibrary.find_look_at_rotation(pos,unreal.Vector(*target)))
    a.set_actor_label(label)
    c=a.get_cine_camera_component()
    lens=unreal.CameraLensSettings();lens.set_editor_property('min_focal_length',1.0);lens.set_editor_property('max_focal_length',1000.0)
    c.set_editor_property('lens_settings',lens)
    c.set_editor_property('current_focal_length',focal)
    c.set_editor_property('current_aperture',8.0)
    film=unreal.CameraFilmbackSettings()
    film.set_editor_property('sensor_width',36.0)
    film.set_editor_property('sensor_height',20.25)
    c.set_editor_property('filmback',film)
    focus=unreal.CameraFocusSettings()
    focus.set_editor_property('focus_method',unreal.CameraFocusMethod.DISABLE)
    c.set_editor_property('focus_settings',focus)
    return a

def cut_track(seq,cam,start,end,binding=None):
    binding=binding or seq.add_possessable(cam)
    tracks=[t for t in seq.get_tracks() if isinstance(t,unreal.MovieSceneCameraCutTrack)]
    cut=(tracks[0] if tracks else seq.add_track(unreal.MovieSceneCameraCutTrack)).add_section()
    cut.set_range(start,end)
    bid=unreal.MovieSceneObjectBindingID()
    bid.set_editor_property('guid',binding.get_id())
    cut.set_camera_binding_id(bid)
    return binding

def focal_track(seq,cam,parent,frames,values):
    bind=seq.add_possessable(cam.get_cine_camera_component())
    bind.set_parent(parent)
    track=bind.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path('CurrentFocalLength','CurrentFocalLength')
    section=track.add_section();section.set_range(frames[0],frames[-1]+1)
    channel=section.get_channels_by_type(unreal.MovieSceneScriptingFloatChannel)[0]
    channel.set_default(values[0])
    for f,v in zip(frames,values):channel.add_key(unreal.FrameNumber(f),v,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)

def render_preset(name,folder,width,height,fps=24000,denominator=1001):
    p=load_if('/Game/Render/'+name)
    if not p:p=ASSETS.create_asset(name,'/Game/Render',unreal.MoviePipelinePrimaryConfig,unreal.MoviePipelinePrimaryConfigFactory())
    o=p.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    # Store portable output paths in presets instead of personal absolute paths.
    root=Path(__file__).resolve().parents[1]
    try:
        folder='{project_dir}'+Path(folder).resolve().relative_to(root).as_posix()
    except ValueError:
        pass
    o.set_editor_property('output_directory',unreal.DirectoryPath(folder))
    o.set_editor_property('file_name_format',name+'.{frame_number}')
    o.set_editor_property('output_resolution',unreal.IntPoint(width,height))
    o.set_editor_property('use_custom_frame_rate',True)
    o.set_editor_property('output_frame_rate',unreal.FrameRate(fps,denominator))
    p.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    p.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    aa=p.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property('spatial_sample_count',1)
    aa.set_editor_property('temporal_sample_count',1)
    aa.set_editor_property('engine_warm_up_count',16)
    # UE5.4 MRQ overwrites MotionBlurAmount from its shutter default even when
    # r.DefaultFeature.MotionBlur=False. Disable the renderer pass explicitly;
    # keep bloom, geometry, source cadence and evaluation timing unchanged.
    console=p.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    assert console.add_or_update_console_variable('r.MotionBlurQuality',0.0)
    console.update_console_variable_enable_state('r.MotionBlurQuality',True)
    EAL.save_loaded_asset(p)
    return p
