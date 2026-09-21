#!/usr/bin/env python3
"""供系统 Python 使用的部署入口。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.local_deploy.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
