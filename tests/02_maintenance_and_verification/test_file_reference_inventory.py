"""迁移预检必须发现漏登记、缺失和越界文件。"""

from pathlib import Path

import pytest

from backend.storage.reference_inventory import FileInventoryError, scan_registered_files


def test_inventory_requires_every_persistent_file(tmp_path: Path) -> None:
    evidence = tmp_path / "manual_evidence" / "row" / "item"
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(b"source evidence")
    records = scan_registered_files(tmp_path, {"manual_evidence/row/item"})
    assert len(records) == 1
    assert records[0].size == len(b"source evidence")
    (evidence.parent / ".DS_Store").write_bytes(b"macOS metadata")
    (evidence.parent / "._item").write_bytes(b"resource fork")
    assert len(scan_registered_files(tmp_path, {"manual_evidence/row/item"})) == 1
    with pytest.raises(FileInventoryError, match="未分类"):
        scan_registered_files(tmp_path, set())
    with pytest.raises(FileInventoryError, match="缺失"):
        scan_registered_files(tmp_path, {"manual_evidence/row/item", "avatars/missing.jpg"})


def test_inventory_rejects_escape_and_symlink(tmp_path: Path) -> None:
    for invalid in ("../secret", "/absolute", "manual_evidence/../secret", "other/file"):
        with pytest.raises(FileInventoryError):
            scan_registered_files(tmp_path, {invalid})
    outside = tmp_path.parent / "outside-evidence"
    root = tmp_path / "manual_evidence"
    root.mkdir()
    (root / "linked").symlink_to(outside)
    with pytest.raises(FileInventoryError, match="符号链接"):
        scan_registered_files(tmp_path, set())
