# SPDX-License-Identifier: Apache-2.0
"""Build-time source/notice retention. Never fetch authentication artifacts."""
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import sys
import urllib.request


def retain(manifest, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        filename = source["filename"]
        if Path(filename).name != filename or not source["url"].startswith("https://"):
            raise ValueError("Unsafe source manifest")
        target = destination / filename
        digest = hashlib.sha256()
        with urllib.request.urlopen(source["url"], timeout=90) as response, target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != source["sha256"]:
            target.unlink()
            raise ValueError("Source archive checksum mismatch: " + source["name"])
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def inventory(destination):
    rows = []
    notices = destination / "python-notices"
    for package in sorted(distributions(), key=lambda p: p.metadata["Name"].lower()):
        name = package.metadata["Name"]
        rows.append({"name": name, "version": package.version,
                     "license_expression": package.metadata.get("License-Expression"),
                     "license": package.metadata.get("License")})
        for entry in package.files or ():
            # Preserve original wheel notice paths/text; do not relabel as Apache.
            path = str(entry)
            if ".dist-info/" in path and any(word in path.upper() for word in ("LICENSE", "NOTICE", "COPYING")):
                output = notices / name / path
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(package.locate_file(entry).read_bytes())
    (destination / "installed-python.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    source_manifest, output = map(Path, sys.argv[1:])
    retain(json.loads(source_manifest.read_text()), output)
    inventory(output)
