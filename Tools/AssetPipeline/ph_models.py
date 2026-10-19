"""Download CC0 Poly Haven models (FBX 1k + JPG diffuse/normal) from the official API into a quarantine folder,
verify MD5 + file signatures, then copy verified files into the Unity project. Usage: python -I ph_models.py id1 id2 ..."""
import hashlib, json, os, shutil, sys, urllib.request

QUAR = r"E:\Unity_project\_downloads\polyhaven_models"
DEST = r"E:\Unity_project\RiseAboveVR\Assets\AcrophobiaVR\ThirdParty\PolyHaven\Models"
HOSTS = ("https://api.polyhaven.com/", "https://dl.polyhaven.org/")
UA = {"User-Agent": "RiseAboveVR-FYP/1.0"}
MAGIC = {".fbx": b"Kaydara FBX Binary", ".jpg": b"\xff\xd8\xff"}


def get(url):
    if not url.startswith(HOSTS):
        raise ValueError("refusing non-Poly-Haven URL: " + url)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def fetch(url, md5, path):
    data = get(url)
    if md5 and hashlib.md5(data).hexdigest() != md5:
        raise ValueError("MD5 mismatch for " + url)
    ext = os.path.splitext(path)[1].lower()
    if ext in MAGIC and not data.startswith(MAGIC[ext]):
        raise ValueError("bad file signature for " + path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main(ids):
    manifest = {}
    for aid in ids:
        files = json.loads(get("https://api.polyhaven.com/files/" + aid))
        fbx = files["fbx"]["1k"]["fbx"]
        q = os.path.join(QUAR, aid)
        got = {"fbx": fetch(fbx["url"], fbx["md5"], os.path.join(q, aid + ".fbx"))}
        for key, name in (("Diffuse", "diff"), ("nor_gl", "nor_gl")):
            m = files.get(key, {}).get("1k", {}).get("jpg")
            if m:
                got[name] = fetch(m["url"], m["md5"], os.path.join(q, aid + "_" + name + ".jpg"))
        d = os.path.join(DEST, aid)
        os.makedirs(d, exist_ok=True)
        for fn in os.listdir(q):
            shutil.copy2(os.path.join(q, fn), os.path.join(d, fn))
        manifest[aid] = got
        print("OK", aid, got)
    mp = os.path.join(DEST, "manifest_models.json")
    old = json.load(open(mp)) if os.path.exists(mp) else {"source": "https://polyhaven.com (CC0)", "assets": {}}
    old["assets"].update(manifest)
    with open(mp, "w") as f:
        json.dump(old, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
