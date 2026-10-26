# Image-to-3D Fidelity · 图片转高还原 3D

**给 AI 建模代理使用的 Agent Skill：从参考图重建真实 3D 模型，保留原图形象，并用多视角、原图渐变和几何检查持续核验。**

适用于图片转 3D、角色与玩偶建模、已有模型修正、拍摄多视图，以及 BLEND / GLB / FBX / OBJ 静态资产交付。它提供建模工作流程和本地工具箱；建模代理仍需观察图片、选择方法、编写或操作建模工具并迭代。

[让 AI 安装](#让你的-ai-下载安装) · [手动安装](#手动安装) · [开始使用](#开始使用) · [依赖环境](#依赖环境) · [验证](#验证与测试) · [下载发布包](https://github.com/tong-we/image-to-3d-fidelity/releases/latest)

English: An Agent Skill and local toolkit for coding agents to reconstruct editable 3D models from reference images, preserve visual identity, and verify real geometry, views, textures, and static exports. The skill entrypoint is [`SKILL.md`](SKILL.md) at the repository root. Install the complete repository as `image-to-3d-fidelity` in your agent's supported skills directory; Blender and Python with Pillow are required. No pretrained weights or API key are bundled or required by these scripts.

## 让你的 AI 下载安装

把下面这段话直接发给**支持 Agent Skills、可联网并能读写本地文件的 AI 代理**：

```text
请从 https://github.com/tong-we/image-to-3d-fidelity 安装 image-to-3d-fidelity 技能。
先阅读 README.md 和 SKILL.md；SKILL.md 就在仓库根目录。
请按当前客户端支持的方式安装完整技能文件夹，确认技能能被发现和调用。
如果使用 Codex 的 skill-installer，仓库内路径为 .，安装名为 image-to-3d-fidelity。
检查本地 Blender、Python 和 Pillow，优先复用已有环境；缺少依赖时说明下载与安装需求。
安装后告诉我技能位置、如何调用和依赖检查结果，然后我会上传参考图开始建模。
```

对于 Codex，也可直接发送：

```text
请用 $skill-installer 安装 https://github.com/tong-we/image-to-3d-fidelity
仓库内路径：.；安装名称：image-to-3d-fidelity。
安装后确认技能被识别，并检查 Blender、Python 和 Pillow。
```

有些版本的安装器要求同时传入 `--path . --name image-to-3d-fidelity`，不要把仓库根目录的 `.` 当作安装名称。安装路径以当前客户端实际支持的目录为准；不要在多个位置重复安装同名技能。

仅能文字聊天、不能执行本地工具的 AI 可以阅读方法，但无法直接运行本技能完成 Blender 建模。不同代理的安装与调用方式可能不同；本仓库不宣称所有客户端均已实测兼容。

## 依赖环境

| 依赖 | 用途 | 说明 |
|---|---|---|
| 支持 Skills 的 AI 代理 | 理解参考图、决定造型、操作工具、迭代核验 | 需要图片理解、文件读写和命令执行能力 |
| Blender | 网格建模、渲染、审计及导出 | 使用 Blender 内置的 Python / `bpy` / NumPy，不需要另装 `bpy` |
| Python + Pillow | 项目记录、拼图、渐变核对页及打包 | Python 依赖列在 [`requirements.txt`](requirements.txt) |
| 现代 WebGL 浏览器 | 查看真实 GLB 与原图对照 | 查看器已随技能附带，生成的页面不需要 CDN |

工具已在 **Blender 5.1、Python 3.12 / 3.13** 环境验证。其它版本请先运行测试。可执行文件通过环境查找或命令行完整路径指定，脚本没有作者电脑的固定安装路径。

先检查已有环境：

```sh
blender --version
python --version
python -c "from PIL import Image; print(Image.__version__)"
```

只有缺少 Pillow 时，才在你选定的 Python 环境中安装：

```sh
python -m pip install -r requirements.txt
```

若 Blender 没有加入 PATH，找到其可执行文件，后续使用完整路径即可。详见[运行环境说明](references/runtime.md)。

**资源说明：**技能 ZIP 约 300 KB，解压后约 1 MB；不包含 Blender、Python、模型权重或用户模型。现有脚本不要求大型图生 3D 权重、GPU 推理框架或 API 密钥。AI 代理自身的使用费用、缺少软件的下载量，以及你另外选择的生成服务，分别计算；先检查本地环境再决定是否下载。

## 手动安装

### Codex：Git 安装

按[当前官方文档](https://learn.chatgpt.com/docs/build-skills)，用户级本地技能可放在 `~/.agents/skills`，项目级技能可放在项目的 `.agents/skills`。以下三选一。

Windows PowerShell：

```powershell
git clone --depth 1 https://github.com/tong-we/image-to-3d-fidelity.git "$env:USERPROFILE\.agents\skills\image-to-3d-fidelity"
```

macOS / Linux：

```sh
git clone --depth 1 https://github.com/tong-we/image-to-3d-fidelity.git "$HOME/.agents/skills/image-to-3d-fidelity"
```

项目级安装：

```sh
git clone --depth 1 https://github.com/tong-we/image-to-3d-fidelity.git .agents/skills/image-to-3d-fidelity
```

安装器或已有客户端可能使用其它支持的技能目录，以实际发现结果为准。已有同名目录时先检查来源和本地改动，不覆盖已有技能。安装后在技能列表中确认 `image-to-3d-fidelity` 已出现；没有出现时重启客户端再检查。

### ZIP 安装

1. 从 [Releases](https://github.com/tong-we/image-to-3d-fidelity/releases/latest) 下载 `image-to-3d-fidelity.zip`。
2. 解压出 `image-to-3d-fidelity` 文件夹，放入你的代理支持的技能目录。
3. 检查结构：`技能目录/image-to-3d-fidelity/SKILL.md`，保留同级的 `scripts`、`references`、`assets` 等文件夹，避免多套一层目录。
4. 确认客户端发现技能，并检查上面的运行环境。

GitHub 的 **Code → Download ZIP** 也可使用；其顶层文件夹通常带分支名，请改名为 `image-to-3d-fidelity` 后安装。使用其它代理时，采用该代理自己的技能目录和调用方式；`agents/openai.yaml` 只是可选的 OpenAI 界面元数据。

### 更新或卸载

通过 Git 克隆安装的版本，在技能文件夹中执行 `git pull --ff-only`。通过 ZIP 或安装器安装的版本，先保留本地修改，再按原安装方式更新。卸载时只移除该技能目录；模型和输出应保存在独立项目文件夹中。

## 开始使用

### 从参考图建模

在新话题上传原始参考图，告诉 AI 目标用途，再发送：

```text
请用 $image-to-3d-fidelity 根据这张参考图制作高还原、可编辑的真实3D模型。
保留原图轮廓、比例、表情、关键花纹和配件，合理补全看不到的侧背面。
先复用本地工具，按整体比例、真实连接、贴图与多视角逐步核验。
交付前实际查看原图渐变、全身多视角、近景、白模和离线旋转页。
需要交付：可编辑BLEND、内嵌贴图GLB、视角PNG、离线预览及核验记录。
```

`$image-to-3d-fidelity` 是 Codex 的显式调用写法；其它客户端请在技能选择器中选择它，或明确要求使用该技能。

### 只修已有模型

```text
请用 image-to-3d-fidelity 修正我提供的当前模型。
只调整我指出的部位，其它已经认可的轮廓、比例、材质和姿态保留。
先保存基线，再用原图渐变、整体多视角及局部近景检查修改是否协调。
```

### 只拍视图或导出

```text
请用 image-to-3d-fidelity 为这个模型导出正面、两前45°、两侧、背面、顶面和底面PNG。
保持模型不变，使用同一尺度、构图、光照和背景，视角必须由真实模型渲染。
分别保存无字图片，附一张标明方向的拼图，并打包成ZIP。
```

需要对接其它多视图平台时，附上该平台的方向示意图；不同平台的“左 / 右”命名可能不同。游戏用途请另行说明引擎、性能预算和动画需求；静态导出不代表已经完成骨骼、动画或引擎内验证。

## 工作流程与交付

1. **锁定形象**：保存原始参考，明确可见事实、侧背面假设，以及已获认可的部分。
2. **先核对整体**：轮廓与比例服从主参考；局部修改后立刻检查完整模型。
3. **检查真实空间**：观察部件厚度、肢体连续性、配件接合与遮挡，避免只在某一视角重合。
4. **分别排查几何和颜色**：用白模区分棱角、凹陷与 UV、重叠面、花纹、杂线问题。
5. **用当前资产核验**：原图渐变、整体多视角、局部近景、数据检查和导出重导入相互补充。
6. **交付可用文件**：按需要打包 BLEND、GLB、FBX / OBJ、PNG、离线页面和检查记录。

原图渐变会保留统一的整体对齐，不通过逐部件扭曲参考图来制造一致；离线旋转页加载实际 GLB，不用静态海报冒充三维模型。脚本检查通过仍需 AI 观察整模，最后的用户认可也应单独记录。

| 工具 | 作用 |
|---|---|
| `project_record.py` | 保存原图、记录文件哈希和模型候选状态 |
| `blender_forms.py` | 稳定截面与圆端帽扫掠构件 |
| `render_views.py` | 真实正交视图和相机清单 |
| `audit_mesh.py` | 网格、交叉候选、保护对象与连接探针 |
| `export_static.py` | 常见静态材质的 BLEND / GLB / FBX / OBJ 导出 |
| `make_review.py` | 原图渐变、分界、离线旋转页与打包 |

命令和配置见[工具文档](references/toolkit.md)；建模判断见[重建方法](references/reconstruction.md)；核验要求见[核验说明](references/verification.md)；文件准备见[交付说明](references/delivery.md)。

## 验证与测试

在仓库根目录执行以下命令；输出目录需为空，`--blender` 可换成可执行文件完整路径：

```sh
python -X utf8 tests/run_checks.py --blender blender --out ./test-output
```

测试自行生成几何和贴图，覆盖 16 项自动检查，包括真实渲染、几何检查、纹理导出、FBX / OBJ 重导入，以及开放实体、保护对象变动、过期渲染、意外裁切和远程纹理的拒绝。无需下载测试模型或大型权重。浏览器交互另按[验证说明](references/validation.md)检查。

自动测试检查工具行为，不能证明任意新输入已经达到视觉还原要求。单图不可见部分仍需合理推断；打印、缝制、动画和游戏运行需另做对应用途的验证。

## 常见问题

**安装后是不是就获得了一个图生 3D 大模型？** 这是工作流与工具型 Skill，模型本身由使用它的代理结合建模工具制作或修正。它没有附带预训练权重，也不承诺一键完成所有输入。

**只给 AI 仓库链接就能用吗？** 可以作为安装请求；前提是客户端允许联网、安装技能和运行本地工具。先确认安装与依赖，再上传图片。只浏览 README 的聊天窗口无法完成本地建模。

**需要把我的图片上传到某个服务吗？** 随附脚本在本地运行，不主动上传参考图或模型。AI 客户端及你选择的外部生成服务如何处理输入，由各自配置与条款决定。

**能直接放进游戏或制作实物吗？** 可以交付通用静态资产；实际引擎中的比例、材质、面数、碰撞和动画需要相应测试。可视模型不等于已经验证的打印件、纸样或实物。

**这是已经上架的插件吗？** 当前发布的是独立 Agent Skill 仓库和 ZIP。[OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills)也支持通过插件分发技能；本仓库没有宣称已进入任何插件市场。

## 开源与反馈

本项目原创脚本、文档和模板采用 [MIT License](LICENSE)，允许依许可使用、修改和再分发。随附查看器等第三方代码保留各自许可，见[第三方声明](assets/THIRD_PARTY_NOTICES.txt)及 `assets/licenses/`。许可不替用户图片、模型或其它第三方素材授予使用权。

欢迎通过 [Issues](https://github.com/tong-we/image-to-3d-fidelity/issues) 报告可复现的问题：请提供客户端、系统、Blender / Python 版本、执行命令和必要的错误信息。请先清除密钥、私人路径及无权公开的图片或模型；优先用合成场景复现。
