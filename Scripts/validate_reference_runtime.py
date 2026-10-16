"""Observe saved native autoplay/controls in a dedicated full Editor SIE run.

Python invokes native player controls and reads state; it never writes actor
transforms, forces, physics flags, playback settings, or binding overrides.
Run with -ExecutePythonScript, not a commandlet or null RHI. Ends only this
dedicated SIE session and editor. No assets or Data files are modified.
"""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,math,os,time,traceback
import unreal

ROOT=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
MAP='/Game/Maps/Ramp_Reconstruction_Draft'
LEVELS=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EDITOR=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
CSV=(ROOT/'Data/trajectory_fit.csv').read_bytes()
ROWS=list(csv.DictReader(CSV.decode('utf-8-sig').splitlines()))
FPS=24000/1001
REPORT=dict(scope='saved native runtime player and controls; NOT image fidelity or vehicle physics',
    process_id=os.getpid(),created_utc=datetime.now(timezone.utc).isoformat(),
    trajectory_sha256=hashlib.sha256(CSV).hexdigest(),
    observer_only_python=True,actor_transform_writes=0,forces_applied=False,
    binding_overrides_changed=False,playback_settings_changed=False,
    checks={},samples=[],**{'pass':False})
STATE=dict(phase='await_viewport',ticks=0,wall_start=time.monotonic(),callback=None)

def frame():
    value=STATE['player'].get_current_time().time
    return float(value.frame_number.value)+float(value.sub_frame)

def position():
    p=STATE['body'].get_actor_location()
    return [p.x,p.y,p.z]

def expected_position(f):
    low=max(0,min(len(ROWS)-1,math.floor(f)))
    high=min(low+1,len(ROWS)-1)
    fraction=f-low
    return [float(ROWS[low][k])*(1-fraction)+float(ROWS[high][k])*fraction
        for k in ('x_cm','y_cm','z_cm')]

def seek(f):
    param=unreal.MovieSceneSequencePlaybackParams()
    param.set_editor_property('frame',unreal.FrameTime(unreal.FrameNumber(f)))
    param.set_editor_property('position_type',unreal.MovieScenePositionType.FRAME)
    param.set_editor_property('update_method',unreal.UpdatePositionMethod.JUMP)
    STATE['player'].set_playback_position(param)

def capture(label):
    f=frame();p=position()
    sample=dict(label=label,world_time_s=unreal.GameplayStatics.get_time_seconds(STATE['world']),
        native_sequence_frame=f,body_position_cm=p,
        csv_position_error_cm=math.dist(p,expected_position(f)),
        body_simulates_physics=STATE['body'].static_mesh_component.is_simulating_physics(),
        player_is_playing=STATE['player'].is_playing(),
        native_play_rate=STATE['player'].get_play_rate())
    REPORT['samples'].append(sample)
    return sample

def save():
    path=ROOT/'Validation/reference_runtime_controls.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')

def finish(error=None):
    if error:
        REPORT['error']=error
    REPORT['pass']=bool(REPORT['checks']) and all(REPORT['checks'].values()) and not error
    REPORT['limitations']=['native control APIs exercised by an editor QA observer; no custom runtime HUD is created',
        'single SIE run; not independent packaged-executable or visual-fidelity acceptance',
        'play-rate timing allows one source frame of observer scheduling difference',
        'existing random-seek report separately checks dense poses, wheel and gas states']
    save()
    LEVELS.editor_request_end_play()
    STATE['phase']='ending';STATE['ending_ticks']=0

def tick(delta_seconds):
    try:
        STATE['ticks']+=1
        if STATE['phase']=='ending':
            STATE['ending_ticks']+=1
            if not LEVELS.is_in_play_in_editor() or STATE['ending_ticks']>120:
                unreal.unregister_slate_post_tick_callback(STATE['callback'])
                unreal.log('ROADSTER_NATIVE_RUNTIME_CONTROLS_RESULT '+json.dumps(REPORT))
                unreal.SystemLibrary.quit_editor()
            return
        if time.monotonic()-STATE['wall_start']>60:
            finish('60-second wall timeout');return
        if STATE['phase']=='await_viewport':
            if STATE['ticks']>=3:
                LEVELS.editor_play_simulate();STATE['phase']='await_world'
            return
        world=EDITOR.get_game_world()
        if not world:return
        if STATE['phase']=='await_world':
            owners=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.LevelSequenceActor)
            owners=[a for a in owners if a.get_sequence() and a.get_sequence().get_name()=='SEQ_Ramp_Draft']
            bodies=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.StaticMeshActor)
            bodies=[a for a in bodies if a.get_actor_label()=='Roadster_Draft_Kinematic']
            if len(owners)!=1 or len(bodies)!=1:return
            owner=owners[0]
            STATE.update(world=world,owner=owner,body=bodies[0],player=owner.get_editor_property('sequence_player'))
            if not STATE['player']:return
            REPORT.update(game_world_path=world.get_path_name(),saved_owner_path=owner.get_path_name(),
                body_path=bodies[0].get_path_name(),
                saved_auto_play=owner.get_editor_property('playback_settings').get_editor_property('auto_play'))
            STATE['autoplay_start']=capture('saved_autoplay_initial_observation')
            STATE['phase']='autoplay';return
        now=float(unreal.GameplayStatics.get_time_seconds(world))
        if STATE['phase']=='autoplay':
            if frame()>=80:
                after=capture('saved_autoplay_progress')
                before=STATE['autoplay_start']
                REPORT['checks']['saved_autoplay_progressed']=REPORT['saved_auto_play'] and after['player_is_playing'] and after['native_sequence_frame']-before['native_sequence_frame']>20 and math.dist(after['body_position_cm'],before['body_position_cm'])>1
                REPORT['checks']['body_is_kinematic']=not after['body_simulates_physics']
                STATE['player'].pause();STATE['pause_start']=capture('pause_start')
                STATE['phase']='pause';return
            if now-STATE['autoplay_start']['world_time_s']>6:
                finish('Saved autoplay did not reach frame80 within6 world seconds');return
        elif STATE['phase']=='pause':
            before=STATE['pause_start']
            if now-before['world_time_s']>=0.4:
                after=capture('pause_after_0_4_world_seconds')
                REPORT['checks']['pause_stable']=abs(after['native_sequence_frame']-before['native_sequence_frame'])<1e-4 and math.dist(after['body_position_cm'],before['body_position_cm'])<0.001
                STATE['seek_targets']=[216,217,240,264,300]
                STATE['seek_index']=0;seek(216);STATE['phase']='seek';return
        elif STATE['phase']=='seek':
            target=STATE['seek_targets'][STATE['seek_index']]
            sample=capture('native_seek_'+str(target))
            REPORT['checks']['seek_'+str(target)]=abs(sample['native_sequence_frame']-target)<1e-4 and sample['csv_position_error_cm']<0.001 and not sample['body_simulates_physics']
            if target==217:
                prior=next(s for s in REPORT['samples'] if s['label']=='native_seek_216')
                REPORT['checks']['single_frame_step_216_to_217']=abs(sample['native_sequence_frame']-prior['native_sequence_frame']-1)<1e-4 and math.dist(sample['body_position_cm'],prior['body_position_cm'])>0.01
            STATE['seek_index']+=1
            if STATE['seek_index']<len(STATE['seek_targets']):
                seek(STATE['seek_targets'][STATE['seek_index']]);return
            seek(144);STATE['player'].set_play_rate(0.25);STATE['player'].play()
            STATE['rate_start']=capture('quarter_rate_start');STATE['phase']='rate';return
        elif STATE['phase']=='rate':
            before=STATE['rate_start']
            if now-before['world_time_s']>=0.6:
                STATE['player'].pause();after=capture('quarter_rate_end')
                dt=after['world_time_s']-before['world_time_s']
                advance=after['native_sequence_frame']-before['native_sequence_frame']
                REPORT['quarter_rate_measurement']=dict(world_elapsed_s=dt,actual_frame_advance=advance,expected_frame_advance=dt*FPS*0.25,error_frames=advance-dt*FPS*0.25)
                REPORT['checks']['quarter_rate_advances_correctly']=advance>0 and abs(advance-dt*FPS*0.25)<=1 and after['csv_position_error_cm']<0.01
                STATE['player'].set_play_rate(1.0);seek(418);STATE['player'].play()
                STATE['loop_start']=capture('loop_from_418');STATE['phase']='loop';return
        elif STATE['phase']=='loop':
            if frame()<20:
                sample=capture('saved_native_loop_wrapped')
                REPORT['checks']['saved_native_loop_wraps']=sample['player_is_playing'] and sample['csv_position_error_cm']<0.001
                STATE['player'].pause();finish();return
            if now-STATE['loop_start']['world_time_s']>2:
                REPORT['checks']['saved_native_loop_wraps']=False
                finish('Native saved loop failed to wrap from418');return
    except Exception:
        finish(traceback.format_exc())

assert not LEVELS.is_in_play_in_editor(), 'Use a dedicated editor, not an existing user play session'
assert LEVELS.load_level(MAP), 'Cannot load saved reference map'
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
STATE['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.log('ROADSTER_NATIVE_RUNTIME_OBSERVER_REGISTERED')
