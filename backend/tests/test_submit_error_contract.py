"""Issue #58：未捕获异常的对外错误契约。

提交审核失败时前端只能显示「提交审核失败」，根因之一是未捕获异常经 Starlette 默认处理
返回纯文本 Internal Server Error，前端无法从 detail 取到具体原因。本模块经真实 FastAPI
路由验证响应体形态与脱敏要求——纯函数测试无法证明 Starlette 处理链的行为。
"""
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/scwiki-error-contract-test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

from backend.main import app


# 复现实测故障：写入超长 section_name 触发的数据库异常，其原文含表名、列名与驱动细节
_REAL_DB_ERROR = (
    "(asyncmy.errors.DataError) (1406, \"Data too long for column 'section_name' at row 1\")\n"
    "[SQL: INSERT INTO paper_chunks (paper_id, section_name, heading, content) VALUES (%s, %s, %s, %s)]"
)


async def _boom():
    raise RuntimeError(_REAL_DB_ERROR)


async def _upload_error_route():
    raise HTTPException(status_code=400, detail={"code": "title_required", "message": "论文标题不能为空"})


@pytest.fixture
def client():
    # 在既有应用上挂载探针路由，验证真实的异常处理链而非替身应用。
    # main.py 注册了 SPA 兜底路由 GET /{full_path:path}，它会先匹配任何路径，
    # 因此探针必须插到路由表最前面，否则请求拿不到 500/400 而是 SPA 响应。
    original_routes = list(app.router.routes)
    app.add_api_route("/api/_test/boom", _boom, methods=["GET"])
    app.add_api_route("/api/_test/upload-error", _upload_error_route, methods=["GET"])
    app.router.routes = app.router.routes[len(original_routes):] + original_routes

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.router.routes = original_routes


def test_uncaught_exception_returns_structured_detail(client):
    response = client.get("/api/_test/boom")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "internal_error"
    assert isinstance(detail["message"], str) and detail["message"].strip()


def test_uncaught_exception_response_hides_internal_details(client):
    body = client.get("/api/_test/boom").text

    for leaked in (
        "asyncmy",
        "DataError",
        "section_name",
        "INSERT",
        "paper_chunks",
        "1406",
        "/app/backend/",
        "Traceback",
    ):
        assert leaked not in body, f"对外响应不得泄漏 {leaked}"


def test_existing_http_exception_contract_is_not_rewritten(client):
    response = client.get("/api/_test/upload-error")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "title_required"
    assert detail["message"] == "论文标题不能为空"


def test_missing_material_contract_names_identity_fields(client):
    """名称与化学式皆空时保留状态序号，并返回可定位的字段错误。"""
    import re

    from backend.api.rag import _validate_draft

    draft = {
        "paper": {
            "title": "测试论文",
            "year": 2024,
            "paper_type": "experimental",
            "superconductor_kind": "unknown",
            "research_materials": ["LaH10"],
            "material_families": [
                {"id": None, "name": "氢基超导体", "status": "pending"}
            ],
        },
        "material_states": [
            {"material": ""},
            {"material": "H3S"},
        ],
    }

    with pytest.raises(HTTPException) as exc_info:
        _validate_draft(draft)

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["code"] == "state_material_required"
    assert re.fullmatch(r"第 \d+ 个材料状态至少需要材料名或化学式", detail["message"]), detail["message"]
    assert detail['field'] == 'material_states[0].material_name'
    # 序号前缀必须保留，供前端解析并定位到出错卡片
    assert detail["message"].startswith("第 1 个材料状态")


def test_issue97_property_error_contains_complete_material_module_record_path():
    from backend.api.rag import _validate_draft

    draft = {
        "paper": {"title": "测试论文", "paper_type": "experimental", "material_families": [{"id": 1, "name": "氢基超导体"}]},
        "material_states": [{
            "material": "Pb",
            "property_modules": [{
                "module_key": "module-superconductive_properties",
                "module_code": "superconductive_properties",
                "records": [{
                    "record_key": "tc-1", "record_type": "measured_tc", "property_code": "tc",
                    "custom_property_key": "stale-key", "definition_key": "record.superconductive_properties.measured_tc.resistivity",
                    "definition_version": 1, "name_raw": "Tc", "value_kind": "number", "value_raw": "203 K",
                    "value_number": 203, "canonical_unit": "K", "method_code": "resistivity",
                    "payload": {"experimental_conditions": {}},
                }],
            }],
        }],
    }

    with pytest.raises(HTTPException) as exc_info:
        _validate_draft(draft)

    issue = exc_info.value.detail["issues"][0]
    assert issue["field"] == "material_states[0].property_modules[0].records[0].custom_property_key"
    assert issue["message"] == "规范性质不能携带自定义键"


def test_scientific_integrity_error_points_to_record_field_without_leaking_database_details():
    from sqlalchemy.exc import IntegrityError

    from backend.api.rag import _scientific_integrity_error

    draft = {
        "material_states": [{
            "material": "Pb",
            "property_modules": [{
                "module_code": "superconductive_properties",
                "records": [{
                    "record_type": "measured_tc",
                    "property_code": "tc",
                    "custom_property_key": "stale-key",
                }],
            }],
        }],
    }
    exc = IntegrityError(
        "INSERT ...",
        {},
        RuntimeError("ck_property_records_custom_identity: CHECK failed for property_records"),
    )

    response = _scientific_integrity_error(exc, draft)

    assert response.status_code == 409
    detail = response.detail
    assert detail["code"] == "scientific_data_integrity_error"
    assert detail["issues"][0]["field"] == "material_states[0].property_modules[0].records[0].custom_property_key"
    assert "填写" in detail["issues"][0]["message"]
    assert "property_records" not in str(detail)
    assert "INSERT" not in str(detail)


def test_scientific_integrity_error_has_actionable_fallback_when_constraint_is_unknown():
    from sqlalchemy.exc import IntegrityError

    from backend.api.rag import _scientific_integrity_error

    exc = IntegrityError("INSERT ...", {}, RuntimeError("driver-specific failure"))
    response = _scientific_integrity_error(exc, {"material_states": [{"material": "Pb"}]})

    issue = response.detail["issues"][0]
    assert issue["field"] == "material_states"
    assert "化学式" in issue["message"]
    assert "重新提交" in issue["message"]
