#!/usr/bin/env python3
"""为独立 Docker 运行目录生成只含编号 LLM 的私有环境文件。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import tempfile

from local_deploy.config import parse_env


def export(source: Path, output: Path) -> int:
    if source.resolve() == output.resolve() or source.is_symlink() or output.is_symlink():
        raise ValueError("源和目标必须是不同的普通文件")
    values = parse_env(source.read_text())
    selected = {k: v for k, v in values.items() if k == "LLM_DEFAULT" or re.fullmatch(r"LLM\d+_.+", k)}
    def quoted(value):
        # Compose 的双美元转义确保密钥中的 $ 不被当成宿主环境变量。
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '$$') + '"'
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=output.parent, prefix='.llm-env-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.writelines(k + '=' + quoted(v) + '\n' for k, v in sorted(selected.items()))
        os.replace(name, output)
    finally:
        Path(name).unlink(missing_ok=True)
    return len(selected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        count = export(args.source, args.output)
        print(f'已同步 {count} 个编号配置字段（不显示配置值）')
    except (OSError, ValueError):
        parser.exit(2, '配置同步失败：请检查文件路径及 .env 格式；未输出任何配置值。\n')
