import unreal,sys,os,json,csv,math
ROOT=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
sys.path.insert(0,os.path.join(ROOT,'Scripts'))
from unreal_helpers import *
from author_appearance import surface_detail,add_visible_gas
from author_environment import add_visible_ground_details
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
for p in ['/Game/Maps','/Game/Vehicle','/Game/Materials','/Game/Sequences','/Game/Render']:EAL.make_directory(p)
manifest=json.load(open(os.path.join(ROOT,'AssetsSource','vehicle_manifest.json')))
materials={
'M_Blockout_Silver':material('M_BodySilverV2',(.58,.61,.66),.25,.26),
'M_Blockout_BlackGlass':material('M_BlackGlass',(.015,.022,.03),.4,.13),
'M_Blockout_DarkTrim':material('M_DarkTrim',(.018,.02,.024),.1,.55),
'M_Blockout_Headlight':material('M_Headlight',(.7,.85,1),.1,.2,5),
'M_Blockout_RedTail':material('M_RedTail',(.7,.008,.004),.1,.2,5),
'M_Blockout_Tire':material('M_Tire',(.014,.016,.018),0,.87),
'M_Blockout_Rim':material('M_Rim',(.23,.25,.28),.8,.24)}
parts={}; bounds={}
for key,part in manifest['parts'].items():
    file=os.path.join(ROOT,'AssetsSource',part['file']);name=os.path.splitext(os.path.basename(file))[0]
    task=unreal.AssetImportTask()
    task.set_editor_property('filename',file);task.set_editor_property('destination_path','/Game/Vehicle')
    task.set_editor_property('destination_name',name);task.set_editor_property('automated',True)
    task.set_editor_property('replace_existing',True);task.set_editor_property('save',True)
    ui=unreal.FbxImportUI();ui.set_editor_property('import_mesh',True);ui.set_editor_property('import_as_skeletal',False)
    ui.set_editor_property('import_materials',False);ui.set_editor_property('import_textures',False)
    ui.set_editor_property('automated_import_should_detect_type',False);ui.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_STATIC_MESH)
    d=ui.static_mesh_import_data
    for prop,value in [('combine_meshes',True),('auto_generate_collision',False),('convert_scene',False),('convert_scene_unit',True),('force_front_x_axis',False),('transform_vertex_to_absolute',True)]:d.set_editor_property(prop,value)
    d.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task.set_editor_property('options',ui);ASSETS.import_asset_tasks([task])
    sm=unreal.load_asset('/Game/Vehicle/'+name);parts[key]=sm
    slots=sm.get_editor_property('static_materials')
    for i,slot in enumerate(slots):
        name=str(slot.get_editor_property('material_slot_name'))
        if name in materials:sm.set_material(i,materials[name])
    EAL.save_loaded_asset(sm)
    b=sm.get_bounds();bounds[key]={'center':[b.origin.x,b.origin.y,b.origin.z],'extent':[b.box_extent.x,b.box_extent.y,b.box_extent.z],'slots':[str(s.material_slot_name) for s in slots]}
if not 200<bounds['body']['extent'][0]<260:raise RuntimeError('FBX dimensions/axes failed: '+str(bounds['body']))
map_path='/Game/Maps/Ramp_Reconstruction_Draft'
if EAL.does_asset_exist(map_path):
    assert levels.load_level(map_path)
    for a in ACTORS.get_all_level_actors():
        if not isinstance(a,unreal.WorldSettings):ACTORS.destroy_actor(a)
else:
    assert levels.new_level(map_path)
cube=unreal.load_asset('/Engine/BasicShapes/Cube')
road=material('M_RampSurface',(.32,.34,.36),.15,.72)
steel=material('M_TrussSteel',(.14,.17,.2),.7,.4)
stripe=material('M_LaneStripe',(.65,.68,.70),0,.75)
edge=material('M_RampEdge',(.7,.008,.005),.2,.5,3)
ground=material('M_NightConcreteV3',(.003,.0035,.0045),0,.72)
mesh_actor('TestPad_hypothesis',cube,(-4000,0,-25),scale=(500,500,.5),mat=ground)
points=json.load(open(os.path.join(ROOT,'Data','ramp_dense.json')))
params=json.load(open(os.path.join(ROOT,'Data','ramp_parameters.json')))
width=params['width_cm']; thick=params['surface_thickness_cm']
ramp_task=unreal.AssetImportTask();ramp_task.set_editor_property('filename',os.path.join(ROOT,'AssetsSource','FBX','SM_Ramp_Ribbon.fbx'))
ramp_task.set_editor_property('destination_path','/Game/Vehicle');ramp_task.set_editor_property('automated',True);ramp_task.set_editor_property('replace_existing',True);ramp_task.set_editor_property('save',True)
ramp_task.set_editor_property('options',ui);ASSETS.import_asset_tasks([ramp_task])
ramp_mesh=unreal.load_asset('/Game/Vehicle/SM_Ramp_Ribbon')
rb=ramp_mesh.get_bounds();bounds['ramp']={'center':[rb.origin.x,rb.origin.y,rb.origin.z],'extent':[rb.box_extent.x,rb.box_extent.y,rb.box_extent.z]}
for i,slot in enumerate(ramp_mesh.static_materials):
    ramp_mesh.set_material(i,{'RampSurface':road,'TrussSteel':steel,'LaneStripe':stripe,'RampEdge':edge}[str(slot.material_slot_name)])
EAL.save_loaded_asset(ramp_mesh)
mesh_actor('Ramp_Continuous_EditableMesh',ramp_mesh)
for i in []: # original segmented version retained below only as readable fallback
    p0=points[i]['p'];p1=points[min(i+3,len(points)-1)]['p'];angle=math.radians((points[i]['pitch']+points[min(i+3,len(points)-1)]['pitch'])/2)
    normal=[-math.sin(angle),0,math.cos(angle)]
    center=[(p0[j]+p1[j])/2-normal[j]*thick/2 for j in range(3)]
    length=math.dist(p0,p1)+1
    a=mesh_actor('RampSurface_%03d'%i,cube,center,unreal.Rotator(math.degrees(angle),0,0),(length/100,width/100,thick/100),road)
    for y,mat,label,w in [(0,stripe,'Centerline',6),(-width/2,edge,'EdgeL',4),(width/2,edge,'EdgeR',4)]:
        pp=[(p0[j]+p1[j])/2+normal[j]*1.5 for j in range(3)];pp[1]=y
        mesh_actor('%s_%03d'%(label,i),cube,pp,unreal.Rotator(math.degrees(angle),0,0),(length/100,w/100,.025),mat)
for y in [-width/2-20,width/2+20]:
    previous=None
    back_x=max(p['p'][0] for p in points)+110
    beam('TrussRearMast',[back_x,y,0],[back_x,y,points[-1]['p'][2]],10,steel,cube)
    for i in range(12,len(points),24):
        p=points[i]['p'];a=math.radians(points[i]['pitch']);attach=[p[0]+math.sin(a)*65,y,p[2]-math.cos(a)*65]
        base=[back_x,y,attach[2]]
        if attach[2]>150:beam('TrussUpright',base,attach,8,steel,cube)
        if previous:
            beam('TrussChord',previous,attach,9,steel,cube)
            beam('TrussDiagonal',[back_x,y,previous[2]],attach,6,steel,cube)
        previous=attach
add_visible_ground_details(ROOT)
body=mesh_actor('Roadster_Draft_Kinematic',parts['body'])
wheels={}
for key,info in manifest['wheel_centers'].items():
    w=mesh_actor('Wheel_'+key,parts[key],info['unreal_cm'])
    w.attach_to_actor(body,'',unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
    wheels[key]=w
trajectory_file='trajectory_fit.csv' if os.path.exists(os.path.join(ROOT,'Data','trajectory_fit.csv')) else 'trajectory_initial.csv'
rows=list(csv.DictReader(open(os.path.join(ROOT,'Data',trajectory_file))))
seq=load_if('/Game/Sequences/SEQ_Ramp_Draft')
if seq:
    for b in seq.get_bindings():b.remove()
    for t in seq.get_tracks():seq.remove_track(t)
else:seq=ASSETS.create_asset('SEQ_Ramp_Draft','/Game/Sequences',unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(24000,1001));seq.set_playback_start(0);seq.set_playback_end(len(rows))
frames=[int(r['frame']) for r in rows]
poses=[[float(r[k]) for k in ['x_cm','y_cm','z_cm','roll_deg_unwrapped','pitch_deg_unwrapped','yaw_deg_unwrapped']]+[1,1,1] for r in rows]
transform_track(seq,body,frames,poses)
for key,w in wheels.items():
    loc=manifest['wheel_centers'][key]['unreal_cm']
    values=[loc+[0,float(r['wheel_pitch_deg_unwrapped']),0,1,1,1] for r in rows]
    transform_track(seq,w,frames,values)
keys=json.load(open(os.path.join(ROOT,'Data','camera_fit_keys.json')))['camera_keys']
def cam_lerp(f,getter,keys=keys):
    if f<=keys[0]['source_frame']:
        a,b=keys[0],keys[1]
    elif f>=keys[-1]['source_frame']:
        a,b=keys[-2],keys[-1]
        f=min(f,b['source_frame'])
    else:
        a,b=next((a,b) for a,b in zip(keys,keys[1:]) if a['source_frame']<=f<=b['source_frame'])
    u=(f-a['source_frame'])/(b['source_frame']-a['source_frame'])
    return getter(a)*(1-u)+getter(b)*u
cam=camera('ReferenceCamera_Wide_Fitted',keys[0]['unreal_location_cm'],(0,0,950),keys[0]['focal_length_mm'])
cam_frames=[];cam_values=[];cam_focal=[]
for f in frames:
    loc=[cam_lerp(f,lambda k,i=i:k['unreal_location_cm'][i]) for i in range(3)]
    rot=[cam_lerp(f,lambda k,n=n:k['unreal_rotation_deg'][n]) for n in ['roll','pitch','yaw']]
    cam_frames.append(f);cam_values.append(loc+rot+[1,1,1]);cam_focal.append(cam_lerp(f,lambda k:k['focal_length_mm']))
cb=transform_track(seq,cam,cam_frames,cam_values);focal_track(seq,cam,cb,cam_frames,cam_focal);cut_track(seq,cam,51,len(rows),cb)
# The separate opening rear view is an explicit estimated camera, never a source-video plane.
closekeys=json.load(open(os.path.join(ROOT,'Data','camera_close_fit.json')))['camera_keys']
close=camera('ReferenceCamera_Rear_Estimate',closekeys[0]['unreal_location_cm'],(-220,0,50),closekeys[0]['focal_length_mm'])
cf=list(range(51));cv=[];fl=[]
for f in cf:
    loc=[cam_lerp(f,lambda k,i=i:k['unreal_location_cm'][i],closekeys) for i in range(3)]
    rot=[cam_lerp(f,lambda k,n=n:k['unreal_rotation_deg'][n],closekeys) for n in ['roll','pitch','yaw']]
    cv.append(loc+rot+[1,1,1]);fl.append(cam_lerp(f,lambda k:k['focal_length_mm'],closekeys))
closebind=transform_track(seq,close,cf,cv);focal_track(seq,close,closebind,cf,fl);cut_track(seq,close,0,51,closebind)
camera('Inspection_Side',(-300,-6000,1500),(0,0,950),35)
camera('Inspection_Top',(-1000,0,8500),(-1000,0,0),35)
camera('Inspection_Vehicle',(-3000,-600,300),(-1800,0,65),55)
light=ACTORS.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,3000),unreal.Rotator(-40,-120,0))
light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE);light.light_component.set_editor_property('intensity',0.1)
sky=ACTORS.spawn_actor_from_class(unreal.SkyLight,unreal.Vector())
sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
sky.light_component.set_editor_property('source_type',unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
sky.light_component.set_editor_property('cubemap',unreal.load_asset('/Engine/EngineResources/GrayLightTextureCube'))
sky.light_component.set_editor_property('intensity',.18)
sky.light_component.set_editor_property('lower_hemisphere_is_black',False)
for pitch,yaw,intensity in [(-30,0,.45),(35,0,.45),(0,-25,.25)]:
    a=ACTORS.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(),unreal.Rotator(pitch,yaw,0))
    a.light_component.set_mobility(unreal.ComponentMobility.MOVABLE);a.light_component.set_editor_property('intensity',intensity);a.light_component.set_editor_property('cast_shadows',False)
for loc,target,power in [((-2600,-2400,1500),(0,0,1000),500),((-2000,1800,300),(0,0,1000),500)]:
    a=ACTORS.spawn_actor_from_class(unreal.RectLight,unreal.Vector(*loc),unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*loc),unreal.Vector(*target)))
    a.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    a.light_component.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
    a.light_component.set_editor_property('intensity',power);a.light_component.set_editor_property('attenuation_radius',10000.0)
    a.light_component.set_editor_property('source_width',700.0);a.light_component.set_editor_property('source_height',700.0)
player=ACTORS.spawn_actor_from_class(unreal.LevelSequenceActor,unreal.Vector())
player.set_actor_label('Reference_Replay_DRAFT_Autoplay');player.set_sequence(seq)
ps=unreal.MovieSceneSequencePlaybackSettings();ps.set_editor_property('auto_play',True);ps.set_editor_property('loop_count',unreal.MovieSceneSequenceLoopCount(-1));player.set_editor_property('playback_settings',ps)
surface_detail()
add_visible_gas(seq,body,rows,ROOT)
EAL.save_loaded_asset(seq)
try:
    seq.delete_marked_frames()
    for f,label in [(0,'Rear camera'),(51,'Wide camera'),(216,'Nose-over interval starts'),(234,'Visible roll interval'),(241,'First full silhouette gap'),(264,'Recovery interval'),(300,'Landing occluded interval starts'),(336,'Low upright after cloud')]:
        mark=unreal.MovieSceneMarkedFrame();mark.set_editor_property('frame_number',unreal.FrameNumber(f));mark.set_editor_property('label',label);seq.add_marked_frame(mark)
    EAL.save_loaded_asset(seq)
except Exception as ex:unreal.log_warning('Event markers unavailable: '+str(ex))
inspect_path='/Game/Sequences/SEQ_Ramp_Inspection'
if EAL.does_asset_exist(inspect_path):EAL.delete_asset(inspect_path)
inspect=EAL.duplicate_asset('/Game/Sequences/SEQ_Ramp_Draft',inspect_path)
for b in inspect.get_bindings():
    if not any(s in str(b.get_name()) for s in ['Roadster','Wheel_','Gas_Approx_']):b.remove()
for track in inspect.get_tracks():
    if isinstance(track,unreal.MovieSceneCameraCutTrack):inspect.remove_track(track)
orbit=camera('Inspection_Orbit_3D',(-2400,2000,1000),(0,0,500),30)
orbit_values=[]
for i,r in enumerate(rows):
    angle=2.5+1.5*i/(len(rows)-1);target=unreal.Vector(float(r['x_cm']),float(r['y_cm']),float(r['z_cm'])+70)
    pos=target+unreal.Vector(2200*math.cos(angle),2200*math.sin(angle),1000)
    rot=unreal.MathLibrary.find_look_at_rotation(pos,target)
    orbit_values.append([pos.x,pos.y,pos.z,rot.roll,rot.pitch,rot.yaw,1,1,1])
ib=transform_track(inspect,orbit,frames,orbit_values);cut_track(inspect,orbit,0,len(rows),ib);EAL.save_loaded_asset(inspect)
render_preset('Ramp_Inspection_720',os.path.join(ROOT,'Renders','inspection'),1280,720)
render_preset('Ramp_Draft_720',os.path.join(ROOT,'Renders','ramp_draft'),1280,720)
render_preset('Ramp_Final_1080',os.path.join(ROOT,'Renders','reference_1080'),1920,1080)
final4k=render_preset('Ramp_Final_4K',os.path.join(ROOT,'Renders','reference_4k'),3840,2160)
aa4k=final4k.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa4k.set_editor_property('spatial_sample_count',4);aa4k.set_editor_property('temporal_sample_count',1)
aa4k.set_editor_property('override_anti_aliasing',True);aa4k.set_editor_property('anti_aliasing_method',unreal.AntiAliasingMethod.AAM_NONE)
EAL.save_loaded_asset(final4k)
smoke=render_preset('Ramp_Smoke',os.path.join(ROOT,'Renders','ramp_smoke'),960,540)
output=smoke.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
output.set_editor_property('use_custom_playback_range',True)
output.set_editor_property('custom_start_frame',264)
output.set_editor_property('custom_end_frame',266)
EAL.save_loaded_asset(smoke)
levels.save_current_level()
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(unreal.Vector(*keys[0]['unreal_location_cm']),cam.get_actor_rotation())
json.dump({'saved':True,'map':'/Game/Maps/Ramp_Reconstruction_Draft','sequence':seq.get_path_name(),'actor_count':len(ACTORS.get_all_level_actors()),'import_bounds':bounds,'trajectory_file':trajectory_file,'status':'static ramp and wide camera fitted; vehicle blockout; no physics validation'},open(os.path.join(ROOT,'Validation','reconstruction_build.json'),'w'),indent=2)
unreal.log('ROADSTER_RECONSTRUCTION_DRAFT_SAVED')
