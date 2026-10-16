param([ValidateSet('Open','Play','Generate','Validate','Render','Render4K','RenderMask','RenderInspection','Physics','Encode1080','Encode4K','EncodeAll')][string]$Action='Open')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$engineRoot=if($env:UE_ROOT){$env:UE_ROOT}else{'C:\Program Files\Epic Games\UE_5.4'}
$editor=Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$commandlet=Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$uePython=Join-Path $engineRoot 'Engine\Binaries\ThirdParty\Python3\Win64\python.exe'
$blender=if($env:BLENDER_EXE){$env:BLENDER_EXE}else{'C:\Program Files\Blender Foundation\Blender 4.2\blender.exe'}
$project=Join-Path $projectRoot 'Roadster_Demo_Reconstruction.uproject'
$shaderPath=Join-Path $projectRoot 'Intermediate\ShaderWork'
$baseArgs=@($project,"-ShaderWorkingDir=$shaderPath",'-nosplash','-nop4')
$map='/Game/Maps/Ramp_Reconstruction_Draft'
foreach($directory in @('Validation','Renders','Intermediate')){
    New-Item -ItemType Directory -Path (Join-Path $projectRoot $directory) -Force | Out-Null
}
function EditorScript([string]$script){
    if(-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $script))){throw "Missing project script: $script"}
    & $commandlet @baseArgs '-run=pythonscript' "-script=$PSScriptRoot\$script" '-nullrhi' '-unattended' '-nosound' "-abslog=$projectRoot\Validation\$script.log"
    if($LASTEXITCODE -ne 0){throw "Script $script failed. See Validation log."}
}
function ValidateSavedProject {
    # Separate commandlet invocations reopen saved assets in fresh processes.
    EditorScript 'validate_reconstruction.py'
    EditorScript 'validate_render_stage.py'
}
if(-not (Test-Path -LiteralPath $project)){throw "Project file not found: $project"}
if(-not (Test-Path -LiteralPath $editor)){throw "Expected Unreal Engine 5.4 installation not found: $editor"}
switch($Action){
 'Encode1080' { & $uePython "$PSScriptRoot\encode_deliverables.py" '--source' '1080' }
 'Encode4K' { & $uePython "$PSScriptRoot\encode_deliverables.py" '--source' '4k' }
 'EncodeAll' { & $uePython "$PSScriptRoot\encode_deliverables.py" '--source' '4k' '--include-inspection' }
 'Open' { & $editor @baseArgs "-ExecutePythonScript=$PSScriptRoot\open_workbench.py" }
 'Play' { & $editor @baseArgs $map '-game' '-windowed' '-ResX=1280' '-ResY=720' '-ExecCmds=t.MaxFPS 30' }
 'Physics' { & $editor @baseArgs '/Game/Maps/Physics_GravityOnly_Baseline' '-game' '-windowed' '-ResX=1280' '-ResY=720' '-ExecCmds=t.MaxFPS 30' }
 'Generate' {
    if(-not (Test-Path -LiteralPath $blender)){throw "Blender 4.2 not found: $blender"}
    foreach($relative in @('Data\trajectory_fit.csv','Data\camera_fit_keys.json','Data\camera_close_fit.json','Data\ramp_parameters.json','Data\vehicle_clearance_adjustment.json','AssetsSource\vehicle_parameters.json')){
        if(-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative))){throw "Missing fitted input: $relative. Restore the supplied data checkpoint before rebuilding."}
    }
    # Refresh the sampled ramp before the vehicle clearance guard reads it.
    # This also writes a separate seed; trajectory_fit.csv stays authoritative.
    & $uePython "$PSScriptRoot\generate_motion.py"
    if($LASTEXITCODE -ne 0){throw 'Motion seed generation failed'}
    & $blender '--background' '--factory-startup' '--threads' '4' '--python' "$PSScriptRoot\build_vehicle_blender.py"
    if($LASTEXITCODE -ne 0){throw 'Vehicle generation failed'}
    & $blender '--background' '--factory-startup' '--threads' '4' '--python' "$PSScriptRoot\build_ramp_blender.py"
    if($LASTEXITCODE -ne 0){throw 'Ramp generation failed'}
    EditorScript 'build_all.py'
    ValidateSavedProject
 }
 'Validate' { ValidateSavedProject }
 default {
    $preset=switch($Action){'Render4K' {'Ramp_Final_4K'} 'RenderMask' {'Ramp_Validation_CarMask'} 'RenderInspection' {'Ramp_Inspection_720'} default {'Ramp_Final_1080'}}
    $sequence=if($Action -eq 'RenderInspection'){'SEQ_Ramp_Inspection'}else{'SEQ_Ramp_Draft'}
    $manifestPath=Join-Path $projectRoot 'Validation\build_manifest.json'
    if(-not (Test-Path -LiteralPath $manifestPath)){$manifestPath=Join-Path $projectRoot 'PUBLICATION_MANIFEST.json'}
    if(-not (Test-Path -LiteralPath $manifestPath)){throw 'Missing build or publication manifest. Restore the release or rebuild before rendering.'}
    $receiptPath=Join-Path $projectRoot "Validation\render_receipt_$preset.json"
    $renderStarted=[DateTime]::UtcNow
    $receipt=[ordered]@{status='running';preset=$preset;sequence=$sequence;map='/Game/Maps/Ramp_Render_Stage';render_start_utc=$renderStarted.ToString('o');build_manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLower();build_manifest_mtime_utc=(Get-Item -LiteralPath $manifestPath).LastWriteTimeUtc.ToString('o')}
    $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    & $commandlet @baseArgs '/Game/Maps/Ramp_Render_Stage' '-game' "-LevelSequence=/Game/Sequences/$sequence.$sequence" "-MoviePipelineConfig=/Game/Render/$preset.$preset" '-windowed' '-ResX=1280' '-ResY=720' '-unattended' '-nosound' "-abslog=$projectRoot\Validation\render_$preset.log"
    $renderExitCode=$LASTEXITCODE
    $receipt['render_end_utc']=[DateTime]::UtcNow.ToString('o')
    $receipt['elapsed_wall_seconds']=([DateTime]::UtcNow-$renderStarted).TotalSeconds
    $receipt['exit_code']=$renderExitCode
    $receipt['status']=if($renderExitCode -eq 0){'process_completed_pending_frame_validation'}else{'process_failed'}
    $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    if($renderExitCode -ne 0){throw "Render failed with code $renderExitCode. See Validation log."}
 }
}
if($LASTEXITCODE -ne 0){throw "Unreal exited with code $LASTEXITCODE. See Validation logs."}
