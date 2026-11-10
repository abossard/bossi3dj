---
name: colossus-gpu-alone
description: Godot Colossus fps measurements are skewed by the user's live Blender on the same GPU; the show runs Godot alone
metadata:
  type: project
---

The show runs the Godot Colossus Scene alone on the GPU (user answer, 2026-11-06). The user's live Blender (synthwave planet) alone holds 52 to 65 % GPU Device Utilization, so windowed Godot fps and startup numbers measured beside it are context, not a verdict.

**Why:** the 2026-11-06 windowed-fps blueprint traced every fps drop to total GPU load at 94 to 100 %, not to a Godot setting.

**How to apply:** workers must never pause or close Blender. Hand Blender-free windowed measurements (C1 fps, C3 windowed smoke) to the user, and don't propose SDFGI or quality cuts based on runs beside Blender.
