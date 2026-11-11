"""严格输出的本地结构门；不重试、不丢键，也不判断科学正确性。"""
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


class StructuredOutputError(ValueError):
    """结构不合规不能通过增加模型纠错轮次处理。"""


def decode_tool_arguments(raw):
    """只恢复已完整对象后的单个冗余闭合符，不修字段、内容或截断响应。"""
    import json
    import hashlib
    import math
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as original:
        if original.msg == 'Extra data':
            def pairs(items):
                value = {}
                for key, item in items:
                    if key in value: raise ValueError('duplicate key')
                    value[key] = item
                return value
            def constant(_): raise ValueError('nonfinite constant')
            def number(text):
                value = float(text)
                if not math.isfinite(value): raise ValueError('nonfinite number')
                return value
            try:
                text = raw.lstrip()
                value, end = json.JSONDecoder(object_pairs_hook=pairs, parse_constant=constant,
                                              parse_float=number).raw_decode(text)
                if isinstance(value, dict) and text[end:].strip() == '}':
                    return value, {'normalization': 'redundant_terminal_object_closer',
                                   'raw_sha256': hashlib.sha256(raw.encode()).hexdigest()}
            except (ValueError, TypeError):
                pass
        raise StructuredOutputError('工具参数未形成完整JSON') from original


def output_format(schema):
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise StructuredOutputError("输出结构定义无效") from exc

    def closed(node):
        if isinstance(node, dict):
            types = node.get("type", [])
            if types == "object" or isinstance(types, list) and "object" in types or "properties" in node:
                if node.get("additionalProperties") is not False:
                    raise StructuredOutputError("模型输出对象必须关闭额外字段")
                if set(node.get("required", [])) != set(node.get("properties", {})):
                    raise StructuredOutputError("严格输出必须声明所有允许字段")
            for value in node.values():
                closed(value)
        elif isinstance(node, list):
            for value in node:
                closed(value)
    closed(schema)
    return {"type": "json_schema", "json_schema": {"name": "scientific_fields", "strict": True, "schema": schema}}


def validate_output(value, schema):
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "$"
        # 不把模型内容、源文或凭据塞入错误提示。
        raise StructuredOutputError(f"模型输出未遵守固定字段结构：{path}（{exc.validator}）") from exc


def validate_tool_action(action, definitions, *, argument_context=None):
    if not isinstance(action, dict) or set(action) != {"name", "arguments"}:
        raise StructuredOutputError("工具调用必须仅包含名称和参数")
    definition = next((item["function"] for item in definitions if item["function"]["name"] == action["name"]), None)
    if definition is None:
        raise StructuredOutputError("模型请求了当前不可用的工具")
    from .panel_identity import bind
    action, bindings = bind(action, argument_context)
    validate_output(action["arguments"], definition["parameters"])
    return action, bindings
