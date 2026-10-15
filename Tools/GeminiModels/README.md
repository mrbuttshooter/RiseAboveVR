# Gemini-made 3D models

The creature and vehicle models in `Assets/AcrophobiaVR/Models/` (Kiwi the parrot, Biscuit the dog,
Mittens the cat, the news helicopter) were modelled by **Gemini 3.8 Flash (High)** through Google's
Antigravity CLI (`agy`, Google AI Pro plan). Gemini writes a Blender Python script; Blender 5.2 builds,
renders and exports it as FBX; Unity imports it.

Loop: brief -> Gemini script -> safety check -> Blender build + preview render -> art-direction notes ->
Gemini improves its own script -> repeat until approved (Kiwi took 3 rounds, the dog 2).

- `gen.sh <name> <round> <prompt-file>` - one round (needs agy signed in, and Blender 5.2).
- `rules.txt` - shared rules (connected parts, Quest triangle budget, export axes, preview render).
- `brief_*.txt` - per-model briefs; `prompt_*_r2/r3.txt` - the art-direction feedback rounds.
- `scripts/` - the final approved Gemini scripts (re-run with Blender:
  `blender -b --factory-startup -P scripts/kiwi_r3.py -- C:/out/Kiwi.fbx`).

Generated scripts are refused if they reference networking, subprocesses or file deletion.
Gemini 4 Argon (stronger at 3D) is Ultra-plan only, so it was not used.
