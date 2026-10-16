# 打开、编辑与重建 / Open, edit and rebuild

## 打开保存的工程 / Open the saved project

Windows 上安装 Unreal Engine **5.4.3**，然后双击仓库根目录的 `Roadster_Demo_Reconstruction.uproject` 或 `Open_Project.cmd`。首次打开可能需要编译着色器。无需先下载参考视频，也无需运行视频拟合流程。

Install Unreal Engine **5.4.3** on Windows and open the root `.uproject` or `Open_Project.cmd`. Initial shader compilation may take time. Reference-video downloads and refitting are not required to open the saved scene.

```powershell
$env:UE_ROOT = 'D:\Epic Games\UE_5.4' # optional / 可选
.\Scripts\Run.ps1 -Action Open
```

主地图：`/Game/Maps/Ramp_Reconstruction_Draft`。主序列：`/Game/Sequences/SEQ_Ramp_Draft`。在 Sequencer 中锁定 Camera Cuts 可观看拟合机位；解除锁定即可自由检查。144、216、240、264 是方便检查的整数帧，不是精确接触事件标记。

Main map: `/Game/Maps/Ramp_Reconstruction_Draft`. Main sequence: `/Game/Sequences/SEQ_Ramp_Draft`. Use Sequencer for play/pause, frame stepping, seeking and playback rate. Unlock Camera Cuts for free inspection. Frames 144, 216, 240 and 264 are useful inspection points, not exact contact-event labels.

`Play_Reference.cmd` / `Run.ps1 -Action Play` 使用保存的原生 LevelSequence 播放。运行时不依赖 Python；独立运行时专用拖动/暂停界面尚未制作。

`Play_Reference.cmd` / `Run.ps1 -Action Play` uses native saved LevelSequence playback without runtime Python. A dedicated standalone playback-control interface has not been implemented.

## 编辑与重复生成 / Edit and regenerate

Blender **4.2** 用于重新生成 `.blend` 和 FBX；仅打开 UE 工程时不需要 Blender。非标准路径可设置：

Blender **4.2** is required to regenerate source models/FBX, but not to open the saved UE project. For a nonstandard installation:

```powershell
$env:BLENDER_EXE = 'D:\Blender\blender.exe'
.\Rebuild_From_Data.cmd
```

生成入口会写入它拥有的源模型和 UE 资产，先保留手工改动。它读取当前参数和已拟合轨迹，不会重新测量视频。直接编辑 `.blend` 后的改动不会自动进入程序化建模脚本。

Regeneration rewrites generated source models and UE assets; preserve manual edits first. It uses existing parameters and fitted motion, and does not refit the source video. Manual `.blend` edits are not automatically incorporated into the procedural model generator.

`Data/vehicle_clearance_adjustment.json` 保存局部车底/悬垂修正与输入哈希。修改坡道、车身比例或接触轨迹后，净空包络可能失效；生成器会中止过期输入，不能把删除校验当成修复。460cm 长度参数是修正前名义输入；实际导出尺寸见 `AssetsSource/vehicle_manifest.json`。

The clearance adjustment records a local underside/overhang correction with input hashes. Changed geometry/contact motion can invalidate it. Do not bypass a stale-input failure; recompute and validate the clearance. The 460cm length parameter is a pre-correction nominal input; use the vehicle manifest for actual exported bounds.

## 渲染 / Render

`Render_Reference_4K.cmd` 是4K入口；也可使用：

```powershell
.\Scripts\Run.ps1 -Action Render4K
```

如需将自制帧图编码成视频，设置本机已安装的 `FFMPEG_EXE`。仓库不附带 FFmpeg 或其他第三方可执行文件。编码不使用或生成官方/自制叠加对比片。不要同时启动两个向同一工程资产写入的进程。

Set `FFMPEG_EXE` to an installed FFmpeg executable when encoding the project's own rendered frames. Third-party executables are not bundled. The public encoding workflow does not create official/reference comparison videos. Avoid concurrent processes writing the same assets.

完成4K与检查镜头渲染后，`Run.ps1 -Action EncodeAll` 可编码自制4K、1080p和检查片；只需单个分辨率时使用 `Encode4K` 或 `Encode1080`。

After rendering 4K and inspection frames, `Run.ps1 -Action EncodeAll` encodes the project's 4K, 1080p and inspection videos. `Encode4K` and `Encode1080` are available separately.

原始本地制作已完成原生重开、播放、渲染和Windows运行验证；公开路径适配并不等于在每种机器上重新验证。若本机依赖或设置不同，应重新渲染并检查结果。

The original local build was reopened, played, rendered and runtime-tested. Portable paths do not mean every machine configuration has been tested; validate outputs after changing dependencies or settings.

`sanitize_public_blender.py` 和 `sanitize_public_unreal.py` 是发布副本准备工具，带目录名保护，不是正常打开/渲染的必要步骤。公开网格的导入源路径已清除；重新生成或导入时由本机建立新的路径。

The two `sanitize_public_*` scripts are release-preparation utilities with a directory-name guard, not required steps for ordinary playback/rendering. Public mesh import-source references were cleared; regeneration or reimport establishes local references on your machine.
