"""Create render-only map with no autonomous sequence playback, then test binding resolution."""
import unreal,os,json,csv,math
ROOT=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
eal=unreal.EditorAssetLibrary;levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
path='/Game/Maps/Ramp_Render_Stage'
if eal.does_asset_exist(path):eal.delete_asset(path)
assert eal.duplicate_asset('/Game/Maps/Ramp_Reconstruction_Draft',path)
assert levels.load_level(path)
for a in actors.get_all_level_actors():
    if isinstance(a,unreal.LevelSequenceActor):actors.destroy_actor(a)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
body=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Roadster_Draft_Kinematic')
by_label={a.get_actor_label():a for a in actors.get_all_level_actors()}
def override_bindings(owner,seq):
    for b in seq.get_bindings():
        name=str(b.get_name())
        if name in by_label:
            bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',b.get_id())
            owner.set_binding(bid,[by_label[name]],False)
rows=list(csv.DictReader(open(os.path.join(ROOT,'Data','trajectory_fit.csv'))))
result={}
for name in ['SEQ_Ramp_Draft','SEQ_Ramp_Inspection']:
    seq=unreal.load_asset('/Game/Sequences/'+name)
    saved=actors.spawn_actor_from_class(unreal.LevelSequenceActor,unreal.Vector());saved.set_actor_label('RenderOwner_'+name);saved.set_sequence(seq)
    ps=unreal.MovieSceneSequencePlaybackSettings();ps.set_editor_property('auto_play',False);saved.set_editor_property('playback_settings',ps);override_bindings(saved,seq)
    settings=unreal.MovieSceneSequencePlaybackSettings();settings.set_editor_property('disable_camera_cuts',True)
    player,owner=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,settings);override_bindings(owner,seq)
    errors=[]
    for f in [0,51,144,216,264,300,418]:
        pp=unreal.MovieSceneSequencePlaybackParams();pp.set_editor_property('frame',unreal.FrameTime(unreal.FrameNumber(f)));pp.set_editor_property('position_type',unreal.MovieScenePositionType.FRAME);pp.set_editor_property('update_method',unreal.UpdatePositionMethod.JUMP);player.set_playback_position(pp)
        p=body.get_actor_location();errors.append(math.dist([p.x,p.y,p.z],[float(rows[f][k]) for k in ['x_cm','y_cm','z_cm']]))
    player.stop();actors.destroy_actor(owner);result[name]=max(errors)
assert levels.save_current_level()
json.dump({'render_map':path,'autonomous_players':0,'max_binding_position_errors_cm':result,'pass':all(v<.001 for v in result.values())},open(os.path.join(ROOT,'Validation','render_stage_bindings.json'),'w'),indent=2)
assert all(v<.001 for v in result.values()),str(result)
unreal.log('ROADSTER_RENDER_STAGE_BINDINGS_OK')
