"""CPU-first reference-image geometry extractor. No cloud upload, no generation."""
import argparse
import json
from pathlib import Path

import cv2
import mediapipe as mp


def main():
    p = argparse.ArgumentParser(description="Extract face landmarks to a private folder")
    p.add_argument("--image", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("output"))
    args = p.parse_args()
    if not args.image.is_file():
        p.error("Image not found: " + str(args.image))
    args.out.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(args.image))
    if img is None:
        p.error("Could not read image")
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    with mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.5) as mesh:
        result = mesh.process(rgb)
    faces = result.multi_face_landmarks or []
    info = {
        "width": w, "height": h, "detected_faces": len(faces),
        "reference_role": "reference_02 / sole identity and body anchor",
        "normalized_face_landmarks": [
            {"x": round(a.x, 6), "y": round(a.y, 6), "z": round(a.z, 6)}
            for a in faces[0].landmark
        ] if faces else [],
        "caveat": "2D/relative 3D landmarks depend on angle and perspective; not an identity reconstruction.",
    }
    (args.out / "landmarks.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "ning_visual_profile.md").write_text(
        "# Ning Visual Profile — manual review required\\n\\n"
        "- Primary reference: original second laboratory photo only.\\n"
        "- Face geometry: REVIEW MANUALLY against the reference, do not infer exact metrics from mesh alone.\\n"
        "- Hair / expression / skin / silhouette / attire: complete from direct image review.\\n"
        "- Pose, camera perspective and lighting must not be confused with anatomy.\\n",
        encoding="utf-8",
    )
    (args.out / "ning_generation_prompt.md").write_text(
        "# ChatGPT generation prompt\\n\\n"
        "Use the original second laboratory photograph as the PRIMARY reference for the same adult woman's face and natural body proportions. "
        "Preserve facial identity and silhouette; change only the requested scene, pose, clothing and lighting. "
        "Do not blend identities from other images. Detailed written profile follows after manual review. "
        "Text alone does not guarantee exact likeness.\\n",
        encoding="utf-8",
    )
    print("Wrote files to", args.out.resolve(), "faces detected:", len(faces))


if __name__ == "__main__":
    main()
