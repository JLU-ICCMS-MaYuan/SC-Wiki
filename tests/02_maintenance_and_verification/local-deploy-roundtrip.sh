#!/usr/bin/env bash
# 只创建本次演练的容器和数据卷，不使用开发实例的数据库或端口。
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
python_bin="${LOCAL_DEPLOY_TEST_PYTHON:-$HOME/miniconda3/envs/sc-wiki/bin/python}"
test_id="scwiki-112-test-$(date +%s)-$$"
containers=()
cleanup() {
  local name
  for name in "${containers[@]}"; do
    docker rm -fv "$name" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT
start() {
  local name="$test_id-$1"; shift
  containers+=("$name")
  docker run -d --name "$name" --label "scwiki.test=$test_id" "$@" >/dev/null
}
start mysql -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=scwiki_test -p 127.0.0.1::3306 mysql:8.4 --skip-log-bin --event-scheduler=OFF
start redis -p 127.0.0.1::6379 redis:7-alpine
qdrant_image="$("$python_bin" -c 'import json; print(json.load(open("scripts/local-deploy-versions.json"))["qdrant"]["image"])')"
start qsource -p 127.0.0.1::6333 "$qdrant_image"
start qtarget -p 127.0.0.1::6333 "$qdrant_image"
mysql_port="$(docker port "$test_id-mysql" 3306 | cut -d: -f2)"
redis_port="$(docker port "$test_id-redis" 6379 | cut -d: -f2)"
export LOCAL_DEPLOY_TEST_MYSQL_URL="mysql+pymysql://root@127.0.0.1:$mysql_port/scwiki_test"
export LOCAL_DEPLOY_TEST_MYSQL_SOURCE="mysql+pymysql://root@127.0.0.1:$mysql_port/scwiki_source_test"
export LOCAL_DEPLOY_TEST_MYSQL_TARGET="mysql+pymysql://root@127.0.0.1:$mysql_port/scwiki_target_test"
export LOCAL_DEPLOY_TEST_REDIS_URL="redis://127.0.0.1:$redis_port/0"
export LOCAL_DEPLOY_TEST_QDRANT_PORT="$(docker port "$test_id-qsource" 6333 | cut -d: -f2)"
export LOCAL_DEPLOY_TEST_QDRANT_TARGET_PORT="$(docker port "$test_id-qtarget" 6333 | cut -d: -f2)"
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "$test_id-mysql" mysql --protocol=TCP -h127.0.0.1 -uroot -e 'CREATE DATABASE IF NOT EXISTS scwiki_source_test; CREATE DATABASE IF NOT EXISTS scwiki_target_test' >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo "隔离 MySQL 未就绪" >&2; exit 1; }
"$python_bin" -m pytest "tests/02_maintenance_and_verification/test_local_deployment.py" -q
