#!/usr/bin/env python3
"""SC-Wiki 三组部署入口：身份检查、显式初始化与有界就绪检查。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

GROUPS = ("data", "compute", "app")
VOLUMES = ("mysql", "redis", "neo4j", "neo4j-logs", "qdrant", "garage-meta",
           "garage-data", "app-scratch", "app-models", "compute-scratch",
           "compute-models", "caddy-data", "caddy-config")
GROUP_VOLUMES = {
    "data": VOLUMES[:7],
    "app": ("app-scratch", "app-models", "caddy-data", "caddy-config"),
    "compute": ("compute-scratch", "compute-models"),
}
IMAGE_KEYS = ("MYSQL_IMAGE", "REDIS_IMAGE", "NEO4J_IMAGE", "QDRANT_IMAGE",
              "GARAGE_IMAGE", "CADDY_IMAGE", "GROBID_IMAGE", "PYTHON_IMAGE",
              "FRONTEND_IMAGE", "GOSERVER_IMAGE")


def read_release(path: Path) -> dict[str, str]:
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("发布配置格式无效")
        if key in values or not value or any(c in value for c in "\x00\r\n"):
            raise ValueError("发布配置包含重复或空字段")
        values[key] = value
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", values.get("DEPLOYMENT_ID", "")):
        raise ValueError("部署身份无效")
    root = Path(values.get("SCWIKI_ROOT", ""))
    if not root.is_absolute() or root.resolve() != root or root == Path("/"):
        raise ValueError("SCWIKI_ROOT 必须是规范绝对目录")
    prefix = values.get("SCWIKI_VOLUME_PREFIX", values["DEPLOYMENT_ID"])
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", prefix):
        raise ValueError("SCWIKI_VOLUME_PREFIX 无效")
    if "SCWIKI_VOLUME_ROOT" in values:
        data_root = Path(values["SCWIKI_VOLUME_ROOT"])
        if (not data_root.is_absolute() or data_root.resolve() != data_root
                or data_root == Path("/") or data_root == root
                or data_root in root.parents or root in data_root.parents):
            raise ValueError("SCWIKI_VOLUME_ROOT 必须是与发布根独立的规范绝对目录")
    if not re.fullmatch(r"[a-f0-9]{40}", values.get("SOURCE_COMMIT", "")):
        raise ValueError("必须记录完整源码提交")
    for key in IMAGE_KEYS:
        if not re.fullmatch(r"(?:[^\s]+@)?sha256:[a-f0-9]{64}", values.get(key, "")):
            raise ValueError(f"{key} 必须固定 digest")
    for key in ("SITE_DOMAIN", "SITE_APEX"):
        if not re.fullmatch(r"[a-z0-9.-]+", values.get(key, "")):
            raise ValueError(f"{key} 无效")
    return values


def run(command, *, capture=False, check=True):
    return subprocess.run(command, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


class Deployment:
    def __init__(self, release: Path):
        self.release = release.resolve()
        self.values = read_release(self.release)
        self.root = Path(self.values["SCWIKI_ROOT"])
        self.identity = self.values["DEPLOYMENT_ID"]
        self.volume_prefix = self.values.get("SCWIKI_VOLUME_PREFIX", self.identity)
        self.volume_root = (Path(self.values["SCWIKI_VOLUME_ROOT"])
                            if self.values.get("SCWIKI_VOLUME_ROOT") else None)
        self.source = Path(__file__).resolve().parents[1]
        self.marker = self.root / "deployment.json"

    def compose(self, group, *args, capture=False, check=True):
        # 发布配置显式传入；不依赖操作者当前目录或 Compose 默认项目名。
        return run(["docker", "compose", "--env-file", str(self.release), "-p",
                    self.identity + "-" + group, "-f",
                    str(self.source / "docker" / f"compose.{group}.yaml"),
                    *args], capture=capture, check=check)

    def inspect(self, kind, name):
        result = run(["docker", kind, "inspect", name], capture=True, check=False)
        return json.loads(result.stdout)[0] if result.returncode == 0 else None

    def require_identity(self, groups=GROUPS):
        if not self.marker.is_file() or self.marker.is_symlink():
            raise ValueError("缺少部署身份，必须显式 init；不会自动创建空存储")
        recorded = json.loads(self.marker.read_text())
        if recorded.get("deployment_id") != self.identity or recorded.get("root") != str(self.root):
            raise ValueError("部署身份或目录不一致")
        if (recorded.get("volume_prefix", self.identity) != self.volume_prefix
                or recorded.get("volume_root") != (str(self.volume_root) if self.volume_root else None)):
            raise ValueError("持久存储配置与部署标记不一致")
        if not set(groups) <= set(recorded.get("groups", [])):
            raise ValueError("目标服务组未显式初始化")
        volumes = [v for group in groups for v in GROUP_VOLUMES[group]]
        for kind, names in (("network", [self.identity + "_internal"]),
                            ("volume", [self.volume_prefix + "_" + v for v in volumes])):
            for name in names:
                info = self.inspect(kind, name)
                if not info or info.get("Labels", {}).get("scwiki.deployment") != self.identity:
                    raise ValueError(f"存储/网络身份不一致：{name}")
                if kind == "volume":
                    self.validate_volume(info, name[len(self.volume_prefix) + 1:])

    def validate_volume(self, info, suffix):
        options = info.get("Options") or {}
        if self.volume_root:
            path = self.volume_root / suffix
            if not path.is_dir() or path.resolve() != path:
                raise ValueError(f"持久目录缺失或使用符号链接：{suffix}")
            if info.get("Driver") != "local" or options != {"type": "none", "o": "bind", "device": str(path)}:
                raise ValueError(f"持久卷实际挂载路径不匹配：{suffix}")
        elif options:
            raise ValueError(f"未声明的持久卷挂载配置：{suffix}")

    def initialize(self, groups=GROUPS):
        if self.marker.exists():
            self.require_identity(groups)
            return
        volumes = [v for group in groups for v in GROUP_VOLUMES[group]]
        # 不接管其他部署的卷，不静默覆盖；同标签的中断初始化可重入。
        for kind, names in (("network", [self.identity + "_internal"]),
                            ("volume", [self.volume_prefix + "_" + v for v in volumes])):
            for name in names:
                info = self.inspect(kind, name)
                if info and info.get("Labels", {}).get("scwiki.deployment") != self.identity:
                    raise ValueError(f"发现不属于本次部署的资源：{name}")
                if info and kind == "volume":
                    self.validate_volume(info, name[len(self.volume_prefix) + 1:])
        if self.volume_root:
            for suffix in volumes:
                path = self.volume_root / suffix
                if path.exists() and (not path.is_dir() or path.resolve() != path):
                    raise ValueError(f"持久目录无效：{suffix}")
                if path.exists() and any(path.iterdir()) and not self.inspect("volume", self.volume_prefix + "_" + suffix):
                    raise ValueError(f"init 不接管非空持久目录：{suffix}")
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("private", "backups"):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        for kind, names in (("network", [self.identity + "_internal"]),
                            ("volume", [self.volume_prefix + "_" + v for v in volumes])):
            for name in names:
                if not self.inspect(kind, name):
                    args = ["docker", kind, "create", "--label", "scwiki.deployment=" + self.identity]
                    if kind == "volume" and self.volume_root:
                        self.volume_root.mkdir(parents=True, exist_ok=True, mode=0o700)
                        path = self.volume_root / name[len(self.volume_prefix) + 1:]
                        path.mkdir(exist_ok=True, mode=0o700)
                        args += ["--driver", "local", "--opt", "type=none", "--opt", "o=bind",
                                 "--opt", "device=" + str(path)]
                    run([*args, name], capture=True)
        with self.marker.open("x") as out:
            json.dump({"deployment_id": self.identity, "root": str(self.root), "groups": list(groups),
                       "volume_prefix": self.volume_prefix,
                       "volume_root": str(self.volume_root) if self.volume_root else None}, out)
        self.require_identity(groups)

    def maintenance(self, arguments, *, capture=False, check=True):
        return run(["docker", "run", "--rm", "--network", self.identity + "_internal",
                    "--label", "scwiki.deployment=" + self.identity,
                    "--env-file", str(self.root / "private/app.env"),
                    self.values["PYTHON_IMAGE"], *arguments], capture=capture, check=check)

    def check(self, role="python", *, schema=True, wait=90):
        deadline = time.monotonic() + wait
        while True:
            args = ["python", "-m",
                    "backend.scripts.check_dependencies", "--role", role]
            if schema:
                args.append("--schema")
            result = self.maintenance(args, capture=True, check=False)
            if result.returncode == 0:
                print(result.stdout.strip())
                return
            if time.monotonic() >= deadline:
                # 只公开检查程序生成的布尔值，不转发配置、异常或 SQL。
                for line in result.stdout.splitlines():
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict) and all(type(v) is bool for v in value.values()):
                            print(json.dumps(value))
                    except ValueError:
                        pass
                raise ValueError("依赖/配置/schema 检查失败；未执行迁移")
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("action", choices=["init", "config", "pull", "up", "stop",
                                           "status", "logs", "check", "migrate"])
    parser.add_argument("--group", choices=[*GROUPS, "all"], default="all")
    parser.add_argument("--service")
    parser.add_argument("--apply", action="store_true", help="显式执行 schema 迁移")
    args = parser.parse_args()
    deployment = Deployment(args.release)
    groups = GROUPS if args.group == "all" else (args.group,)
    if args.action == "init":
        deployment.initialize(groups)
        return
    deployment.require_identity(groups)
    if args.action == "check":
        deployment.check("compute" if args.group == "compute" else "python")
        return
    if args.action == "migrate":
        if not args.apply:
            deployment.maintenance(["python", "-m", "backend.scripts.check_dependencies", "--schema"])
        else:
            deployment.maintenance(["python", "-m", "backend.scripts.run_migrations", "--production", "--apply"])
        return
    if args.action == "logs" and (args.group == "all" or not args.service):
        parser.error("logs 必须指定 --group 和 --service")
    for group in (tuple(reversed(groups)) if args.action == "stop" else groups):
        if args.action == "config":
            deployment.compose(group, "config", "--quiet")
        elif args.action == "pull":
            deployment.compose(group, "pull")
        elif args.action == "up":
            if group != "data":
                deployment.check()
            deployment.compose(group, "up", "-d", "--no-build", "--pull", "never")
            if group == "compute":
                deployment.check("compute")
        elif args.action == "stop":
            deployment.compose(group, "stop", "--timeout", "120")
        elif args.action == "status":
            deployment.compose(group, "ps", "-a")
        elif args.action == "logs":
            deployment.compose(group, "logs", "--tail", "100", args.service)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc) if isinstance(exc, ValueError) else
                         "部署命令失败；请检查所选项目、镜像与私有配置")
