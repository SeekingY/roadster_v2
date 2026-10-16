"""Post-build setup and tests in one new editor process."""
import os,runpy,unreal
root=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
for script in ['build_mask_pass.py','validate_reconstruction.py','build_render_stage.py']:
    runpy.run_path(os.path.join(root,'Scripts',script),run_name='__main__')
