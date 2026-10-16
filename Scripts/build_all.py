import unreal,os,runpy,json,hashlib,glob,datetime
root=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
for name in ['build_reconstruction.py','setup_validate.py','validate_render_stage.py']:
    runpy.run_path(os.path.join(root,'Scripts',name),run_name='__main__')
files=['Data/trajectory_fit.csv','Data/flight_attitude_fit.json','Data/camera_fit_keys.json','Data/camera_close_fit.json','Data/ramp_parameters.json','Data/ramp_dense.json','Data/vehicle_clearance_adjustment.json','AssetsSource/vehicle_parameters.json','AssetsSource/vehicle_manifest.json','Roadster_Demo_Reconstruction.uproject']
for pattern in ['AssetsSource/FBX/*.fbx','Config/*.ini','Scripts/build_*.py','Scripts/author_*.py','Scripts/unreal_helpers.py']:
    files.extend(os.path.relpath(p,root).replace('\\','/') for p in glob.glob(os.path.join(root,pattern)))
json.dump({'status':'built; in-process native replay checks executed; independent new-process checks and image fidelity separate',
    'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'inputs':{p:hashlib.sha256(open(os.path.join(root,p),'rb').read()).hexdigest() for p in sorted(set(files))}},open(os.path.join(root,'Validation','build_manifest.json'),'w'),indent=2)
