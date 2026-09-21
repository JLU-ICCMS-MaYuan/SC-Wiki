#!/usr/bin/env bash
# 由系统 Python 预检和引导，不要求旧 .env 或已经激活 Conda。
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$root/scripts/local-deploy.py" deploy "$@"
