# Ning Visual Identity Extractor / 宁宁视觉身份提取

目标：**照片 → 面部几何与姿态结构化数据 + 人工核对的视觉文字档案 → 提供给 ChatGPT 的提示词**。不是 LoRA 训练、不是模型权重蒸馏，**不保证只靠文字恢复精确身份**。

## 上游项目（不复制第三方源码）

| 项目 | 上游 | 用途 | 本仓库状态 |
|---|---|---|---|
| MediaPipe | https://github.com/google-ai-edge/mediapipe | Face Landmarker、Pose Landmarker | 首期可选安装，脚本基于 Face Mesh 提取归一化关键点 |
| InsightFace | https://github.com/deepinsight/insightface | 额外人脸定位、关键点分析 | 可选；不上传人脸 embeddings，留意模型权重非商用许可 |
| JoyCaption | https://github.com/fpgaminer/joycaption | 图片内容与服装的细粒度文字描述 | 可选，较大的 VLM 不适合强制安装在 6GB 显存电脑 |
| Florence-2 | https://huggingface.co/microsoft/Florence-2-base | 图片描述模型与辅助识别 | 可选；这是模型仓库，不是 microsoft/Florence-2 GitHub 仓库 |

## Windows 安装（PowerShell）

```powershell
cd skills/ning-visual-identity
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python extract.py --image "D:\\private\\ning\\reference_02.jpg" --out "D:\\private\\ning\\output"
```

脚本使用 CPU 即可运行，**无需 NVIDIA GPU**。如果 MediaPipe API 不兼容你的 Python 版本，请使用 Python 3.11，并按 `requirements.txt` 版本区间安装。

输出：
- `landmarks.json`：468 个归一化人脸网格点（若检测成功）；仅用于几何参考，**不等于生物身份的数字复制**。
- `ning_visual_profile.md`：人工复核模板，明确哪些结论可观察、哪些仍待补充。
- `ning_generation_prompt.md`：ChatGPT 可用的身份一致性提示词模板。

## 重要规则

1. **第二张实验室回眸原图是宁宁的唯一主脸和主身形锚点**；图一、图三只辅助搭配和光线，不用于混合人脸。
2. 首先观察照片、手工校准文字，**不要把角度、光线、透视造成的表观比例当成准确的人体尺寸**。
3. MediaPipe 脚本输出的面部关键点并不会自动得到“鼻梁多高”等可靠自然语言结论；这些描述需要视觉模型或人工复核。
4. `data/`、`output/`、`*.onnx`、人物照片、向量文件与训练权重不得提交到公共仓库。这个 GitHub 仓库是公开的。
5. 仅将参考照片送入可信任环境；第三方模型许可证需要单独确认。

## 后续选择

如果你希望 VLM 自动生成详细 caption，可以在本机或托管推理环境按上游说明单独安装 JoyCaption / Florence-2，再把候选 caption 人工整理到 `ning_visual_profile.md`。**无须先购买云 GPU**，首期轻量流程完全 CPU 可用。
