import unreal,os,json,csv,math,random
ROOT=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/Ramp_Reconstruction_Draft')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
objects=actors.get_all_level_actors()
body=next(a for a in objects if a.get_actor_label()=='Roadster_Draft_Kinematic')
wheels=[a for a in objects if a.get_actor_label().startswith('Wheel_')]
gas=[a for a in objects if a.get_actor_label().startswith('Gas_Approx_')]
cameras=[a for a in objects if isinstance(a,unreal.CineCameraActor) and a.get_actor_label().startswith('ReferenceCamera_')]
seq=unreal.load_asset('/Game/Sequences/SEQ_Ramp_Draft')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings=unreal.MovieSceneSequencePlaybackSettings();settings.set_editor_property('disable_camera_cuts',True)
player,owner=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,settings)
build_report=os.path.join(ROOT,'Validation','reconstruction_build.json')
name=json.load(open(build_report))['trajectory_file'] if os.path.exists(build_report) else 'trajectory_fit.csv'
rows=list(csv.DictReader(open(os.path.join(ROOT,'Data',name))))
def sample(frame):
    param=unreal.MovieSceneSequencePlaybackParams()
    param.set_editor_property('frame',unreal.FrameTime(unreal.FrameNumber(frame)))
    param.set_editor_property('position_type',unreal.MovieScenePositionType.FRAME)
    param.set_editor_property('update_method',unreal.UpdatePositionMethod.JUMP)
    player.set_playback_position(param)
    tr=body.get_actor_transform();p=tr.translation;q=tr.rotation
    wp=[]
    for wheel in wheels:
        pos=wheel.get_actor_location();wp.append([pos.x,pos.y,pos.z])
    gp=[]
    for a in gas:
        p1=a.get_actor_location();s=a.get_actor_scale3d();gp.extend([p1.x,p1.y,p1.z,s.x,s.y,s.z])
    cp=[]
    for a in cameras:
        if (frame<51)!=('Rear' in a.get_actor_label()):continue
        p1=a.get_actor_location();r=a.get_actor_rotation();cp.extend([p1.x,p1.y,p1.z,r.pitch,r.yaw,r.roll,a.get_cine_camera_component().get_editor_property('current_focal_length')])
    return {'position':[p.x,p.y,p.z],'quaternion':[q.x,q.y,q.z,q.w],'scale':[tr.scale3d.x,tr.scale3d.y,tr.scale3d.z],'wheels':wp,'gas':gp,'cameras':cp}
baseline=[sample(f) for f in range(len(rows))]
rng=random.Random(20261016);samples=rng.sample(range(len(rows)),min(60,len(rows)))
errors=[]
for f in samples:
    result=sample(f);ref=baseline[f]
    errors.append({'frame':f,'position_difference_cm':math.dist(result['position'],ref['position']),'orientation_dot_error':abs(1-abs(sum(a*b for a,b in zip(result['quaternion'],ref['quaternion'])))),'wheel_difference_cm':max(math.dist(a,b) for a,b in zip(result['wheels'],ref['wheels']))})
    errors[-1]['gas_transform_max_difference']=max([abs(a-b) for a,b in zip(result['gas'],ref['gas'])]+[0])
    errors[-1]['camera_transform_focal_max_difference']=max([abs(a-b) for a,b in zip(result['cameras'],ref['cameras'])]+[0])
expected=max(math.dist(baseline[f]['position'],[float(rows[f][k]) for k in ['x_cm','y_cm','z_cm']]) for f in range(len(rows)))
max_delta=max(e['position_difference_cm'] for e in errors);max_angle=max(e['orientation_dot_error'] for e in errors)
report={'scope':'native Unreal playback determinism and imported coordinate checks; NOT reference similarity or physics validation','reopened_in_new_process':True,'sequence_frames':len(rows),'frame_rate':[seq.get_display_rate().numerator,seq.get_display_rate().denominator],'random_seek_count':len(samples),'max_position_seek_difference_cm':max_delta,'max_orientation_dot_error':max_angle,'max_wheel_seek_difference_cm':max(e['wheel_difference_cm'] for e in errors),'max_position_csv_error_cm':expected,'scale_all_unit':all(max(abs(v-1) for v in b['scale'])<1e-6 for b in baseline),'single_body_transform_track':sum(1 for b in seq.get_bindings() if 'Roadster' in str(b.get_name())),'samples':errors,'key_pose_states':{str(f):baseline[f] for f in [0,144,216,240,252,264,300,336,len(rows)-1]}}
report['csv_tolerance_cm']=0.001 # 10 micrometres, above native property precision and far below annotation precision.
report['max_gas_seek_delta']=max(e['gas_transform_max_difference'] for e in errors)
report['max_camera_seek_delta']=max(e['camera_transform_focal_max_difference'] for e in errors)
report['pass']=max_delta<1e-5 and max_angle<1e-5 and expected<report['csv_tolerance_cm'] and report['scale_all_unit'] and report['max_gas_seek_delta']<1e-5 and report['max_camera_seek_delta']<1e-5
player.stop();actors.destroy_actor(owner)
json.dump(report,open(os.path.join(ROOT,'Validation','reconstruction_reopen_seek.json'),'w'),indent=2)
if not report['pass']:raise RuntimeError('Reconstruction playback determinism failed')
unreal.log('ROADSTER_REOPEN_RANDOM_SEEK_OK')
