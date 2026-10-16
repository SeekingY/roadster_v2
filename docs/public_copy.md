# 公开副本准备 / Public-copy preparation

画质数字来自原工程最终本地测量版本（构建清单SHA-256前缀 `f404e1e4`）。公开副本保留该版本的场景、轨迹、车身与自制成片，另行做路径可移植和元数据清理；没有将清理后的副本宣称为新一轮画质测量。

Image metrics belong to the original final locally evaluated build (manifest SHA-256 prefix `f404e1e4`). The public derivative retains its scene, trajectory, vehicle and rendered videos, with separate portability/metadata changes. Those changes are not presented as a new fidelity evaluation.

- 通过Blender 4.2 API清理两个`.blend`里的本机路径与File Browser目录；保存前后evaluated mesh的坐标、变换、三角面和材质签名相同。 / Blender APIs cleared local paths and file-browser state in both `.blend` files; evaluated mesh coordinates, transforms, triangles and materials retained identical signatures.
- 坡道FBX从无本机文件名的临时场景导出，清除ApplicationNativeFile路径；原版与公开版实际重新导入后的几何、材质与UV签名相同。 / Ramp FBX was exported from an unsaved scene to remove its native-file path; actual reimport produced identical geometry/material/UV signatures.
- 通过UE5.4.3 API把7个渲染预设输出改成`{project_dir}/Renders/...`，清除6个静态网格的导入源文件引用。没有修改镜头、运动或网格几何。 / UE APIs changed seven render-preset output paths to project-relative tokens and cleared import-source references on six static meshes, without changing cameras, motion or geometry.
- 在新的UE进程重开已保存的公开工程，确认419帧、24000/1001 fps，144/240帧位置与CSV的差值均小于0.001cm。 / A fresh UE process reopened the saved public project and confirmed its frame range/rate; positions at 144/240 matched the CSV within 0.001cm.

检查使用原生API，没有十六进制修改二进制文件。路径检查包括53个`.blend`、FBX、uasset和umap；完整本机日志与清理过程报告留在本地，没有纳入公开子集。清理使部分文件哈希发生变化，不能再用原文件字节哈希替代公开副本自身清单。

Cleanup used native APIs, not hex patches. A private-path scan covered 53 Blender/FBX/Unreal binary assets. Full local logs and preparation reports are omitted from the public subset. Some file hashes necessarily changed; the public-copy manifest must be used instead of treating original byte hashes as identical.
