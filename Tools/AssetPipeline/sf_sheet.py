"""Contact sheet of Sketchfab thumbnails for the top-liked candidates of some categories (permissive licences only)."""
import json, sys, io, os, urllib.request
from PIL import Image, ImageDraw
m = json.load(open("sf_meta.json"))
cats, n, outp = sys.argv[1].split(","), int(sys.argv[2]), sys.argv[3]
skip = ("toon", "lego", "minecraft", "voxel", "kart", "toy", "hot wheels", "cartoon", "low poly", "low-poly", "lowpoly", "cute", "anime", "chibi", "kitty", "figure", "furby", "hello", "tom ", "yuumi", "ranma", "jelly", "spooky", "mae ", "mew", "donut")
rows, seen = [], set()
for c in cats:
    for r in m.get(c, []):
        if r["uid"] in seen or not r.get("thumb"): continue
        seen.add(r["uid"])
        lic = r.get("license") or ""
        if "NonCommercial" in lic or "NoDerivs" in lic: continue
        if any(k in (r["name"] or "").lower() for k in skip): continue
        rows.append(r)
rows.sort(key=lambda r: -(r["likes"] or 0))
rows = rows[:n]
W = 6; sheet = Image.new("RGB", (W * 256, ((len(rows) + W - 1) // W) * 276), "white")
d = ImageDraw.Draw(sheet)
for i, r in enumerate(rows):
    url = r["thumb"]
    assert url.startswith("https://media.sketchfab.com/")
    try:
        im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RiseAboveVR-FYP/1.0"}), timeout=30).read())).convert("RGB")
        im.thumbnail((256, 256)); sheet.paste(im, ((i % W) * 256, (i // W) * 276))
    except Exception as e:
        pass
    d.text(((i % W) * 256 + 2, (i // W) * 276 + 258), f"{i}: {r['faces']}f a{r['anims']} {r['likes']}L", fill="black")
sheet.save(outp)
json.dump(rows, open(outp + ".json", "w"), indent=1)
