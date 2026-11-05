"""核验 #221 逐字迁移、引用及旧 #220 历史索引；不写业务数据。"""
from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument("--check-current", action="store_true", help="核对本次迁移后的文档快照；后续正常编辑可能改变快照")
args = parser.parse_args()
directory = Path(__file__).resolve().parents[1]
root = directory.parents[2]
manifest = json.loads((directory / "migration-manifest.json").read_text())
archive = (directory / "migrated-records.md").read_bytes().decode("utf-8")
digest = lambda value: hashlib.sha256(value).hexdigest()
for item in manifest["fragments"]:
    original = archive[item["archive_char_start"]:item["archive_char_start"] + item["archive_char_length"]]
    assert digest(original.encode()) == item["sha256"], item["id"]
for item in manifest["relocations"]:
    assert digest((root / item["destination"]).read_bytes()) == item["sha256"], item["destination"]
    if args.check_current:
        assert digest((root / item["source"]).read_bytes()) == item["source_after_sha256"], item["source"]
if args.check_current:
    for item in manifest["documents"]:
        assert digest((root / item["path"]).read_bytes()) == item["after_sha256"], item["path"]
    for item in manifest.get("reviewed_unchanged", []):
        assert digest((root / item["path"]).read_bytes()) == item["before_sha256"], item["path"]
    # 混合段落迁移不能把共享表单、数据及解析约束改归侧栏。
    guards = {
        "docs/specs/174-form-processing-contract/spec.md": ["中文组合输入、中间数值、清空", "临时错误、待处理计数", "不丢值或串位"],
        "docs/specs/203-fixed-form-field-contract/spec.md": ["不新增独立诊断面板", "不隐藏未解决问题"],
        "docs/specs/204-automatic-state-structure/spec.md": ["已有人工内容保护", "不伪造核对通过"],
    }
    for path, requirements in guards.items():
        text = (root / path).read_text()
        assert all(value in text for value in requirements), path

old_path = root / "docs/specs/220-field-red-marking/migration-manifest.json"
old_manifest = json.loads(old_path.read_text())
old_archive = (old_path.parent / old_manifest["archive_path"]).read_bytes().decode("utf-8")
for item in old_manifest["fragments"]:
    original = old_archive[item["archive_char_start"]:item["archive_char_start"] + item["archive_char_length"]]
    assert digest(original.encode()) == item["sha256"], item["id"]

def remove_fences(text):
    result, fence = [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(" + chr(96) + r"{3,}|~{3,})", line)
        if fence:
            if re.match(r"^\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", line):
                fence = None
            continue
        if match:
            fence = match[1]
            continue
        result.append(line)
    return "".join(result)

checked = 0
paths = [root / item["path"] for item in manifest["documents"]] + list(directory.rglob("*.md")) + [root / "AGENTS.md"]
for path in paths:
    text = remove_fences(path.read_text())
    for match in re.finditer(r"\]\(([^)]+)\)", text):
        value = match[1].strip("<>").split("#")[0]
        if not value or ":" in value:
            continue
        # 只证明新增入口及本功能文档链接，不把原有无关链接算成本次验证。
        if "221-scientific-field-sidebar" not in value and not path.is_relative_to(directory):
            continue
        target = Path(value) if value.startswith("/") else path.parent / value
        assert target.exists(), (str(path), value)
        checked += 1
print(json.dumps({
    "documents": len(manifest["documents"]), "issues": len(manifest["issues"]),
    "comments": len(manifest.get("comments", [])), "fragments": len(manifest["fragments"]),
    "relocations": len(manifest["relocations"]), "old_220_fragments": len(old_manifest["fragments"]),
    "links_checked": checked, "all_hashes_match": True, "check_current": args.check_current
}, ensure_ascii=False))
