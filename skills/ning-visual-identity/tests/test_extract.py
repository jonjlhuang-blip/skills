"""Synthetic regressions only. Never put personal photos or profiles in this tree."""
import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract


def reviewed_profile():
    profile = extract.make_draft(["reference_01", "reference_02"], "reference_02")
    profile["subject"]["name"] = "Synthetic adult character"
    for feature in profile["identity_features"].values():
        feature["description"] = "Synthetic observed feature for schema testing."
        feature["limitations"] = ["Synthetic limitation."]
    for ref in profile["reference_observations"]:
        for key in ("pose", "expression", "clothing", "lighting", "framing", "scene"):
            ref[key] = "Synthetic scene observation."
    profile["generation"]["target_scene"] = "Synthetic studio scene."
    return profile


def geometry(reference_id, role, count=1):
    return {"reference_id": reference_id, "reference_role": role, "width": 200, "height": 100,
            "detected_faces": count, "face_detection_cap": 2, "detection_status": "one_face",
            "normalized_face_landmarks": [{"x": 0.5, "y": 0.5, "z": 0.0}] * 468,
            "projected_metrics": {}, "caveat": extract.MESH_CAVEAT}


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.profile_path = self.root / "reviewed.json"
        self.profile_path.write_text(json.dumps(reviewed_profile()), encoding="utf-8")
    def tearDown(self):
        self.temp.cleanup()
    def load(self, profile, primary="reference_02"):
        self.profile_path.write_text(json.dumps(profile), encoding="utf-8")
        return extract.load_profile(self.profile_path, ["reference_01", "reference_02"], primary)
    def invoke(self, arguments):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return extract.main(arguments)
    def blank(self, name="input.png"):
        path = self.root / name
        Image.new("RGB", (64, 64), "white").save(path)
        return path

    def test_unicode_path_and_exif_rotation(self):
        path = self.root / "私密参考.jpeg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (30, 20), "red").save(path, exif=exif)
        rgb = extract.load_rgb(path)
        self.assertEqual(rgb.shape, (30, 20, 3))
        self.assertGreater(int(rgb[0, 0, 0]), 200)

    def test_transparency_composites_on_white(self):
        path = self.root / "transparent.png"
        Image.new("RGBA", (20, 30), (0, 0, 0, 0)).save(path)
        self.assertTrue((extract.load_rgb(path) == 255).all())

    def test_corrupt_input_does_not_create_output(self):
        path = self.root / "broken.jpg"
        path.write_bytes(b"not an image")
        out = self.root / "result"
        with self.assertRaises(SystemExit) as exc:
            self.invoke(["--image", str(path), "--out", str(out)])
        self.assertEqual(exc.exception.code, 2)
        self.assertFalse(out.exists())

    def test_valid_profile_and_primary_mismatch(self):
        self.assertEqual(self.load(reviewed_profile())["reference_policy"]["primary_id"], "reference_02")
        with self.assertRaisesRegex(ValueError, "primary_id"):
            self.load(reviewed_profile(), primary="reference_01")

    def test_empty_or_whitespace_feature_is_rejected(self):
        for description in ("", " \n "):
            profile = reviewed_profile()
            profile["identity_features"]["eyes"]["description"] = description
            with self.assertRaisesRegex(ValueError, "schema violation"):
                self.load(profile)

    def test_auxiliary_identity_evidence_is_rejected(self):
        profile = reviewed_profile()
        profile["identity_features"]["eyes"]["evidence"] = ["reference_01", "reference_02"]
        with self.assertRaisesRegex(ValueError, "only the primary"):
            self.load(profile)

    def test_duplicate_missing_or_wrong_role_references_are_rejected(self):
        for mutation in ("duplicate", "missing", "role"):
            profile = reviewed_profile()
            if mutation == "duplicate":
                profile["reference_observations"][0] = copy.deepcopy(profile["reference_observations"][1])
            elif mutation == "missing":
                profile["reference_observations"].pop()
            else:
                profile["reference_observations"][0]["role"] = "primary"
            with self.assertRaises(ValueError):
                self.load(profile)

    def test_projected_ratio_uses_pixel_dimensions(self):
        points = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(468)]
        points[234]["x"], points[454]["x"] = 0.1, 0.9
        points[10]["y"], points[152]["y"] = 0.1, 0.9
        points[33]["x"] = points[133]["x"] = 0.3
        points[263]["x"] = points[362]["x"] = 0.7
        result = extract.projected_metrics(points, 200, 100)
        self.assertEqual(result["face_width_to_height_projected"], 2.0)
        self.assertEqual(result["eye_center_distance_to_face_width_projected"], 0.5)
        self.assertEqual(result["eye_axis_tilt_degrees_in_image"], 0.0)

    def test_complete_cli_and_primary_landmarks_compatibility(self):
        inputs = [self.blank("one.png"), self.blank("two.png")]
        out = self.root / "result"
        def fake_geometry(rgb, ref_id, role):
            item = geometry(ref_id, role)
            item["width"] = 200 if role == "primary" else 100
            return item
        with patch.object(extract, "extract_geometry", side_effect=fake_geometry):
            self.invoke(["--image", str(inputs[0]), "--image", str(inputs[1]), "--primary-index", "2", "--profile", str(self.profile_path), "--out", str(out)])
        identity = json.loads((out / "ning_visual_identity.json").read_text())
        mesh = json.loads((out / "landmarks.json").read_text())
        self.assertEqual(identity["review_status"], "complete")
        self.assertEqual(mesh["width"], 200)
        self.assertEqual(mesh["reference_role"], "primary")
        self.assertEqual(len(mesh["references"]), 2)
        self.assertFalse((out / "profile_draft.json").exists())
        for name in ("ning_visual_profile.md", "ning_generation_prompt.md", "review_report.md"):
            text = (out / name).read_text()
            self.assertIn("\n\n", text)
            self.assertNotIn("\\n", text)
        self.assertIn("仅文字版本", (out / "ning_generation_prompt.md").read_text())

    def test_unreviewed_cli_explicitly_marks_pending(self):
        path, out = self.blank(), self.root / "result"
        with patch.object(extract, "extract_geometry", return_value=geometry("reference_01", "primary")):
            self.invoke(["--image", str(path), "--out", str(out)])
        identity = json.loads((out / "ning_visual_identity.json").read_text())
        self.assertEqual(identity["review_status"], "pending_visual_review")
        self.assertIsNone(identity["reviewed_profile"])
        draft = json.loads((out / "profile_draft.json").read_text())
        self.assertEqual(draft["reference_policy"]["primary_id"], "reference_01")

    def test_no_face_real_cpu_detector(self):
        # Actual MediaPipe inference on a synthetic blank image, with no mocks.
        result = extract.extract_geometry(np.full((256, 256, 3), 255, dtype=np.uint8), "reference_01", "primary")
        self.assertEqual(result["detected_faces"], 0)
        self.assertEqual(result["normalized_face_landmarks"], [])

    def test_no_face_or_ambiguous_face_cli_fails_before_writing(self):
        path, out = self.blank(), self.root / "result"
        for count in (0, 2):
            with patch.object(extract, "extract_geometry", return_value=geometry("reference_01", "primary", count)):
                with self.assertRaises(SystemExit) as exc:
                    self.invoke(["--image", str(path), "--out", str(out)])
            self.assertEqual(exc.exception.code, 2)
            self.assertFalse(out.exists())

    def test_output_cannot_overwrite_input_profile(self):
        path, out = self.blank(), self.root / "result"
        out.mkdir()
        draft = out / "profile_draft.json"
        draft.write_text("keep me")
        with self.assertRaises(SystemExit) as exc:
            self.invoke(["--image", str(path), "--profile", str(draft), "--out", str(out)])
        self.assertEqual(exc.exception.code, 2)
        self.assertEqual(draft.read_text(), "keep me")

    def test_git_output_privacy_ignored_unignored_and_tracked(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text("output/\n")
        extract.private_output_guard(repo / "output")
        with self.assertRaisesRegex(ValueError, "tracked by Git"):
            extract.private_output_guard(repo / "public")
        (repo / "output").mkdir()
        (repo / "output" / "landmarks.json").write_text("{}")
        subprocess.run(["git", "-C", str(repo), "add", "-f", "output/landmarks.json"], check=True)
        with self.assertRaisesRegex(ValueError, "tracked by Git"):
            extract.private_output_guard(repo / "output")

    def test_placeholder_git_directory_is_not_a_checkout(self):
        (self.root / ".git").mkdir()
        extract.private_output_guard(self.root / "result")

    def test_output_symlink_is_rejected(self):
        out = self.root / "result"
        out.mkdir()
        (out / "landmarks.json").symlink_to(self.profile_path)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            extract.private_output_guard(out)


if __name__ == "__main__":
    unittest.main()
