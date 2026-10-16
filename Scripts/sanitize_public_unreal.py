"""Public-copy metadata cleanup and native saved-sequence check; no rendering."""
import unreal,os,json,csv,math
from pathlib import Path
ROOT=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert ROOT.name=='roadster_v2_public','Run only inside the public copy'
OUT=Path(os.environ.get('ROADSTER_PUBLIC_AUDIT_DIR',str(ROOT/'Saved')));OUT.mkdir(parents=True,exist_ok=True)
VERIFY=os.environ.get('ROADSTER_PUBLIC_VERIFY_ONLY')=='1'
EAL=unreal.EditorAssetLibrary
report={'scope':'public-copy metadata cleanup/reopen test; not a new image-fidelity measurement','verify_only':VERIFY,'presets':[],'import_data':[]}
folders={'Ramp_Draft_720':'ramp_draft','Ramp_Final_1080':'reference_1080','Ramp_Final_4K':'reference_4k',
 'Ramp_Inspection_720':'inspection','Ramp_Smoke':'ramp_smoke','Ramp_Smoke_CarMask':'mask_smoke','Ramp_Validation_CarMask':'mask_validation'}
for name,folder in folders.items():
    asset=unreal.load_asset('/Game/Render/'+name);assert asset
    setting=asset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    desired='{project_dir}/Renders/'+folder
    if not VERIFY:
        setting.set_editor_property('output_directory',unreal.DirectoryPath(desired));assert EAL.save_loaded_asset(asset)
    assert setting.get_editor_property('output_directory').path==desired
    report['presets'].append({'asset':asset.get_path_name(),'output':desired})
meshes=[]
for path in EAL.list_assets('/Game',recursive=True,include_folder=False):
    asset=unreal.load_asset(path)
    if isinstance(asset,unreal.StaticMesh):
        info=asset.get_editor_property('asset_import_data')
        if info is not None:
            count=len(info.extract_filenames())
            if VERIFY:
                assert count==0,'Import source filenames remain: '+path
                report['import_data'].append({'asset':path,'remaining_source_reference_count':count})
            else:
                asset.set_editor_property('asset_import_data',None)
                report['import_data'].append({'asset':path,'source_reference_count_cleared':count})
        meshes.append(asset)
if not VERIFY:
    info=None
    unreal.SystemLibrary.collect_garbage()
    for asset in meshes:
        assert asset.get_editor_property('asset_import_data') is None
        assert EAL.save_loaded_asset(asset)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/Ramp_Reconstruction_Draft')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
body=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Roadster_Draft_Kinematic')
seq=unreal.load_asset('/Game/Sequences/SEQ_Ramp_Draft');assert seq
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings=unreal.MovieSceneSequencePlaybackSettings();settings.set_editor_property('disable_camera_cuts',True)
player,owner=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,settings)
rows={int(r['frame']):r for r in csv.DictReader((ROOT/'Data/trajectory_fit.csv').open(encoding='utf-8-sig'))}
results=[]
for frame in [144,240]:
    pos=unreal.MovieSceneSequencePlaybackParams();pos.set_editor_property('frame',unreal.FrameTime(unreal.FrameNumber(frame)))
    pos.set_editor_property('position_type',unreal.MovieScenePositionType.FRAME);pos.set_editor_property('update_method',unreal.UpdatePositionMethod.JUMP)
    player.set_playback_position(pos);actual=body.get_actor_location()
    target=[float(rows[frame][k]) for k in ['x_cm','y_cm','z_cm']]
    delta=math.dist([actual.x,actual.y,actual.z],target);assert delta<.001
    results.append({'frame':frame,'actual_xyz_cm':[actual.x,actual.y,actual.z],'csv_error_cm':delta})
report['sequence']={'display_rate':[seq.get_display_rate().numerator,seq.get_display_rate().denominator],
 'playback_start':seq.get_playback_start(),'playback_end':seq.get_playback_end(),'samples':results,'passed':True}
assert report['sequence']['display_rate']==[24000,1001] and report['sequence']['playback_end']==419
player.stop();actors.destroy_actor(owner)
report['pass']=True
(OUT/('public_unreal_reopen.json' if VERIFY else 'public_unreal_metadata_cleanup.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('PUBLIC_METADATA_REOPEN_OK '+json.dumps(report))
