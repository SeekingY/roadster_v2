import unreal
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/Ramp_Reconstruction_Draft')
sequence=unreal.load_asset('/Game/Sequences/SEQ_Ramp_Draft')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(144)
unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(True)
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'t.MaxFPS 30')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
unreal.log('ROADSTER_WORKBENCH_OPEN: draft reference sequence, frame144; Sequencer provides play/pause/step/seek/speed/loop; unlock camera cut for free inspection.')
