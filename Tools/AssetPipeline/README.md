# Realistic asset pipeline

Everything here is downloaded only from official hosts, checked (MD5 / file signature) in a quarantine folder,
scanned with Windows Defender, then copied into the project. Licences are recorded next to the assets.

| Source | What | Licence | Scripts |
|---|---|---|---|
| Poly Haven (api.polyhaven.com) | photo-scanned props, PBR textures, HDRI skies, 2k facade detail | CC0 | `ph_models.py`, `ph_include.py`, `ph_tex.py` |
| MakeHuman / MPFB 2 (Blender extension) | the 10 realistic pedestrians | CC0 | `make_human.py` |
| Objaverse (huggingface.co/datasets/allenai/objaverse, from Sketchfab) | realistic cat, dog, parrot, pigeon, SUV, traffic light, patio umbrella | CC-BY (credited in `Models/*/CREDITS.txt`) | `ov_meta.py`, `sf_sheet.py`, `ov_get.py` |
| Gemini 4 Argon (Antigravity CLI) | buildings, cars, container, site cabin, drone | made for this project | `../GeminiModels/` |

Objaverse flow: `ov_meta.py <lvis categories>` builds a candidate list from the dataset metadata ->
`sf_sheet.py` makes a thumbnail contact sheet (permissive licences only) -> `ov_get.py` downloads the chosen GLBs ->
`render_glb.py` renders a Blender preview -> `glb2fbx.py in.glb out_dir Name yaw decimate height` converts to FBX
plus `Textures/<Name>_<m>_albedo.png` (images rewired straight into the BSDF so FBX keeps them, unlit materials
rebuilt as Principled, optional decimation and height normalisation).

In Unity, `Editor/ModelTextureImporter.cs` binds each model's textures from the `Textures` folder next to the FBX,
and `BuildKit.PolyProp` handles Poly Haven variants (`_LODn`, `_aged`/`_rusted` twins, `_a.._d` alternatives,
glass / bulb slots, separate opacity maps merged into cutout textures).
