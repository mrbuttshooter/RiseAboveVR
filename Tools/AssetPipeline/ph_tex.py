"""Download CC0 Poly Haven texture maps (2k JPG) via the official API into quarantine; verify MD5 + JPEG signature; copy to DEST."""
import hashlib, json, os, shutil, sys, urllib.request
QUAR = r"E:\Unity_project\_downloads\polyhaven_textures"
DEST = r"E:\Unity_project\RiseAboveVR\Assets\AcrophobiaVR\ThirdParty\PolyHaven\FacadeSource"
UA = {"User-Agent": "RiseAboveVR-FYP/1.0"}
def get(u):
    if not u.startswith(("https://api.polyhaven.com/", "https://dl.polyhaven.org/")): raise ValueError("refusing " + u)
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120) as r: return r.read()
res = sys.argv[1]
man = {}
for aid in sys.argv[2:]:
    files = json.loads(get("https://api.polyhaven.com/files/" + aid))
    for key, short in (("Diffuse", "diff"), ("nor_gl", "nor_gl"), ("Rough", "rough"), ("Displacement", "disp")):
        m = files.get(key, {}).get(res, {}).get("jpg") or files.get(key, {}).get(res, {}).get("png")
        if not m: print("missing", aid, key); continue
        data = get(m["url"])
        if hashlib.md5(data).hexdigest() != m["md5"]: raise ValueError("MD5 mismatch " + m["url"])
        ext = ".jpg" if data.startswith(b"\xff\xd8\xff") else ".png" if data.startswith(b"\x89PNG") else None
        if ext is None: raise ValueError("bad signature " + m["url"])
        name = f"{aid}_{short}{ext}"
        q = os.path.join(QUAR, name); os.makedirs(QUAR, exist_ok=True); open(q, "wb").write(data)
        os.makedirs(DEST, exist_ok=True); shutil.copy2(q, os.path.join(DEST, name))
        man[name] = {"url": m["url"], "md5": m["md5"], "bytes": len(data)}
        print("OK", name, len(data))
old = {}
mp = os.path.join(DEST, "manifest.json")
if os.path.exists(mp): old = json.load(open(mp))
old.update(man)
json.dump(old, open(mp, "w"), indent=1)
