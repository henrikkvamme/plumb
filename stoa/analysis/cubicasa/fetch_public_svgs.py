# /// script
# requires-python = ">=3.11"
# dependencies = ["remotezip"]
# ///
"""Fetch only model.svg and the split lists from the public CubiCasa5K zip with HTTP range requests.

Source: Zenodo record 2613548, CC BY-NC-SA 4.0 (the GitHub repository says CC BY-NC 4.0).
Writes to stoa/data/external/cubicasa5k/svg/<group>/<id>/model.svg and .../splits/*.txt.
If the full zip is already on disk, it reads from that file instead.
"""
import pathlib
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from remotezip import RemoteZip

URL = "https://zenodo.org/api/records/2613548/files/cubicasa5k.zip/content"
ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = ROOT / "data/external/cubicasa5k"
LOCAL = DEST / "cubicasa5k.zip"


def wanted(name):
    return name.endswith("model.svg") or name.endswith(".txt")


def target(name):
    rel = name.split("/", 1)[1]
    if rel.endswith(".txt"):
        return DEST / "splits" / rel
    return DEST / "svg" / rel


def main():
    use_local = "--local" in sys.argv
    opener = (lambda: zipfile.ZipFile(LOCAL)) if use_local else (lambda: RemoteZip(URL))
    with opener() as z:
        names = [n for n in z.namelist() if wanted(n)]
    todo = [n for n in names if not target(n).exists()]
    print("members", len(names), "todo", len(todo))

    def work(chunk):
        with opener() as z:
            for n in chunk:
                t = target(n)
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(z.read(n))
        return len(chunk)

    chunks = [todo[i::24] for i in range(24)]
    with ThreadPoolExecutor(24) as ex:
        print("done", sum(ex.map(work, chunks)))


if __name__ == "__main__":
    main()
