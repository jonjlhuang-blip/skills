---
name: ning-visual-identity
description: Extract private CPU face geometry from reference photos and turn directly reviewed visual observations into a complete identity description, structured JSON, and ChatGPT image prompts. Use for Ning or other user-designated character references, multiple-image primary/auxiliary selection, and comparison of descriptions with source photos. Keep photos and personal outputs out of public Git repositories.
---

# Visual identity from private references

Read `README.md` for environment setup and CLI commands. Install `requirements.txt` in a dedicated Python 3.11 or 3.12 environment. Use CPU; do not install optional VLMs or download training weights for this workflow.

1. Inspect every input image directly. Select the user's primary reference explicitly. For Ning's laboratory reference set, use the original second laboratory photograph as the sole face and body anchor. Use auxiliary images to compare styling, poses and lighting; do not blend faces.
2. Keep originals outside the Git checkout. Run `extract.py` with repeated `--image`, `--primary-index` and a private `--out` folder. Image order defines `reference_01`, `reference_02`, etc. Single-image calls default to the first input and do not imply that it is the original second photo.
3. Read `profile_draft.json`; fill every feature and scene from direct visual inspection. Follow `profile.schema.json`. Record evidence IDs, qualitative confidence and limitations. Attribute identity features only to the selected primary image. Describe visible appearance without inferring ethnicity, actual age, real identity, height, weight or body measurements.
4. Describe face outline, eyes, brows, nose, mouth, hair, skin and visible silhouette. Separate those features from per-image pose, expression, attire, light, framing and scene. Account for foreshortening, rotation, occlusion, makeup and fitted clothing when comparing photographs.
5. Run again with `--profile` pointing to the reviewed JSON. Preserve that input as `reviewed_profile.json` in a private folder, not as the generated draft filename in the same output folder. Reject no-face or multiple-face inputs and profile/reference mismatches. Never deliver an unreviewed draft as a complete profile.
6. Read all generated text and compare it against the original primary photograph. Check that scene details have not become identity constraints. Revise the reviewed input and rerun if necessary. Describe remaining losses; do not invent a likeness percentage or claim a generated-image comparison when no image was generated.
7. Deliver `ning_visual_profile.md`, `ning_visual_identity.json`, `ning_generation_prompt.md`, `review_report.md` and, if useful, private `landmarks.json`. Label CPU measurements separately from manually reviewed observations. Explain that text alone cannot retain precise facial identity; attach the primary reference when available.

Do not upload reference photos, crops, landmarks, reviewed personal profiles, embeddings or weights to GitHub. Commit only generic code, schema, instructions and synthetic regression tests. Use a file allowlist when staging. Do not treat this workflow as biometric identity verification or model-weight distillation.
