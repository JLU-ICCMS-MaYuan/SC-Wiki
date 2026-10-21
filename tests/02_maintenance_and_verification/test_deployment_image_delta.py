"""真实 VCDIFF 编解码及错误基准/损坏包的拒绝保护。"""
import gzip
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from scripts.deployment_image_delta import create, digest, restore


@unittest.skipUnless(shutil.which("xdelta3"), "需要系统 xdelta3 验证真实编解码")
class DeploymentImageDeltaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base, self.target = self.root / "base", self.root / "target"
        shared = random.Random(146).randbytes(512 * 1024)
        self.expected = b"target header" + shared + b"new tail"
        self.commit = "1" * 40
        for folder, data in ((self.base, b"old header" + shared + b"old tail"), (self.target, self.expected)):
            folder.mkdir()
            (folder / "image.tar.gz").write_bytes(gzip.compress(data))
            (folder / "source.json").write_text(json.dumps({
                "Digest": "sha256:" + "a" * 64,
                "config": {"architecture": "amd64", "os": "linux",
                           "config": {"Labels": {"org.opencontainers.image.revision": self.commit}}},
            }))
            (folder / "checksums.sha256").write_text("".join(
                digest(folder / name) + "  " + name + "\n" for name in ("image.tar.gz", "source.json")))
        self.package = self.root / "delta"
        create(self.base, self.target, self.package, self.commit)

    def test_real_roundtrip_is_byte_exact(self):
        restored = self.root / "restored.tar"
        restore(self.base / "image.tar.gz", self.package, restored)
        self.assertEqual(restored.read_bytes(), self.expected)

    def test_corrupted_delta_is_rejected_before_creating_output(self):
        with (self.package / "image.vcdiff").open("ab") as out:
            out.write(b"tampered")
        restored = self.root / "restored.tar"
        with self.assertRaises(ValueError):
            restore(self.base / "image.tar.gz", self.package, restored)
        self.assertFalse(restored.exists())

    def test_wrong_base_is_rejected(self):
        wrong = self.root / "wrong.tar.gz"
        wrong.write_bytes(gzip.compress(b"different base"))
        with self.assertRaises(ValueError):
            restore(wrong, self.package, self.root / "restored.tar")

    def test_existing_output_is_preserved(self):
        restored = self.root / "restored.tar"
        restored.write_bytes(b"must keep")
        with self.assertRaises(ValueError):
            restore(self.base / "image.tar.gz", self.package, restored)
        self.assertEqual(restored.read_bytes(), b"must keep")


if __name__ == "__main__":
    unittest.main()
