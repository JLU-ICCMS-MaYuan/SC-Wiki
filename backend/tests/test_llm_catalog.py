"""#116 编号组解析与安全元数据。"""
import pytest

from backend.rag.llm_catalog import CatalogConfigError, parse_catalog


def group(number, **changes):
    values = {"NAME": "测试", "BASE_URL": "https://example.com/v1", "MODEL": "model", "API_KEY": "secret-test"}
    values.update(changes)
    return {f"LLM{number}_{key}": value for key, value in values.items()}


def test_numeric_order_gaps_default_and_safe_projection():
    catalog = parse_catalog({**group(10), **group(3), **group(1), "LLM_DEFAULT": "LLM3"})
    assert [v.id for v in catalog.items] == ["LLM1", "LLM3", "LLM10"]
    assert catalog.default_id == "LLM3"
    assert catalog.find("LLM3").public() == {"id": "LLM3", "name": "测试", "model": "model"}
    assert "secret-test" not in repr(catalog)
    assert catalog.find("LLM2") is None


def test_empty_templates_and_legacy_keys_do_not_enable_catalog():
    assert not parse_catalog({**group(1, NAME="", BASE_URL="", MODEL="", API_KEY=""), "LLM_API_KEY": "legacy"}).items
    assert parse_catalog(group(8)).default_id == "LLM8"


@pytest.mark.parametrize("values", [
    group(0), group("01"), group(1, API_KEY=""), group(1, BASE_URL="bad-secret-url"),
    {**group(1), "LLM_DEFAULT": "LLM2"}, {"LLM1_PASSWORD": "secret-test"},
    group(1, API_KEY="secret-test\nmore"), group(1, BASE_URL="https://example.com/?key=secret-test"),
    group(1, BASE_URL="https://[secret-test"), group(1, BASE_URL="https://example.com:secret-test"),
])
def test_invalid_configuration_never_echoes_values(values):
    with pytest.raises(CatalogConfigError) as error:
        parse_catalog(values)
    assert "secret-test" not in str(error.value)
    assert "bad-secret-url" not in str(error.value)
