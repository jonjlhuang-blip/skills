"""CPU face geometry + explicitly reviewed descriptions. No cloud calls or training."""
import argparse
import json
import math
import subprocess
from pathlib import Path

FEATURE_LABELS = {
    "face_outline": "脸型与轮廓", "eyes": "眼睛", "brows": "眉毛",
    "nose": "鼻部", "mouth": "嘴唇", "hair": "头发",
    "skin": "肤色与质感", "body_silhouette": "可见身形",
}
OUTPUT_FILES = (
    "landmarks.json", "ning_visual_identity.json", "profile_draft.json",
    "ning_visual_profile.md", "ning_generation_prompt.md", "review_report.md",
)
MESH_CAVEAT = (
    "Coordinates and ratios describe the oriented image, depend on pose, lens and "
    "perspective, and cannot establish identity, physical dimensions or true head pose. "
    "x/y are relative to image width/height; z is relative depth, not metres."
)
TEXT_CAVEAT = "文字会丢失五官之间的细微空间关系，不能保证精确复现身份；附原始主参考图通常更可靠。"


def load_rgb(path):
    """Decode Unicode paths; apply EXIF orientation before inference."""
    import numpy as np
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(path) as source:
            source.load()
            rgba = ImageOps.exif_transpose(source).convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            return np.array(Image.alpha_composite(background, rgba).convert("RGB"))
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Could not decode image: {path.name}") from exc


def projected_metrics(points, width, height):
    """Use pixel distances, avoiding non-square normalized-coordinate bias."""
    def point(i):
        return (points[i]["x"] * width, points[i]["y"] * height)
    def midpoint(a, b):
        return tuple((x + y) / 2 for x, y in zip(point(a), point(b)))
    eye_a, eye_b = midpoint(33, 133), midpoint(263, 362)
    face_width = math.dist(point(234), point(454))
    face_height = math.dist(point(10), point(152))
    return {
        "face_width_to_height_projected": round(face_width / face_height, 4) if face_height else None,
        "eye_center_distance_to_face_width_projected": round(math.dist(eye_a, eye_b) / face_width, 4) if face_width else None,
        "eye_axis_tilt_degrees_in_image": round(math.degrees(math.atan2(eye_b[1] - eye_a[1], eye_b[0] - eye_a[0])), 2),
        "interpretation": "Image geometry only; eye centres approximate eyelid corners, not pupils. Tilt is not 3D head yaw/pitch/roll.",
    }


def extract_geometry(rgb, reference_id, role):
    import mediapipe as mp
    if not hasattr(mp, "solutions"):
        raise ValueError("MediaPipe solutions API unavailable; install pinned requirements.txt in a clean venv.")
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=2, refine_landmarks=False,
        min_detection_confidence=0.5,
    ) as mesh:
        result = mesh.process(rgb)
    faces = result.multi_face_landmarks or []
    height, width = rgb.shape[:2]
    points = [{"x": round(p.x, 6), "y": round(p.y, 6), "z": round(p.z, 6)} for p in faces[0].landmark] if len(faces) == 1 else []
    return {
        "reference_id": reference_id, "reference_role": role,
        "width": width, "height": height, "detected_faces": len(faces),
        "face_detection_cap": 2,
        "detection_status": "one_face" if len(faces) == 1 else "no_face" if not faces else "ambiguous_multiple_faces",
        "normalized_face_landmarks": points,
        "projected_metrics": projected_metrics(points, width, height) if points else {},
        "caveat": MESH_CAVEAT,
    }


def load_profile(path, reference_ids, primary_id):
    from jsonschema import Draft202012Validator
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Reviewed profile is not readable UTF-8 JSON") from exc
    schema = json.loads(Path(__file__).with_name("profile.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(profile), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        field = ".".join(str(part) for part in error.path) or "profile"
        # ValidationError.message may echo private instance values.
        raise ValueError(f"Reviewed profile schema violation at {field} ({error.validator})")
    policy = profile["reference_policy"]
    if policy["primary_id"] != primary_id:
        raise ValueError("Profile primary_id does not match --primary-index")
    if set(policy["auxiliary_ids"]) != set(reference_ids) - {primary_id}:
        raise ValueError("Profile auxiliary_ids do not match input references")
    observed = [entry["reference_id"] for entry in profile["reference_observations"]]
    if len(observed) != len(set(observed)) or set(observed) != set(reference_ids):
        raise ValueError("Profile must describe each input reference exactly once")
    for feature in profile["identity_features"].values():
        if set(feature["evidence"]) != {primary_id}:
            raise ValueError("Identity features must use only the primary reference as evidence")
    for entry in profile["reference_observations"]:
        expected = "primary" if entry["reference_id"] == primary_id else "auxiliary"
        if entry["role"] != expected:
            raise ValueError("Reference observation role conflicts with --primary-index")
    return profile


def private_output_guard(out):
    """Reject tracked or unignored reports inside a Git checkout."""
    if any((out / name).is_symlink() for name in OUTPUT_FILES):
        raise ValueError("Output files must not be symlinks")
    for parent in (out, *out.parents):
        if not (parent / ".git").exists():
            continue
        try:
            repository = subprocess.run(["git", "-C", str(parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
            # A placeholder .git directory does not establish a Git checkout.
            if repository.returncode or Path(repository.stdout.strip()).resolve() != parent:
                continue
            paths = [(out / name).relative_to(parent).as_posix() for name in OUTPUT_FILES]
            tracked = subprocess.run(["git", "-C", str(parent), "ls-files", "-z", "--", *paths], capture_output=True, check=True)
            ignored = subprocess.run(["git", "-C", str(parent), "check-ignore", "--stdin", "-z"], input="\0".join(paths) + "\0", capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("Cannot verify output privacy; choose a folder outside the Git checkout") from exc
        if tracked.stdout or ignored.returncode not in (0, 1) or set(ignored.stdout.rstrip("\0").split("\0")) != set(paths):
            raise ValueError("Output may be tracked by Git; choose a private folder outside the checkout or an ignored output/ folder")
        break


def make_draft(reference_ids, primary_id):
    return {
        "schema_version": "1.0", "subject": {"name": "宁宁", "presentation": "由用户指定的成年女性角色"},
        "review_method": "direct_visual_review",
        "reference_policy": {"primary_id": primary_id, "auxiliary_ids": [r for r in reference_ids if r != primary_id], "notes": ["主图决定脸和身形；辅助图只描述场景、姿势、服装和光线差异。"]},
        "identity_features": {name: {"description": "", "confidence": "medium", "evidence": [primary_id], "limitations": []} for name in FEATURE_LABELS},
        "reference_observations": [{"reference_id": r, "role": "primary" if r == primary_id else "auxiliary", "pose": "", "expression": "", "clothing": "", "lighting": "", "framing": "", "scene": "", "differences": [], "limitations": []} for r in reference_ids],
        "generation": {"target_scene": "", "avoid": []},
        "unknowns": ["真实年龄、身高、体重和身体尺寸不从照片推断。"],
    }


def render_profile(profile):
    policy = profile["reference_policy"]
    lines = [f"# {profile['subject']['name']}｜完整视觉身份档案", "", f"主参考：{policy['primary_id']}；审核方式：直接视觉复核。", "", profile["subject"]["presentation"], ""]
    lines.extend(f"- {note}" for note in policy["notes"])
    lines.extend(["", "## 身份特征（主图观察）", ""])
    for key, label in FEATURE_LABELS.items():
        item = profile["identity_features"][key]
        lines.extend([f"### {label}", "", item["description"], "", f"观察置信度：{item['confidence']}；来源：{', '.join(item['evidence'])}。", ""])
        lines.extend(f"- 边界：{v}" for v in item["limitations"])
        lines.append("")
    labels = {"pose": "姿势", "expression": "表情", "clothing": "服装", "lighting": "光线", "framing": "构图", "scene": "背景"}
    lines.extend(["## 逐图场景与差异", ""])
    for ref in profile["reference_observations"]:
        lines.extend([f"### {ref['reference_id']}（{ref['role']}）", ""])
        lines.extend(f"- {label}：{ref[key]}" for key, label in labels.items())
        lines.extend(f"- 差异：{v}" for v in ref["differences"])
        lines.extend(f"- 不确定性：{v}" for v in ref["limitations"])
        lines.append("")
    lines.extend(["## 无法从这些照片可靠确定", ""])
    lines.extend(f"- {v}" for v in profile["unknowns"])
    lines.extend(["", TEXT_CAVEAT, ""])
    return "\n".join(lines)


def render_prompt(profile):
    primary_id = profile["reference_policy"]["primary_id"]
    features = "\n".join(f"- {label}：{profile['identity_features'][key]['description']}" for key, label in FEATURE_LABELS.items())
    avoid = "\n".join(f"- {item}" for item in profile["generation"]["avoid"])
    scene = profile["generation"]["target_scene"]
    return (
        "# ChatGPT 图像生成提示词\n\n## 附主参考图版本（推荐）\n\n"
        f"以附件中标明 {primary_id} 的原图作为宁宁唯一的脸部和自然身形参考，生成同一成年女性角色的真实摄影风格照片。"
        "保持主图五官之间的关系、柔和脸部轮廓与自然身形，不把其他图片的面部特征混入。"
        "以下文字用于提示重点；文字与主图存在冲突时以主图为准。\n\n"
        f"{features}\n\n场景要求：{scene}\n\n避免：\n{avoid}\n\n"
        "## 仅文字版本（没有参考图时）\n\n生成一张成年女性角色宁宁的真实摄影风格照片，遵循以下外观描述，保留自然皮肤和人体比例。\n\n"
        f"{features}\n\n场景要求：{scene}\n\n避免：\n{avoid}\n\n使用边界：{TEXT_CAVEAT}\n\n"
        "## 换场景复用\n\n保留上述身份特征，只替换“场景要求”的服装、动作、环境与光线。"
        "改变头发绑法、表情或相机角度时，以主图人物为准。\n"
    )


def render_review(profile, references):
    lines = ["# 输出与参考图对照", "", "本报告比较文字档案与输入照片的观察依据，以及照片的投影几何差异；未生成新照片、未计算身份相似率。", "", "## 观察依据与文字损失", ""]
    for key, label in FEATURE_LABELS.items():
        item = profile["identity_features"][key]
        lines.append(f"- {label}：依据 {', '.join(item['evidence'])}，观察置信度 {item['confidence']}。")
        lines.extend(f"  - 仍可能丢失：{v}" for v in item["limitations"])
    lines.extend(["", "## 逐图差异", ""])
    for ref in profile["reference_observations"]:
        lines.extend([f"### {ref['reference_id']}", ""])
        lines.extend(f"- {v}" for v in ref["differences"])
        lines.extend(f"- 限制：{v}" for v in ref["limitations"])
        lines.append("")
    lines.extend(["## 真实 CPU 检测结果", "", "| 参考图 | 角色 | 尺寸 | 检出人脸 | 网格点 | 投影脸宽/脸长 | 眼轴倾斜角 |", "|---|---|---|---:|---:|---:|---:|"])
    for ref in references:
        metrics = ref["projected_metrics"]
        lines.append(f"| {ref['reference_id']} | {ref['reference_role']} | {ref['width']} × {ref['height']} | {ref['detected_faces']} | {len(ref['normalized_face_landmarks'])} | {metrics.get('face_width_to_height_projected', '—')} | {metrics.get('eye_axis_tilt_degrees_in_image', '—')} |")
    lines.extend(["", MESH_CAVEAT, "", "## 验收边界", "", "- 几何由 MediaPipe 在实际输入上计算；文字由直接视觉复核提供，脚本校验结构和参考角色后输出。", "- 几何比值仅描述当前图像；表情、转头、俯拍、前倾与服装都会改变表观外形，不能反推人体尺寸。", "- 文字不能保存纹理、微小非对称和全部空间关系。", f"- {TEXT_CAVEAT}", ""])
    return "\n".join(lines)


def write_outputs(out, references, primary_id, profile):
    primary = next(r for r in references if r["reference_id"] == primary_id)
    # Keep original primary-only landmarks keys for existing consumers.
    geometry = {**primary, "schema_version": "1.0", "primary_reference_id": primary_id, "references": references}
    identity = {
        "schema_version": "1.0", "review_status": "complete" if profile else "pending_visual_review",
        "primary_reference_id": primary_id,
        "geometry_summary": [{k: v for k, v in r.items() if k != "normalized_face_landmarks"} for r in references],
        "reviewed_profile": profile, "limitations": [MESH_CAVEAT, TEXT_CAVEAT],
    }
    payloads = {"landmarks.json": json.dumps(geometry, ensure_ascii=False, indent=2, allow_nan=False) + "\n", "ning_visual_identity.json": json.dumps(identity, ensure_ascii=False, indent=2, allow_nan=False) + "\n"}
    if profile:
        payloads.update({"ning_visual_profile.md": render_profile(profile), "ning_generation_prompt.md": render_prompt(profile), "review_report.md": render_review(profile, references)})
    else:
        payloads["profile_draft.json"] = json.dumps(make_draft([r["reference_id"] for r in references], primary_id), ensure_ascii=False, indent=2) + "\n"
        payloads["ning_visual_profile.md"] = f"# 待视觉复核\n\n主参考：{primary_id}。\n\n已提取几何数据；尚未填写外观描述。直接观察图片，填写 profile_draft.json 后以 --profile 重跑。\n"
        payloads["ning_generation_prompt.md"] = "# 尚未生成提示词\n\n先提供通过校验的 --profile；空模板不作为完整视觉档案交付。\n"
        payloads["review_report.md"] = "# 待对照\n\n当前仅完成几何提取，尚未完成文字与原图的视觉对照。\n"
    out.mkdir(parents=True, exist_ok=True)
    for name, contents in payloads.items():
        (out / name).write_text(contents, encoding="utf-8")
    if profile and (out / "profile_draft.json").exists():
        (out / "profile_draft.json").unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract private CPU face geometry and render a reviewed visual identity")
    parser.add_argument("--image", required=True, action="append", type=Path, help="Repeat for multiple references; order defines reference_01, reference_02, …")
    parser.add_argument("--primary-index", type=int, default=1, help="1-based primary reference index (default: 1)")
    parser.add_argument("--profile", type=Path, help="Directly reviewed JSON matching profile.schema.json")
    parser.add_argument("--out", type=Path, default=Path("output"))
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.primary_index <= len(args.image):
            raise ValueError("--primary-index must identify an input --image (1-based)")
        for path in args.image:
            if not path.is_file():
                raise ValueError(f"Image not found: {path.name}")
        out = args.out.resolve()
        private_output_guard(out)
        for path in [*args.image, *([args.profile] if args.profile else [])]:
            if path.resolve() in {out / name for name in OUTPUT_FILES}:
                raise ValueError("Output would overwrite an input; choose another private folder")
        reference_ids = [f"reference_{index:02d}" for index in range(1, len(args.image) + 1)]
        primary_id = reference_ids[args.primary_index - 1]
        profile = load_profile(args.profile, reference_ids, primary_id) if args.profile else None
        references = []
        for path, reference_id in zip(args.image, reference_ids):
            role = "primary" if reference_id == primary_id else "auxiliary"
            geometry = extract_geometry(load_rgb(path), reference_id, role)
            if geometry["detected_faces"] > 1:
                raise ValueError(f"{reference_id}: multiple faces detected; provide a single-person reference")
            if geometry["detected_faces"] == 0:
                raise ValueError(f"{reference_id}: no face detected; provide a clearer reference")
            references.append(geometry)
        write_outputs(out, references, primary_id, profile)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Wrote private outputs to {out}; primary: {primary_id}; review: {'complete' if profile else 'pending_visual_review'}")
    for ref in references:
        print(f"{ref['reference_id']}: {ref['detected_faces']} face, {len(ref['normalized_face_landmarks'])} landmarks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
