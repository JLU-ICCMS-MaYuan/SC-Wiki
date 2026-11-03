"""#205：将已审定业务字段用于模型生成；人工扩展不经过此入口。"""
from copy import deepcopy

from .fixed_form_contract import CONTRACT


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def array(items):
    return {"type": "array", "items": items}


TEXT = {"type": "string"}
NUMBER = {"type": "number"}
BOOLEAN = {"type": "boolean"}


def quote_schema():
    return obj({"file_id": TEXT, "pdf_page": {"type": "integer"}, "block_id": TEXT,
                "quote": nullable(TEXT), "quote_id": nullable(TEXT)})


def quantity_schema():
    types = {"value_kind": TEXT, "value_raw": TEXT, "value_number": NUMBER, "value_min": NUMBER,
             "value_max": NUMBER, "value_text": TEXT, "value_boolean": BOOLEAN,
             "unit_raw": TEXT, "reported": BOOLEAN, "evidences": array(quote_schema())}
    return obj({key: nullable(types[key]) for key in CONTRACT["quantity_fields"]})


def parameter_value():
    return {"anyOf": [NUMBER, TEXT, array(NUMBER), {"$ref": "#/$defs/ScientificQuantity"}, {"type": "null"}]}


def conditions_schema():
    fields = {key: nullable(TEXT) for key in CONTRACT["condition_fields"]}
    for software, keys in CONTRACT["software"].items():
        fields[software] = nullable(obj({key: parameter_value() for key in keys}))
    # 人工extensions/field_settings由人工入口拥有，模型不能输出它们。
    return obj(fields)


def parameters_schema():
    extension = quantity_schema()["properties"] | {
        "key": {"type": "string", "enum": ["mu_star", "mu_star_reported_range", "mu_star_reported",
                                              "lambda_ep_reported", "omega_log_reported"]}}
    return obj({"lambda_ep": parameter_value(), "omega_log": parameter_value(), "mu_star": parameter_value(),
                "extensions": array(obj(extension))})


def payload_schema():
    case_types = {"stability": TEXT, "above_hull": NUMBER, "unit": TEXT, "temperature_k": NUMBER,
                  "zpe": TEXT, "decomposition_path": TEXT, "source_description": TEXT}
    case = obj({key: nullable(case_types[key]) for key in CONTRACT["thermodynamic_case_fields"]})
    thermal = obj({"version": {"type": "integer"}, "basis": TEXT,
                   "cases": obj({key: nullable(case) for key in
                                 ("formation_energy", "formation_enthalpy", "formation_gibbs", "unspecified")})})
    fields = {"parameters": nullable({"$ref": "#/$defs/ScientificParameters"}),
              "calculation_conditions": nullable({"$ref": "#/$defs/ScientificConditions"}),
              "thermodynamic_stability": nullable(thermal),
              "table_row_ref": nullable(obj({"file_id": TEXT, "table_id": TEXT,
                                               "row_index": {"type": "integer"}, "group": nullable(TEXT)})),
              "method_variant_status": nullable(TEXT)}
    assert set(fields) <= set(CONTRACT["payload_fields"])
    return obj(fields)


def definitions():
    return {"ScientificQuantity": quantity_schema(), "ScientificParameters": parameters_schema(),
            "ScientificConditions": conditions_schema()}


def _strict(node):
    """只转换已有声明；开放对象必须由调用方给出明确结构，不能悄悄放行。"""
    if isinstance(node, list):
        return [_strict(value) for value in node]
    if not isinstance(node, dict):
        return node
    result = {key: _strict(value) for key, value in node.items() if key not in {"default", "title"}}
    if result.get("type") == "object":
        if "properties" not in result:
            raise ValueError("科学输出存在未定义允许字段的对象")
        result["additionalProperties"] = False
        result["required"] = list(result["properties"])
    return result


def extraction_schema(base):
    schema = deepcopy(base)
    defs = schema["$defs"]
    props = schema["properties"]
    quote = quote_schema()
    fact = obj({"value": TEXT, "scope": {"enum": ["current_paper", "referenced_work"], "type": "string"},
                "evidences": array(quote)})
    paper = {}
    for key, kind in CONTRACT["paper_fields"].items():
        if kind == "enum":
            value = {"type": "string", "enum": CONTRACT["enums"][key]}
        elif kind == "integer":
            value = {"type": "integer"}
        elif kind.endswith("[]"):
            value = array(TEXT)
        else:
            value = TEXT
        paper[key] = nullable(value)
    props["metadata"] = obj(paper)
    props["paper_type_evidence"] = array(obj(quote["properties"] | {
        "candidate": TEXT, "scope": {"enum": ["current_paper", "referenced_work"], "type": "string"}}))
    for name in ("research_materials", "referenced_materials", "methodology", "key_findings"):
        props[name] = array({"anyOf": [TEXT, fact]})
    family = obj({"name": TEXT, "scope": TEXT, "page": nullable({"type": "integer"}), "quote": nullable(TEXT)})
    defs["ExtractedState"]["properties"]["material_family"] = nullable(family)
    defs["ExtractedState"]["properties"]["structure_families"] = array(family)
    record = defs["ExtractedRecord"]
    record["properties"]["payload"] = payload_schema()
    # 服务器分配身份。删除的是schema中的可选身份声明，不删除模型响应中的非法键。
    owned = {"record_key", "definition_key", "definition_version", "custom_property_key", "structure_key", "evidence"}
    for key in owned:
        record["properties"].pop(key, None)
    record["required"] = [key for key in record.get("required", []) if key not in owned]
    defs.pop("JsonValue", None)
    defs.update(definitions())
    result = _strict(schema)
    from backend.rag.structured_output import output_format
    output_format(result)
    return result


def filling_schema():
    # values对应既有PATCH_FIELDS；不允许approximation或模型新增人工扩展。
    fields = {key: nullable(NUMBER) for key in ("value_number", "value_min", "value_max", "uncertainty")}
    fields.update({key: nullable(TEXT) for key in ("value_text", "method_raw", "unit_raw", "canonical_unit")})
    fields.update({"value_kind": {"type": "string", "enum": ["number", "range", "text", "boolean"]},
                   "value_raw": TEXT, "method_code": nullable(TEXT), "value_boolean": nullable(BOOLEAN),
                   "parameters": nullable({"$ref": "#/$defs/ScientificParameters"}),
                   "calculation_conditions": nullable({"$ref": "#/$defs/ScientificConditions"})})
    record = obj({"candidate_ids": array(TEXT), "group": TEXT, "method": TEXT, "values": obj(fields),
                  "source_ids": array(TEXT), "reason": TEXT})
    disposition = obj({"candidate_id": TEXT, "category": TEXT, "source_ids": array(TEXT), "reason": TEXT})
    return obj({"done": BOOLEAN, "read_source_ids": array(TEXT), "search": array(TEXT),
                "records": array(record), "excluded": array(disposition), "unresolved": array(disposition)}) | {"$defs": definitions()}



def decode_optional_containers(value):
    """严格协议用null表示未提供的可选容器；保留科学标量null及原始响应。"""
    value = deepcopy(value)
    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for key in ("parameters", "calculation_conditions", "thermodynamic_stability", "table_row_ref"):
                if key in node and node[key] is None:
                    del node[key]
            thermal = node.get("thermodynamic_stability")
            if isinstance(thermal, dict) and isinstance(thermal.get("cases"), dict):
                thermal["cases"] = {k: v for k, v in thermal["cases"].items() if v is not None}
            for item in node.values():
                visit(item)
    visit(value)
    return value
