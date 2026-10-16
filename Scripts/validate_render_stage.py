"""Reopen the saved render stage and verify its saved native binding overrides.

Run in a fresh UE commandlet process. No asset saves, rebinding, new player,
or actor spawning: use each saved LevelSequenceActor just as MRQ reuses it.
SetSequence(same_sequence) initializes its transient player in editor worlds;
it preserves the serialized BindingOverrides. This mirrors MRQ initialization.
"""
from pathlib import Path
import csv, hashlib, json, math, os, traceback
import unreal

ROOT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
MAP = '/Game/Maps/Ramp_Render_Stage'
TOLERANCE_CM = 0.001
REPORT = ROOT/'Validation/render_stage_reopen_bindings.json'

def object_world(obj):
    if isinstance(obj, unreal.Actor):
        return obj.get_world()
    if isinstance(obj, unreal.ActorComponent):
        owner = obj.get_owner()
        return owner.get_world() if owner else None
    return None

def main(report):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level(MAP), 'Cannot load saved render stage'
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report['world_path'] = world.get_path_name()
    assert world.get_path_name() == MAP+'.Ramp_Render_Stage', report['world_path']
    body = next(a for a in actors if a.get_actor_label() == 'Roadster_Draft_Kinematic')
    report['body_path'] = body.get_path_name()
    report['body_world_path'] = body.get_world().get_path_name()
    owners = [a for a in actors if isinstance(a, unreal.LevelSequenceActor)]
    report['saved_sequence_actor_count'] = len(owners)
    report['autoplay_actor_paths'] = [a.get_path_name() for a in owners
        if a.get_editor_property('playback_settings').get_editor_property('auto_play')]
    assert not report['autoplay_actor_paths'], 'Autonomous sequence in render map'
    snapshot = (ROOT/'Data/trajectory_fit.csv').read_bytes()
    report['trajectory_sha256'] = hashlib.sha256(snapshot).hexdigest()
    rows = list(csv.DictReader(snapshot.decode('utf-8-sig').splitlines()))
    report['sequences'] = []
    for sequence_name in ['SEQ_Ramp_Draft', 'SEQ_Ramp_Inspection']:
        matching = [a for a in owners if a.get_sequence()
                    and a.get_sequence().get_name() == sequence_name]
        assert len(matching) == 1, (sequence_name, len(matching))
        owner = matching[0]
        sequence = owner.get_sequence()
        # UE5.4 exposes the BlueprintGetter-backed property to Python, but
        # does not export GetSequencePlayer() itself as a Python method.
        player = owner.get_editor_property('sequence_player')
        assert player, 'No native player on saved actor'
        player.stop()
        owner.set_sequence(sequence)  # initialize only; DO NOT set_binding here
        entry = dict(sequence=sequence.get_path_name(), owner_path=owner.get_path_name(),
            owner_world_path=owner.get_world().get_path_name(), bindings=[], samples=[])
        report['sequences'].append(entry)
        for binding in sequence.get_bindings():
            bid = unreal.MovieSceneObjectBindingID()
            bid.set_editor_property('guid', binding.get_id())
            objects = list(player.get_bound_objects(bid))
            detail = dict(name=str(binding.get_name()), guid=str(binding.get_id()),
                resolved_paths=[o.get_path_name() for o in objects],
                resolved_world_paths=[object_world(o).get_path_name()
                    if object_world(o) else None for o in objects])
            detail['all_in_render_world'] = bool(objects) and all(object_world(o) == world for o in objects)
            entry['bindings'].append(detail)
            assert detail['all_in_render_world'], detail
        for frame in [0, 51, 144, 216, 264, 300, len(rows)-1]:
            param = unreal.MovieSceneSequencePlaybackParams()
            param.set_editor_property('frame', unreal.FrameTime(unreal.FrameNumber(frame)))
            param.set_editor_property('position_type', unreal.MovieScenePositionType.FRAME)
            param.set_editor_property('update_method', unreal.UpdatePositionMethod.JUMP)
            player.set_playback_position(param)
            p = body.get_actor_location()
            error = math.dist([p.x,p.y,p.z], [float(rows[frame][k]) for k in ('x_cm','y_cm','z_cm')])
            entry['samples'].append(dict(frame=frame, body_position_error_cm=error))
        entry['max_body_position_error_cm'] = max(s['body_position_error_cm'] for s in entry['samples'])
        assert entry['max_body_position_error_cm'] < TOLERANCE_CM, entry
        player.stop()
    report['pass'] = True

report = dict(scope='saved render-map binding resolution and playback; not visual similarity',
    process_id=os.getpid(), expected_map=MAP, csv_tolerance_cm=TOLERANCE_CM,
    validation_uses_saved_actor=True, rebinds_performed=0, assets_saved=False, **{'pass':False})
try:
    main(report)
except Exception:
    report['exception'] = traceback.format_exc()
    raise
finally:
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('ROADSTER_RENDER_STAGE_REOPEN_BINDINGS_OK')
