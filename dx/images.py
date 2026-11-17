"""Download film stills and speaker photos from the festival website, resized, into public/img/{f,p}/.
Writes data/images.json ({"f:<film id>": "img/f/<id>.jpg", "p:<person id>": ...}). Re-runs skip files already there.

    python3 -m dx.images
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUB = ROOT / "public"
TMP = ROOT / "raw" / "imgcache"


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (archive explorer)"})
        data = urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:
        print("fail", url, e)
        return False
    dest.write_bytes(data)
    time.sleep(0.4)
    return True


def resize(src, dest, width):
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "--resampleWidth", str(width),
                        str(src), "--out", str(dest)], capture_output=True)
    return r.returncode == 0 and dest.exists()


def main():
    d = json.load(open(DATA / "festival.json"))
    TMP.mkdir(parents=True, exist_ok=True)
    out = {}
    jobs = [("f", fid, f["image"], 480) for fid, f in d["films"].items() if f.get("image")]
    jobs += [("p", pid, p["photo"], 200) for pid, p in d["people"].items() if p.get("photo")]
    for kind, id_, url, w in jobs:
        ext = url.rsplit(".", 1)[-1].split("?")[0].lower()[:4]
        raw = TMP / f"{kind}-{id_}.{ext}"
        dest = PUB / "img" / kind / f"{id_}.jpg"
        if fetch(url, raw) and resize(raw, dest, w):
            out[f"{kind}:{id_}"] = f"img/{kind}/{id_}.jpg"
    # Films with no web still: the largest picture on the film's catalogue page.
    # (2023 is skipped: its PDF pages are two-page spreads, so the largest picture may belong to the next film.)
    for fid, f in d["films"].items():
        if f"f:{fid}" in out:
            continue
        sc = next((s for s in f["screenings"] if s.get("page") and s["year"] not in (2023,)), None)
        if not sc:
            continue
        dest = PUB / "img" / "f" / f"{fid}.jpg"
        if not dest.exists():
            pdf = ROOT / "raw" / "pdf" / f"{sc['year']}.pdf"
            work = TMP / f"pdf-{fid}"
            work.mkdir(exist_ok=True)
            subprocess.run(["pdfimages", "-f", str(sc["page"]), "-l", str(sc["page"]), "-png", str(pdf), str(work / "i")],
                           capture_output=True)
            imgs = sorted(work.glob("i-*.png"), key=lambda p: p.stat().st_size, reverse=True)
            if not imgs or imgs[0].stat().st_size < 30000:
                continue
            w = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(imgs[0])], capture_output=True, text=True).stdout
            nums = [int(x) for x in __import__("re").findall(r"pixel\w+: (\d+)", w)]
            if len(nums) == 2 and (nums[0] < 300 or nums[0] < nums[1] * 0.9):
                continue  # small or portrait: probably a headshot or poster, not a still
            resize(imgs[0], dest, 480)
        if dest.exists():
            out[f"f:{fid}"] = f"img/f/{fid}.jpg"
    # The same picture on several films (shorts that share a catalogue page, placeholder art): keep it for none.
    import hashlib
    from collections import defaultdict
    groups = defaultdict(list)
    for k, v in out.items():
        if k.startswith("f:"):
            groups[hashlib.md5((PUB / v).read_bytes()).hexdigest()].append(k)
    for ks in groups.values():
        if len(ks) > 1:
            for k in ks:
                (PUB / out.pop(k)).unlink(missing_ok=True)
    for k in [l.strip() for l in (DATA / "bad_images.txt").read_text().splitlines()
              if l.strip() and not l.startswith("#")] if (DATA / "bad_images.txt").exists() else []:
        if k in out:
            (PUB / out.pop(k)).unlink(missing_ok=True)
    json.dump(out, open(DATA / "images.json", "w"), indent=0, sort_keys=True)
    print(len(out), "images of", len(jobs))


if __name__ == "__main__":
    main()
