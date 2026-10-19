"""Download the texture files an official Poly Haven FBX 'include' list references (quarantine, MD5, PNG signature)."""
import hashlib, json, os, shutil, sys, urllib.request
QUAR = r"E:\Unity_project\_downloads\polyhaven_models"
DEST = r"E:\Unity_project\RiseAboveVR\Assets\AcrophobiaVR\ThirdParty\PolyHaven\Models"
HOSTS = ("https://api.polyhaven.com/", "https://dl.polyhaven.org/")
UA = {"User-Agent": "RiseAboveVR-FYP/1.0"}
def get(url):
    if not url.startswith(HOSTS): raise ValueError("refusing " + url)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: return r.read()
for aid in sys.argv[1:]:
    files = json.loads(get("https://api.polyhaven.com/files/" + aid))
    inc = files["fbx"]["1k"]["fbx"].get("include", {})
    for rel, m in inc.items():
        data = get(m["url"])
        if hashlib.md5(data).hexdigest() != m["md5"]: raise ValueError("MD5 mismatch " + rel)
        name = os.path.basename(rel).replace("_1k", "")
        if not (data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8\xff")): raise ValueError("bad signature " + rel)
        q = os.path.join(QUAR, aid, name); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, "wb").write(data)
        shutil.copy2(q, os.path.join(DEST, aid, name))
        print("OK", aid, name, len(data))
