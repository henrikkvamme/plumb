# /// script
# requires-python = ">=3.11"
# dependencies = ["remotezip"]
# ///
"""List the public CubiCasa5K zip (Zenodo 2613548, CC BY-NC-SA 4.0) with HTTP range requests.

Writes out/public_zip_listing.json: every member name and size. No full download needed.
"""
import json
import pathlib
from remotezip import RemoteZip

URL = "https://zenodo.org/api/records/2613548/files/cubicasa5k.zip/content"
OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

with RemoteZip(URL) as z:
    infos = [{"name": i.filename, "size": i.file_size, "csize": i.compress_size} for i in z.infolist()]
json.dump(infos, open(OUT / "public_zip_listing.json", "w"))
print(len(infos))
