import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class TestPhase1Integration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "revised_ed").mkdir()
        (self.tmpdir / "data" / "vnext" / "iiif" / "manifests").mkdir(parents=True)

        shutil.copytree(ROOT / "tests/fixtures/revised_ed", self.tmpdir / "revised_ed", dirs_exist_ok=True)
        shutil.copytree(ROOT / "tests/fixtures/vnext", self.tmpdir / "data" / "vnext", dirs_exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_script(self, script: str, args):
        cmd = [sys.executable, str(ROOT / "scripts" / script)] + args
        subprocess.check_call(cmd)

    def test_end_to_end_build(self):
        vnext_dir = self.tmpdir / "data" / "vnext"
        manifest_dir = vnext_dir / "iiif" / "manifests"

        self.run_script(
            "vnext_build_citations.py",
            ["--revised-ed-dir", str(self.tmpdir / "revised_ed"), "--out-dir", str(vnext_dir)],
        )
        self.run_script(
            "vnext_build_citation_iiif_map.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir), "--manifest-dir", str(manifest_dir)],
        )
        self.run_script(
            "vnext_validate_phase1.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir)],
        )

        expected_dir = ROOT / "tests/fixtures/expected/vnext"
        for name in [
            "citations.csv",
            "citation_iiif_map.csv",
            "needs_review_missing_manifest.csv",
            "needs_review_missing_iiif.csv",
            "needs_review_ambiguous_iiif.csv",
            "needs_review_bad_rows.csv",
            "validation_report.md",
        ]:
            with self.subTest(name=name):
                actual = (vnext_dir / name).read_bytes()
                expected = (expected_dir / name).read_bytes()
                self.assertEqual(actual, expected)

    def test_determinism(self):
        vnext_dir = self.tmpdir / "data" / "vnext"
        manifest_dir = vnext_dir / "iiif" / "manifests"

        self.run_script(
            "vnext_build_citations.py",
            ["--revised-ed-dir", str(self.tmpdir / "revised_ed"), "--out-dir", str(vnext_dir)],
        )
        self.run_script(
            "vnext_build_citation_iiif_map.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir), "--manifest-dir", str(manifest_dir)],
        )
        self.run_script(
            "vnext_validate_phase1.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir)],
        )

        hashes_first = {
            name: file_hash(vnext_dir / name)
            for name in [
                "citations.csv",
                "citation_iiif_map.csv",
                "validation_report.md",
            ]
        }

        # Run again and compare
        self.run_script(
            "vnext_build_citations.py",
            ["--revised-ed-dir", str(self.tmpdir / "revised_ed"), "--out-dir", str(vnext_dir)],
        )
        self.run_script(
            "vnext_build_citation_iiif_map.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir), "--manifest-dir", str(manifest_dir)],
        )
        self.run_script(
            "vnext_validate_phase1.py",
            ["--in-dir", str(vnext_dir), "--out-dir", str(vnext_dir)],
        )

        hashes_second = {
            name: file_hash(vnext_dir / name)
            for name in hashes_first
        }
        self.assertEqual(hashes_first, hashes_second)


if __name__ == "__main__":
    unittest.main()
