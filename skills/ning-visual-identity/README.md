# Ning Visual Identity Extractor / 宁宁视觉身份提取

照片 → **CPU 几何检测 + 直接视觉复核的外观档案** → 结构化 JSON、ChatGPT 提示词和对照报告。

这不是模型权重蒸馏或 LoRA 训练。MediaPipe 不会自动从网格点推导鼻梁高低、服装或完整外貌；直接观察照片并填写档案是必需步骤。只用文字不能保证精确身份复现。

## 安装

使用独立的 Python **3.11 或 3.12** 环境。CPU 即可运行，无需 NVIDIA GPU、云算力、API 密钥或另行下载模型权重。固定 MediaPipe、NumPy、OpenCV 和 JAX 版本，避免旧 FaceMesh API 与新版依赖冲突。

Windows PowerShell：

```powershell
cd skills/ning-visual-identity
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

Linux/macOS：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

## 两阶段运行

原照片和个人输出放在仓库之外的私密目录。按传入顺序编号 `reference_01`、`reference_02`；`--primary-index` 从 1 开始。宁宁这组照片使用**第二张原始实验室回眸图**作为唯一主脸和主身形参考，第一张只描述风格、姿势、穿搭与光线变化。

先提取真实几何和复核草稿：

```powershell
python extract.py --image "D:\private\ning\window.jpg" --image "D:\private\ning\laboratory.jpg" --primary-index 2 --out "D:\private\ning\output"
```

直接观察原图，把 `output/profile_draft.json` 中的空字段填写完整，另存为 `D:\private\ning\reviewed_profile.json`。依据 `profile.schema.json` 记录脸型、眼睛、眉毛、鼻部、嘴唇、头发、皮肤、可见身形；每项附来源、置信度和限制。把服装、表情、姿势、构图、光线和背景分开写在逐图观察中。身份特征的来源只能是主参考图。不要推断真实身份、族裔、实际年龄、身高、体重、三围或衣物遮挡下的精确形态。

用复核档案渲染完整结果：

```powershell
python extract.py --image "D:\private\ning\window.jpg" --image "D:\private\ning\laboratory.jpg" --primary-index 2 --profile "D:\private\ning\reviewed_profile.json" --out "D:\private\ning\output"
```

仍兼容单图命令 `python extract.py --image "D:\private\reference.jpg" --out "D:\private\output"`；此时第一张就是主图，**不会硬编码为原始第二张照片**。

## 输出

| 文件 | 内容 |
|---|---|
| `landmarks.json` | 每张图的 468 点面部网格、角色、尺寸、检测状态和投影几何；保留原版主图字段 |
| `ning_visual_identity.json` | `review_status`、几何摘要、完整复核档案和限制 |
| `ning_visual_profile.md` | 完整中文视觉身份描述与逐图观察 |
| `ning_generation_prompt.md` | 附主参考图提示词、仅文字提示词及换场景说明 |
| `review_report.md` | 文字与原图的观察依据、差异、文字损失及实际检测结果 |
| `profile_draft.json` | 只在没有 `--profile` 时输出的待填写草稿；复核运行后移除 |

`review_status: complete` 表示提供的复核档案通过结构和参考角色校验，**不是自动证明描述正确**。必须读回生成文档并与原图核对。不提供 `--profile` 时明确标注 `pending_visual_review`，不会把空模板称为完整结果。

网格 x/y 按图片宽高归一化，z 为相对深度。投影比值换算为像素后计算，避免竖幅图片的宽高归一化混用；这些值仍受角度、镜头、表情影响，不是真实身体尺寸或身份相似率。眼轴倾斜角也不是三维头部姿态。

## 输入与隐私保护

- 读取支持中文/Unicode 路径，先处理 EXIF 旋转；透明图片以白底合成后检测。输入多脸、无脸、损坏图片或参考角色冲突时非零退出。
- 脚本不调用云服务、不生成 embeddings、不上传原图。照片、坐标、个人档案和提示词都不得提交到公开仓库。
- 输出目录在 Git 仓库内时，只允许全部生成文件已被忽略且未被跟踪的路径；也拒绝输出文件符号链接和会覆盖输入文件的操作。优先使用仓库外私密目录。
- `.gitignore` 保护常见大小写图片扩展名、模型权重及生成文件；提交前仍使用明确的代码文件清单，避免 `git add .`。

## 验证

```bash
python -m unittest discover -s tests -v
```

公共回归测试使用临时合成图和合成档案，不包含人物照片。真实照片检测和视觉复核应在私密目录完成；对照报告不是图像生成结果的相似率评测。

## 可选上游

| 项目 | 来源 | 用途 |
|---|---|---|
| MediaPipe | https://github.com/google-ai-edge/mediapipe | 本流程使用安装包内 CPU FaceMesh 模型 |
| InsightFace | https://github.com/deepinsight/insightface | 可选人脸定位；本流程不安装、不输出 embeddings |
| JoyCaption | https://github.com/fpgaminer/joycaption | 可选 VLM caption；较大，不适合作为 6GB 显存的强制依赖 |
| Florence-2 | https://huggingface.co/microsoft/Florence-2-base | 可选辅助描述模型；本流程不安装 |

这些候选描述仍需逐项视觉复核，模型和权重的许可需分别确认。默认流程没有安装可选上游项目。
