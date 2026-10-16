"""Observe a saved native Chaos gravity baseline in a full Unreal Editor.

Run with -ExecutePythonScript, not -run=pythonscript or -nullrhi: SIE needs
an active Slate level viewport. Python only samples native physics. It does
not apply forces, move bodies, alter mass, gravity, solver settings or time.
The script ends its own SIE session and exits the dedicated editor process.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv, json, math, os, time, traceback
import unreal

ROOT=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
SPEC=json.loads((ROOT/'Data/physics_baseline_spec.json').read_text(encoding='utf-8'))
MAP=SPEC['map']
LEVELS=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EDITOR=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
REPORT_PATH=ROOT/'Validation/physics_baseline_simulation.json'
SAMPLES_PATH=ROOT/'Data/physics_baseline_native_samples.csv'
STATE=dict(phase='await_viewport',wall_start=time.monotonic(),ticks=0,samples=[],callback=None)
REPORT=dict(scope='native gravity-only box baseline; NOT Roadster Physics Reconstruction',
    process_id=os.getpid(),created_utc=datetime.now(timezone.utc).isoformat(),
    map=MAP,observer_only_python=True,forces_applied=False,trajectory_tracking=False,
    solver_step_changed=False,convergence_validated=False,**{'pass':False})

def slope(points):
    t_mean=sum(t for t,v in points)/len(points)
    v_mean=sum(v for t,v in points)/len(points)
    denom=sum((t-t_mean)**2 for t,v in points)
    return sum((t-t_mean)*(v-v_mean) for t,v in points)/denom if denom else None

def save_report():
    samples=STATE['samples']
    REPORT['sample_count']=len(samples)
    if samples:
        SAMPLES_PATH.parent.mkdir(exist_ok=True)
        with SAMPLES_PATH.open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(samples[0]))
            writer.writeheader();writer.writerows(samples)
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')

def assess():
    rows=STATE['samples']
    g=SPEC['gravity_world_cm_s2'][2]
    # Keep well away from spawn and expected contact. No data-dependent
    # time shift or starting-height fit is applied to the analytic reference.
    pre=[r for r in rows if 0.1<=r['world_time_s']<=1.1 and r['z_cm']>250]
    REPORT['precontact_selection']='world_time_s in [0.1,1.1], z>250cm; no fitted time/position offset'
    REPORT['precontact_sample_count']=len(pre)
    assert len(pre)>=8, 'Too few precontact native samples'
    g_observed=slope([(r['world_time_s'],r['vz_cm_s']) for r in pre])
    errors=[r['z_error_vs_absolute_analytic_cm'] for r in pre]
    # An observed state provides a separate IVP test of the integrator. Do
    # not fit a release time, height, velocity, gravity, or additive offset.
    # Choose the first two consecutive downward precontact samples whose
    # observer interval is <=50ms, to avoid the initial PIE scheduling gap.
    anchor_candidates=[b for a,b in zip(pre,pre[1:])
        if a['vz_cm_s']<0 and b['vz_cm_s']<0 and 0<b['world_time_s']-a['world_time_s']<=0.05]
    assert anchor_candidates, 'No stable measured precontact initial state'
    anchor=anchor_candidates[0]
    initial_state=dict(t0_s=anchor['world_time_s'],z0_cm=anchor['z_cm'],v0_cm_s=anchor['vz_cm_s'])
    REPORT['measured_initial_state']=initial_state
    REPORT['state_initialization_method']='first stable measured precontact state; no fitted parameters; not a recovered release clock'
    state_rows=[r for r in pre if r['world_time_s']>=anchor['world_time_s']]
    for r in rows:
        r['analytic_state_z_cm']=None
        r['z_error_vs_measured_initial_state_cm']=None
        r['analytic_state_vz_cm_s']=None
        r['vz_error_vs_measured_initial_state_cm_s']=None
    for r in state_rows:
        elapsed=r['world_time_s']-anchor['world_time_s']
        predicted_z=anchor['z_cm']+anchor['vz_cm_s']*elapsed+0.5*g*elapsed*elapsed
        predicted_v=anchor['vz_cm_s']+g*elapsed
        r['analytic_state_z_cm']=predicted_z
        r['z_error_vs_measured_initial_state_cm']=r['z_cm']-predicted_z
        r['analytic_state_vz_cm_s']=predicted_v
        r['vz_error_vs_measured_initial_state_cm_s']=r['vz_cm_s']-predicted_v
    state_errors=[r['z_error_vs_measured_initial_state_cm'] for r in state_rows]
    intervals=[b['world_time_s']-a['world_time_s'] for a,b in zip(rows,rows[1:])]
    rest=[r for r in rows if r['world_time_s']>=2.2]
    assert rest, 'No postcontact samples'
    bottom_height=SPEC['visible_proxy_dimensions_cm'][2]/2
    measured=dict(gravity_from_native_velocity_slope_cm_s2=g_observed,
        gravity_relative_error=abs(g_observed-g)/abs(g),
        analytic_z_rms_error_cm=math.sqrt(sum(e*e for e in errors)/len(errors)),
        analytic_z_max_error_cm=max(abs(e) for e in errors),
        measured_state_analytic_z_rms_error_cm=math.sqrt(sum(e*e for e in state_errors)/len(state_errors)),
        measured_state_analytic_z_max_error_cm=max(abs(e) for e in state_errors),
        measured_state_analytic_vz_max_error_cm_s=max(abs(r['vz_error_vs_measured_initial_state_cm_s']) for r in state_rows),
        observer_world_dt_min_s=min(intervals),observer_world_dt_max_s=max(intervals),
        observer_world_dt_mean_s=sum(intervals)/len(intervals),
        max_lateral_displacement_cm=max(math.hypot(r['x_cm'],r['y_cm']) for r in rows),
        precontact_max_lateral_displacement_cm=max(math.hypot(r['x_cm'],r['y_cm']) for r in pre),
        minimum_center_z_cm=min(r['z_cm'] for r in rows),
        postcontact_center_z_min_cm=min(r['z_cm'] for r in rest),
        postcontact_center_z_max_cm=max(r['z_cm'] for r in rest),
        postcontact_max_abs_vz_cm_s=max(abs(r['vz_cm_s']) for r in rest))
    REPORT['measured']=measured
    REPORT['acceptance_criteria']=dict(min_precontact_samples=8,
        gravity_slope_relative_error_max=0.05,analytic_z_max_error_cm_max=10,
        precontact_lateral_displacement_cm_max=1,postcontact_height_error_cm_max=5,
        postcontact_speed_cm_s_max=5,
        meaning='explicit minimum sanity thresholds for this box scene, not vehicle reconstruction criteria')
    checks=dict(native_physics_active=all(r['simulating_physics'] for r in rows),
        gravity_downward=g_observed<0,
        gravity_slope_within_5_percent=measured['gravity_relative_error']<=0.05,
        absolute_analytic_z_within_10cm=measured['analytic_z_max_error_cm']<=10,
        measured_state_analytic_z_within_10cm=measured['measured_state_analytic_z_max_error_cm']<=10,
        precontact_lateral_displacement_within_1cm=measured['precontact_max_lateral_displacement_cm']<=1,
        no_floor_penetration_over_5cm=measured['minimum_center_z_cm']>=bottom_height-5,
        rests_above_floor=all(abs(r['z_cm']-bottom_height)<=5 for r in rest),
        rest_speed_within_5cm_s=measured['postcontact_max_abs_vz_cm_s']<=5)
    REPORT['checks']=checks
    REPORT['release_time_zero_assumption_pass']=checks['absolute_analytic_z_within_10cm']
    REPORT['native_gravity_integrator_pass']=all(checks[k] for k in (
        'native_physics_active','gravity_downward','gravity_slope_within_5_percent',
        'measured_state_analytic_z_within_10cm','precontact_lateral_displacement_within_1cm'))
    REPORT['postcontact_settling_window_pass']=checks['rests_above_floor'] and checks['rest_speed_within_5cm_s']
    REPORT['pass']=all(checks.values())
    REPORT['overall_pass_meaning']='strict conjunction, including original release-time-zero assumption and 2.2-2.6s settling window; see independent gravity-integrator result'
    REPORT['limitations']=['single solver configuration only; no timestep convergence claim',
        'observer world-time intervals are not proof of Chaos internal substep sizes',
        'absolute analytic z error includes native integration and game/physics clock staggering',
        'contact time from observer sampling is not exact impact time',
        'no vehicle, inverted attachment, thrust, torque, suspension or tire-model validation']

def finish(error=None):
    if error:
        REPORT['error']=error
        REPORT['pass']=False
    else:
        assess()
    save_report()
    LEVELS.editor_request_end_play()
    STATE['phase']='ending'
    STATE['ending_ticks']=0

def tick(delta_seconds):
    try:
        STATE['ticks']+=1
        if STATE['phase']=='ending':
            STATE['ending_ticks']+=1
            if not LEVELS.is_in_play_in_editor() or STATE['ending_ticks']>120:
                unreal.unregister_slate_post_tick_callback(STATE['callback'])
                unreal.log('ROADSTER_NATIVE_GRAVITY_BASELINE_RESULT '+json.dumps(REPORT))
                unreal.SystemLibrary.quit_editor()
            return
        if time.monotonic()-STATE['wall_start']>60:
            finish('60-second wall timeout waiting for native simulation samples')
            return
        if STATE['phase']=='await_viewport':
            if STATE['ticks']>=3:
                LEVELS.editor_play_simulate()
                STATE['phase']='await_world'
            return
        world=EDITOR.get_game_world()
        if not world:
            return
        if STATE['phase']=='await_world':
            candidates=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.StaticMeshActor)
            candidates=[a for a in candidates if a.get_actor_label()==SPEC['actor']]
            if len(candidates)!=1:
                return
            STATE['actor']=candidates[0]
            STATE['component']=candidates[0].static_mesh_component
            REPORT['game_world_path']=world.get_path_name()
            REPORT['sampled_actor_path']=candidates[0].get_path_name()
            REPORT['world_gravity_override_cm_s2']=world.get_world_settings().get_editor_property('global_gravity_z')
            STATE['phase']='sampling'
        actor=STATE['actor'];component=STATE['component']
        t=float(unreal.GameplayStatics.get_time_seconds(world))
        if STATE['samples'] and t<=STATE['samples'][-1]['world_time_s']:
            return
        p=actor.get_actor_location();v=component.get_physics_linear_velocity()
        g=SPEC['gravity_world_cm_s2'][2]
        analytic=SPEC['release_center_z_cm']+0.5*g*t*t
        STATE['samples'].append(dict(world_time_s=t,slate_dt_s=float(delta_seconds),
            x_cm=p.x,y_cm=p.y,z_cm=p.z,vx_cm_s=v.x,vy_cm_s=v.y,vz_cm_s=v.z,
            analytic_free_z_cm=analytic,z_error_vs_absolute_analytic_cm=p.z-analytic,
            simulating_physics=component.is_simulating_physics()))
        if t>=2.6:
            finish()
    except Exception:
        REPORT['error']=traceback.format_exc();REPORT['pass']=False
        save_report()
        LEVELS.editor_request_end_play()
        STATE['phase']='ending';STATE['ending_ticks']=0

assert not LEVELS.is_in_play_in_editor(), 'Run in a dedicated editor, not an existing user play session'
assert LEVELS.load_level(MAP), 'Cannot load saved baseline map'
for source,history in [(REPORT_PATH,ROOT/'Validation/physics_baseline_absolute_time_first.json'),
                       (SAMPLES_PATH,ROOT/'Data/physics_baseline_absolute_time_first_samples.csv')]:
    if source.exists() and not history.exists():
        history.write_bytes(source.read_bytes())
# -ExecutePythonScript's executor otherwise closes the editor immediately
# after this top-level script returns, before any deferred Slate sampling.
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
STATE['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
unreal.log('ROADSTER_NATIVE_GRAVITY_OBSERVER_REGISTERED')
