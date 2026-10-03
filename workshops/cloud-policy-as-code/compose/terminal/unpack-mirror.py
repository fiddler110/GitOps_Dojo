#!/usr/bin/env python3
"""Build-time: convert `tofu providers mirror` output (zip files) into the
UNPACKED filesystem-mirror layout: <host>/<ns>/<type>/<version>/<os_arch>/.

With an unpacked mirror `tofu init` SYMLINKS the provider into each student's
.terraform/ instead of copying it (azurerm is ~218 MB unpacked — copying it 30
times would be ~6.5 GB). Usage: unpack-mirror.py <packed-dir> <unpacked-dir>
"""
import glob
import os
import re
import sys
import zipfile

packed, unpacked = sys.argv[1], sys.argv[2]
pattern = re.compile(r"terraform-provider-(?P<type>[^_]+)_(?P<version>[^_]+)_(?P<platform>[a-z0-9]+_[a-z0-9]+)\.zip$")
count = 0
for zpath in glob.glob(f"{packed}/*/*/*/*.zip"):
    host, ns = zpath.split("/")[-4:-2]
    m = pattern.search(os.path.basename(zpath))
    if not m:
        sys.exit(f"unexpected mirror file name: {zpath}")
    dest = f"{unpacked}/{host}/{ns}/{m['type']}/{m['version']}/{m['platform']}"
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    for f in glob.glob(f"{dest}/terraform-provider-*"):
        os.chmod(f, 0o755)
    print("unpacked", dest)
    count += 1
if count == 0:
    sys.exit("no provider zips found in the mirror")
