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
## Argon batch (2026-10-19)
Gemini 4 Argon became available on the Google AI Pro plan in Antigravity, so `gen.sh` now defaults to
"Gemini 4 Argon (High)" (override with `MODEL="Gemini 3.8 Flash (High)" gen.sh ...`). All seven models were
generated in ONE parallel batch (7 jobs at once), reviewed together, and the weak ones got a second
parallel round: Kiwi (shorter legs), Mittens (flush stripes, no brows), pigeon (syntax retry).
Final models (all Argon): Kiwi, Mittens, Biscuit, Helicopter, Pip (separate flapping wings),
Pigeon (separate flapping wings), Pedestrian (recoloured per person in the game).
Final scripts: `scripts/*_rargon*.py`. Earlier Flash versions are kept for comparison.

## Realistic pass (2026-10-19/20)
Goal: replace cartoon art with realistic assets. Code-generated organic shapes (animals, people) never looked real,
so Gemini is used where it is strong - hard-surface objects with baked PBR textures - and real scans fill the rest
(see `../AssetPipeline/README.md`).
- `realistic/rules_bldg.txt`, `rules_car.txt`, `rules_prop.txt` - shared rules (bake albedo + normal at 2048, one material).
- `realistic/briefs/` - per-object briefs plus `fb_*.txt` art-direction feedback rounds.
- `realistic/scripts/` - approved scripts: 4 city buildings, 4 cars, the shipping container, the site cabin and the
  camera drone that is now Pip. Small mechanical fixes were applied where Argon slipped (e.g. `Matrix.Euler` ->
  `Euler(...).to_matrix()`, a miswired node link, a stray space in a variable name).
- Long scripts (2000+ lines) can hit the CLI print timeout and come back truncated - ask for "under 1200 lines".
