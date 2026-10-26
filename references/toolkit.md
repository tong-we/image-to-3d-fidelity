# 工具调用与配置

这些工具只处理已有的真实模型/渲染，不会单靠一张图片自动猜出完美网格。建模判断按SKILL与reconstruction执行，工具负责稳定生成和核对证据。

## 环境与命令

普通Python需Pillow，Blender脚本用其内置bpy/NumPy。先定位现有环境，不自动安装。下例中的`SKILL`是本技能目录，`PROJECT`是本次独立项目目录，路径由当前任务确定。

```text
python SKILL/scripts/project_record.py init --project PROJECT --reference INPUT_IMAGE --identity-notes "主参考和必须保留的特征"
blender -b -t 6 --python-exit-code 9 --python SKILL/scripts/audit_mesh.py -- --blend PROJECT/working/model.blend --config PROJECT/model_config.json --out PROJECT/review/data.json --snapshot-out PROJECT/review/baseline.json --strict
blender -b -t 6 --python-exit-code 9 --python SKILL/scripts/render_views.py -- --blend PROJECT/working/model.blend --config PROJECT/model_config.json --out PROJECT/review/views --preset review8 --resolution 1024 --samples 16
blender -b -t 6 --python-exit-code 9 --python SKILL/scripts/export_static.py -- --blend PROJECT/working/model.blend --config PROJECT/model_config.json --out PROJECT/delivery/model --formats blend,glb,fbx,obj --clay
python SKILL/scripts/make_review.py --manifest PROJECT/review/views/render_manifest.json --out PROJECT/delivery/review --reference INPUT_IMAGE --config PROJECT/model_config.json --model PROJECT/delivery/model/model.glb --clay PROJECT/delivery/model/model_clay.glb --export-report PROJECT/delivery/model/export_report.json --package PROJECT/delivery/package.zip
```

每个渲染/导出/审阅输出目录用新的空目录，避免旧图与新模型混杂。只录入需要的格式；无FBX/OBJ需求时用默认BLEND/GLB。退出码3表示某些导出材质还需处理，不能报告全部导出成功。几何检查`--strict`遇到配置失败退出2；正常输出仍不是视觉验收。

`project_record.py record --project PROJECT --model MODEL --status candidate --note "本次改动"`记录候选。只有直接用户反馈确认时才用`--status user-approved --approval-evidence "实际反馈"`，不拿自动测试代替。

## JSON配置字段

配置不必包含所有字段。对象名、坐标、相机和阈值必须依据当前对象与用途确定。

| 字段 | 说明 |
|---|---|
| `subject_objects` | 网格对象名列表。场景里有地面/旧稿/其它主体时必须明确选择，避免把环境当角色。缺省为所有未隐藏渲染的网格，并在清单列出。 |
| `frame` | 选定当前姿态帧（需要时）。 |
| `lighting` | `studio`创建固定柔光棚；`existing`保留原光照。始终同一套灯光，不逐角度摆灯。 |
| `camera.target` | 统一观察中心的世界坐标；省略时用包围盒中心。 |
| `camera.ortho_scale` | 统一正交范围；省略时按所有指定方向的包围盒投影与填充比例计算。 |
| `camera.fill_fraction` | 自动取景占比，默认0.88；这是构图值，不改变模型。 |
| `camera.front_yaw_degrees` | 模型不是朝-Y时，整体相机方向偏移，不镜像模型。 |
| `views` | 可选自定义列表：`id`、`label`、`yaw`、`elevation`，必要时`allow_crop`。近景被裁切必须明确标记，不能冒充完整全身。 |
| `require_closed` / `allowed_open_meshes` | 本次实体闭合约束与有意开放的例外。 |
| `require_positive_volume` / `require_single_component` | 根据用途启用，非所有资产通用。 |
| `reject_degenerate` | 默认true，退化三角视为数据错误。 |
| `reject_self_intersections` | 把非邻接BVH候选列为失败；仍需视觉解释数值误差/共面。 |
| `expected_intersections` | 预期接合的对象名对。 |
| `reject_unexpected_intersections` | 显式清单以外的表面交叉作为失败。 |
| `require_contact_pairs` | 必须有表面交叉的名对；完全埋入而不穿出表面的部件改用接触探针。 |
| `contact_probes` | 每项`mesh`、`inside`、`toward`、`min_depth`、`min_engagement`，单位为当前场景世界单位；仅闭合表面，点内是启发式。 |
| `protected_snapshot` / `protected_objects` | 基线JSON及需逐点保持的对象，快照路径可相对配置文件。只哈希几何，不冒充材质保护；材质另做文件/像素检查。 |
| `reference_alignment` | 单一整体`scale`与`offset_xy_px`；先匹配相机，不能逐部件变形或调整宽高。 |
| `comparison_regions` | 源图同画布矩形，格式`名称:[x,y,width,height]`；只改变观察窗口。 |

## 视角约定

Blender世界Z向上、正面朝-Y；相机绕向量`(sin(yaw),-cos(yaw),0)`放置。`review8`采用相机侧命名：0、-45、+45、+90、-90、+135、180、-135。`orthographic8`提供正面、两前45、两侧、背、真顶、真底。`face-direction8`采用画面中主体朝向的左右约定，左朝向使用+45/+90，右朝向使用-45/-90。使用平台输入时先核对其示意方向，不假设某种命名适用于所有产品。

顶视时正面在图片下方，底视时正面在上方。俯仰变化后不要单独放大顶/底图：厚度小于高度时，投影显得更扁是正常的。

## 原图与交互

`make_review.py`检查渲染源文件仍存在且SHA没变。装GLB时还要求匹配的`export_report.json`，防止旧GLB配新海报。它拒绝远程纹理和需额外Draco/meshopt/KTX2解码资源的GLB；先用本地导出得到普通内嵌贴图GLB。

输出：独立无字PNG、拼图、原图原始副本、整体对齐模型图、离线`review.html`和数据记录。可选压缩包包含记录过的导出文件，不能自动称用户已认可。查看页不装GLB时会明确说仅是图像核对，不能把它称旋转模型。

离线打开或使用已有本地服务；若需临时服务，用独立端口且不影响现有预览。实际点击仅原图/仅模型、滑动、分界、自动渐变与暂停；装模型后真实拖动、复位和灰模切换。保存当前页面截图以及拖动前后、暂停帧的观察结果。脚本自己不替你做这一步。

## 连续扫掠

`blender_forms.round_sweep`接受中心线实际采样点、圆半径列表或每点两个椭圆半径，可选材质。需要柔和手臂时先均匀采样平滑曲线，不能只把两三个Bezier控制点直接当作环中心。它拒绝重复点、零切向尖点、非正半径、近反向切线和覆盖同名对象，创建有圆端帽的新网格。它不自动融合躯干、生成语义UV、修复回环自交或决定手指形象；这些仍需按原图完成。
