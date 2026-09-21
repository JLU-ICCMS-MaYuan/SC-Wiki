#!/usr/bin/env bash
# 与 locallydeploy 共用环境安装和配置生成，不再要求旧 .env。
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$root/scripts/locallydeploy.sh" --setup-only "$@"
