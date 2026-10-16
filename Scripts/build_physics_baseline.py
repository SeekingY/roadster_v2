"""Create a separate native Chaos gravity-only sanity scene in UE 5.4.

AUTHORING SCRIPT ONLY: do not run while another Unreal process writes assets.
Does not edit the replay map, sequence, project gravity settings or trajectory.
The saved movable cube is controlled only by native rigid-body simulation.
It is an explicitly visible collision proxy, not a Roadster reconstruction.
No thrust, attraction, force tracking, constraints or runtime Python are used.

Verified local APIs: WorldSettings.h (bGlobalGravitySet, GlobalGravityZ),
PrimitiveComponent.h (SetSimulatePhysics, SetEnableGravity, SetMassOverrideInKg,
SetLinearDamping, SetAngularDamping), BodyInstance.h (bUseCCD),
CameraActor.h (AutoActivateForPlayer). A build report is not a simulation result.
"""
from pathlib import Path
import json, math
import unreal

ROOT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
MAP = '/Game/Maps/Physics_GravityOnly_Baseline'
OWNER = 'RoadsterV2_GravityOnlyBaseline_v1'
MASS_KG = 2000.0  # exploratory assumption, not an official vehicle specification
BOX_CM = (460.0,200.0,115.0)
RELEASE_CENTER_Z_CM = 1000.0
GRAVITY_CM_S2 = -980.665
EAL = unreal.EditorAssetLibrary
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def create_box(label,position,scale,movable=False):
    actor=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*position))
    actor.set_actor_label(label)
    component=actor.static_mesh_component
    component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    component.set_mobility(unreal.ComponentMobility.MOVABLE if movable else unreal.ComponentMobility.STATIC)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    return actor,component

def main():
    if EAL.does_asset_exist(MAP):
        existing=unreal.load_asset(MAP)
        if str(EAL.get_metadata_tag(existing,'RoadsterPhysicsBaselineOwner'))!=OWNER:
            raise RuntimeError('Refusing to replace unowned map: '+MAP)
        if not LEVELS.load_level(MAP):
            raise RuntimeError('Could not load own baseline map')
        for actor in ACTORS.get_all_level_actors():
            if not isinstance(actor,unreal.WorldSettings):
                ACTORS.destroy_actor(actor)
    else:
        if not LEVELS.new_level(MAP):
            raise RuntimeError('Could not create independent baseline map')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    settings=world.get_world_settings()
    settings.set_editor_property('global_gravity_set',True)
    settings.set_editor_property('global_gravity_z',GRAVITY_CM_S2)
    floor,floor_component=create_box('Baseline_StaticFloor',(0,0,-25),(50,50,0.5))
    floor_component.set_collision_profile_name('BlockAll')
    box,component=create_box('Baseline_2000kg_GravityOnly_VISIBLE_PROXY',
        (0,0,RELEASE_CENTER_Z_CM),tuple(v/100 for v in BOX_CM),True)
    component.set_collision_profile_name('PhysicsActor')
    component.set_enable_gravity(True)
    component.set_mass_override_in_kg('',MASS_KG,True)
    component.set_linear_damping(0.0)
    component.set_angular_damping(0.0)
    body=component.get_editor_property('body_instance')
    body.set_editor_property('use_ccd',True)
    component.set_editor_property('body_instance',body)
    component.set_simulate_physics(True)
    camera_position=unreal.Vector(-1900,-2400,1300)
    camera_rotation=unreal.MathLibrary.find_look_at_rotation(camera_position,unreal.Vector(0,0,450))
    camera=ACTORS.spawn_actor_from_class(unreal.CineCameraActor,camera_position,camera_rotation)
    camera.set_actor_label('Baseline_Observe_GravityOnly')
    camera.set_editor_property('auto_activate_for_player',unreal.AutoReceiveInput.PLAYER0)
    camera.get_cine_camera_component().set_editor_property('current_focal_length',35.0)
    light=ACTORS.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,2500),unreal.Rotator(-55,-35,0))
    light.set_actor_label('Baseline_Light')
    light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.light_component.set_editor_property('intensity',3.0)
    EAL.set_metadata_tag(world,'RoadsterPhysicsBaselineOwner',OWNER)
    if not LEVELS.save_current_level():
        raise RuntimeError('Could not save independent physics baseline')
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera_position,camera_rotation)
    height_m=(RELEASE_CENTER_Z_CM-BOX_CM[2]/2)/100
    analytic_time=math.sqrt(2*height_m/(abs(GRAVITY_CM_S2)/100))
    report=dict(status='scene_built_and_saved_NOT_simulation_validated',map=MAP,
      actor=box.get_actor_label(),gravity_world_cm_s2=[0,0,GRAVITY_CM_S2],
      mass_kg=MASS_KG,mass_status='exploratory assumption, not official vehicle mass',
      visible_proxy_dimensions_cm=list(BOX_CM),release_center_z_cm=RELEASE_CENTER_Z_CM,
      nominal_initial_velocity_cm_s=[0,0,0],linear_damping=0,angular_damping=0,
      collision='engine cube simple collision; native PhysicsActor against BlockAll floor; CCD enabled',
      precontact_analytic_reference='z(t)=1000 - 0.5*980.665*t^2 cm, until bottom face reaches floor',
      predicted_first_contact_s_ideal=analytic_time,
      predicted_speed_m_s_ideal=abs(GRAVITY_CM_S2)/100*analytic_time,
      analytical_values_are_not_measured_chaos_results=True,
      trajectory_track=False,runtime_python=False,applied_thrust=False,adhesion=False,
      tracking_force=False,hidden_constraint=False,reconstruction_claim=False,
      solver_timestep='inherits project defaults; not yet converged or benchmarked',
      friction_and_restitution='engine default materials; not calibrated to Roadster',
      validation_pending=['native Play/Simulate free-fall samples','compare precontact z(t) with analytic prediction',
        'check actual gravity direction','repeat at smaller physical solver step','check floor contact/penetration and repeatability'])
    for relative in ('Data/physics_baseline_spec.json','Validation/physics_baseline_build.json'):
        path=ROOT/relative;path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('ROADSTER_GRAVITY_BASELINE_SAVED_NOT_VALIDATED '+json.dumps(report))

if __name__=='__main__':
    main()
