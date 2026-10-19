"""Download Objaverse GLBs (official Hugging Face dataset host) into quarantine; verify the glTF signature; record licence info."""
import gzip, json, os, sys, urllib.request
paths = json.loads(gzip.decompress(open("object-paths.json.gz", "rb").read()))
rows = json.load(open(sys.argv[1]))
os.makedirs("glb", exist_ok=True)
lic = json.load(open("licenses.json")) if os.path.exists("licenses.json") else {}
for idx in sys.argv[2:]:
    r = rows[int(idx)]
    url = "https://huggingface.co/datasets/allenai/objaverse/resolve/main/" + paths[r["uid"]]
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RiseAboveVR-FYP/1.0"}), timeout=300).read()
    if data[:4] != b"glTF": raise ValueError("not a GLB: " + url)
    out = os.path.join("glb", r["uid"] + ".glb")
    open(out, "wb").write(data)
    lic[r["uid"]] = {"name": r["name"], "author": r["user"], "license": r["license"], "source": "https://sketchfab.com/3d-models/" + r["uid"], "via": url}
    print("OK", idx, r["uid"], len(data), r["license"], r["name"].encode("ascii", "replace").decode())
json.dump(lic, open("licenses.json", "w"), indent=1)
