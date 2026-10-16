# 验证摘要与差距 / Validation and remaining gaps

这是本地已测版本的结果摘要。公开仓库省略了含本机路径的完整日志和官方参考像素，因此不是原始证据归档，也不保证仅克隆仓库就能独立复算所有参考图指标。

This summarizes the locally evaluated build. Full local logs and official reference pixels are omitted from the public subset, so this is not the complete evidence archive and does not promise standalone reproduction of every reference-image metric.

| 指标 / Metric | 结果 / Result | 范围 / Scope |
|---|---|---|
| Vehicle silhouette IoU | Mean **0.693439**, minimum **0.621942**; **0/6 ≥ 0.90** | Frames 96, 144, 192, 216, 240, 264 |
| Clear bbox-center error | Mean **4.796 px / 0.2177% diagonal** | 21 pre-labelled clear observations at 1920×1080 |
| All eligible bbox centers | Mean **4.918 px**, RMS **7.458 px**, max **22.209 px** | All 32 eligible observations; max at frame 288 |
| Body/primary-road intersection | No detected intersections | Actual source mesh triangles at 419 integer + 418 half-frame states |

轮廓目标未达标。中心是可见车身/轮胎包围框中心，不是物理重心。中心覆盖32/419帧，轮廓覆盖6/419帧；人工轮廓边界不确定度约±3–7px，不能把稀疏结果扩大为全片保证。

The silhouette target was not met. Centers describe visible vehicle bounding boxes, not physical centers of mass. Coverage is 32/419 frames for centers and 6/419 for silhouettes; manual silhouette boundaries have approximately ±3–7px uncertainty. These sparse measurements are not whole-film guarantees.

## 拟合与验收不是独立盲测 / Fitting and evaluation are not blind

7个位置留出帧共享相机、几何与先验。最终飞行姿态使用234/240/252帧的框，240帧还使用轮廓凸支撑；246/258/264像素未进入该姿态目标，但264固定端点姿态且已被查看。所有6个轮廓均经历过QA查看，后续调整属于迭代拟合。

Seven position holdouts share fitted cameras, geometry and priors. The final attitude fit uses boxes at 234/240/252 and silhouette support at 240. Pixels at 246/258/264 are withheld from that attitude objective, but 264 has a fixed endpoint pose and was already reviewed. All six masks have been seen during QA; this is not end-to-end blind validation.

## 实际验证了什么 / What was actually checked

本地UE5.4.3完成保存地图的新进程重开、原生序列绑定、随机跳转和播放控制验证。实际打包的Windows进程验证了自动播放与循环。离线输出核对419帧与24000/1001 fps；曾发现的MRQ默认运动模糊已通过 `r.MotionBlurQuality=0` 修正，实际4K快速翻转样本重新查看。

Local UE5.4.3 checks covered saved-map reopening in fresh processes, native bindings, seeking and playback controls. A packaged Windows process demonstrated autoplay and looping. Render outputs were checked for 419 frames at 24000/1001 fps. The unwanted MRQ velocity-blur pass was disabled with `r.MotionBlurQuality=0` and rapid-rotation 4K samples were reviewed again.

净空检查针对已选定轨迹上的实际网格三角面；它不是UE车辆碰撞仿真，不覆盖连续时间扫掠、支架或地面。接触段457个整/半帧采样未发现车身侵入，最小采样净空约0.865cm。修正涉及外侧悬垂缩短与局部下表面抬高，是可逆建模假设，不是实车尺寸恢复。

The clearance check uses actual mesh triangles under the selected motion. It is not a UE vehicle collision simulation and does not cover continuous swept motion, truss or ground. Contact-phase sampling at 457 integer/half states found no body penetration, with a minimum sampled clearance of about 0.865cm. Shorter outer overhangs and locally raised lower surfaces are reversible modeling assumptions, not recovered real dimensions.

## 未完成 / Unresolved

- 未覆盖直播首趟爬升、倒挂停留和倒退。 / The earlier climb, inverted hold and reverse descent are absent.
- 单目场景尺度、相机、形状与姿态不唯一；精确离轨与触地被遮挡，13.25秒落地是运动学假设。 / Monocular scale/camera/shape/attitude are non-unique; exact release and touchdown remain uncertain, and the 13.25s landing is assumed.
- 车身为外观初模；气流是程序化视觉近似，缺少可靠的真实喷口、流场与推力参数。 / The car is an exterior blockout and gas is a procedural visual approximation, without recovered nozzle/flow/thrust parameters.
- 参考回放是关键帧运动，不是已验证的车辆动力学。独立重力方块仅检查基础物理管线。 / Keyed replay is not validated vehicle dynamics; a gravity box only checks a basic physics pipeline.
- 整数帧LINEAR插值不保证连续时间C1。 / LINEAR interpolation of sampled Euler keys is not strictly continuous-time C1.
- 自定义独立运行时控制界面与全平台性能验收未完成。 / A custom standalone control interface and cross-platform performance validation remain unfinished.
