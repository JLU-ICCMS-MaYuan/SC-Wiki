"""生产恢复边界和三组编排的隔离检查。"""
import hashlib
import json
from pathlib import Path
import subprocess

import boto3
import pytest
from moto import mock_aws

from scripts import deploy
from scripts import production_backup as backup


@pytest.fixture
def objects(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="source-bucket")
        client.create_bucket(Bucket="target-bucket")
        content = b"scientific evidence"
        client.put_object(Bucket="source-bucket", Key="papers/source.pdf", Body=content,
                          ContentType="application/pdf",
                          Metadata={"sha256": hashlib.sha256(content).hexdigest(), "origin": "original"})
        monkeypatch.setattr(backup, "object_client", lambda: (client, "source-bucket"))
        yield client


def test_object_roundtrip_preserves_key_content_and_metadata(objects, monkeypatch, tmp_path):
    source = tmp_path / "objects"
    assert backup.export_objects(source)["objects"] == 1
    monkeypatch.setattr(backup, "object_client", lambda: (objects, "target-bucket"))
    assert backup.restore_objects(source)["verified_objects"] == 1
    item = objects.get_object(Bucket="target-bucket", Key="papers/source.pdf")
    assert item["Body"].read() == b"scientific evidence"
    assert item["Metadata"]["origin"] == "original"
    assert item["ContentType"] == "application/pdf"
    with pytest.raises(ValueError, match="必须为空"):
        backup.restore_objects(source)


def test_corrupt_backup_does_not_write_target(objects, monkeypatch, tmp_path):
    source = tmp_path / "objects"
    backup.export_objects(source)
    (source / "00000000.blob").write_bytes(b"corrupt")
    monkeypatch.setattr(backup, "object_client", lambda: (objects, "target-bucket"))
    with pytest.raises(ValueError):
        backup.restore_objects(source)
    assert backup.list_objects(objects, "target-bucket") == {}


def test_missing_digest_metadata_is_rejected(objects, tmp_path):
    objects.put_object(Bucket="source-bucket", Key="papers/invalid.pdf", Body=b"missing")
    with pytest.raises(ValueError, match="摘要元数据"):
        backup.export_objects(tmp_path / "objects")
    assert not (tmp_path / "objects/manifest.json").exists()


def make_release(tmp_path):
    values = {"DEPLOYMENT_ID": "scwiki-test", "SCWIKI_ROOT": str(tmp_path.resolve()),
              "SOURCE_COMMIT": "1" * 40, "SITE_DOMAIN": "www.example.org", "SITE_APEX": "example.org"}
    values.update({name: "example/image@sha256:" + "a" * 64 for name in deploy.IMAGE_KEYS})
    path = tmp_path / "release.env"
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    private = tmp_path / "private"
    private.mkdir()
    for name in ("app.env", "neo4j.env", "qdrant.env", "redis.conf", "garage.toml"):
        (private / name).write_text("")
    return path


def test_unknown_storage_is_not_implicitly_created(tmp_path):
    deployment = deploy.Deployment(make_release(tmp_path))
    with pytest.raises(ValueError, match="显式 init"):
        deployment.require_identity()


def test_mutable_image_tag_is_rejected(tmp_path):
    release = make_release(tmp_path)
    release.write_text(release.read_text().replace("example/image@sha256:" + "a" * 64, "example/image:latest"))
    with pytest.raises(ValueError, match="固定 digest"):
        deploy.read_release(release)


def test_compose_groups_have_no_cross_dependencies_or_shared_business_files(tmp_path):
    release = make_release(tmp_path)
    deployment = deploy.Deployment(release)
    configs = {}
    for group in deploy.GROUPS:
        result = deployment.compose(group, "--profile", "*", "config", "--format", "json", capture=True)
        configs[group] = json.loads(result.stdout)
        for service in configs[group]["services"].values():
            assert not service.get("depends_on")
    assert all(not service.get("ports") for service in configs["data"]["services"].values())
    assert all(not service.get("ports") for service in configs["compute"]["services"].values())
    app_mounts = configs["app"]["services"]["python"]["volumes"]
    compute_mounts = configs["compute"]["services"]["worker"]["volumes"]
    assert {v["source"] for v in app_mounts}.isdisjoint(v["source"] for v in compute_mounts)
    assert configs["app"]["services"]["maintenance"]["profiles"] == ["maintenance"]
    assert configs["app"]["networks"]["default"]["external"]
