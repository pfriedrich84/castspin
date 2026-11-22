# SPDX-License-Identifier: Apache-2.0
"""Static artifact/source coverage, not proof that a container was built."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_source_manifest_covers_locked_python_and_native_artifacts(self):
        manifest = json.loads((ROOT / "castspin/sources.json").read_text())
        sources = {row["name"].lower().replace("_", "-"): row for row in manifest["sources"]}
        for lock in ("requirements.txt", "build-requirements.txt"):
            text = (ROOT / "castspin" / lock).read_text()
            for name, version in re.findall(r"^([\w-]+)==([^\s]+)", text, re.MULTILINE):
                self.assertEqual(sources[name.lower().replace("_", "-")]["version"], version)
        self.assertIn("cast-audio-receiver-lab", sources)
        self.assertIn("vibecast-vendored-source", sources)
        self.assertIn(manifest["receiver_image"], (ROOT / "castspin/Dockerfile").read_text())
        for row in sources.values():
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(row["url"].startswith("https://"))
            self.assertEqual(Path(row["filename"]).name, row["filename"])

    def test_base_and_ha_build_configuration_use_same_pinned_debian_index(self):
        dockerfile = (ROOT / "castspin/Dockerfile").read_text()
        base = re.search(r"ARG BUILD_FROM=(\S+)", dockerfile).group(1)
        self.assertIn("base-debian:trixie-", base)
        self.assertIn("@sha256:", base)
        self.assertEqual((ROOT / "castspin/build.yaml").read_text().count(base), 2)


if __name__ == "__main__":
    unittest.main()
