"""Build sf_meta.json for chosen LVIS categories from the Objaverse metadata files on Hugging Face (official host)."""
import gzip, json, sys, urllib.request, concurrent.futures as cf, collections
lv = json.loads(gzip.decompress(open("lvis-annotations.json.gz", "rb").read()))
paths = json.loads(gzip.decompress(open("object-paths.json.gz", "rb").read()))
cats = sys.argv[1:]
want = collections.defaultdict(set)
for c in cats:
    for u in lv[c]: want[paths[u].split("/")[1]].add(u)
def grab(group):
    url = f"https://huggingface.co/datasets/allenai/objaverse/resolve/main/metadata/{group}.json.gz"
    for _ in range(3):
        try:
            d = json.loads(gzip.decompress(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RiseAboveVR-FYP/1.0"}), timeout=300).read()))
            return {u: d[u] for u in want[group] if u in d}
        except Exception:
            pass
    return {}
meta = {}
with cf.ThreadPoolExecutor(8) as ex:
    for part in ex.map(grab, sorted(want)): meta.update(part)
LIC = {"by": "CC Attribution", "by-sa": "CC Attribution-ShareAlike", "by-nd": "CC Attribution-NoDerivs", "by-nc": "CC Attribution-NonCommercial",
       "by-nc-sa": "CC Attribution-NonCommercial-ShareAlike", "by-nc-nd": "CC Attribution-NonCommercial-NoDerivs", "cc0": "CC0"}
out = {}
for c in cats:
    rows = []
    for u in lv[c]:
        d = meta.get(u)
        if not d: continue
        th = sorted((d.get("thumbnails") or {}).get("images", []), key=lambda t: -t.get("width", 0))
        rows.append({"uid": u, "name": d.get("name"), "license": LIC.get(d.get("license"), d.get("license")), "likes": d.get("likeCount", 0),
                     "views": d.get("viewCount", 0), "faces": d.get("faceCount"), "anims": d.get("animationCount", 0),
                     "user": (d.get("user") or {}).get("displayName"), "thumb": next((t["url"] for t in th if t.get("width", 0) <= 720), None)})
    out[c] = rows
    print(c, len(rows))
json.dump(out, open("sf_meta.json", "w"), indent=1)
