#!/usr/bin/env bash
# 参数通过 argv/环境传递，不拼接 shell 命令。
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$root/scripts/local-deploy.py" pack "$@"
