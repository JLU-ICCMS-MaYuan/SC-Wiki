"""预测 Tc 已有参数契约的校验；范围 μ* 复用 parameters.extensions。"""
import math
from decimal import Decimal


def parameter_issues(record):
    if record.get("record_type") != "predicted_tc":
        return []
    parameters = record.get("payload", {}).get("parameters")
    if parameters is None:
        return []
    if not isinstance(parameters, dict):
        return [("payload.parameters", "参数必须是对象")]
    issues = []

    def valid(value):
        return value is None or (not isinstance(value, bool) and isinstance(value, (int, float, Decimal)) and math.isfinite(value) and value >= 0)

    for key in ("lambda_ep", "omega_log", "mu_star"):
        value = parameters.get(key, parameters.get("omega_log_k") if key == "omega_log" else None)
        if isinstance(value, dict):
            value = value.get("value_number")
        if not valid(value):
            issues.append((f"payload.parameters.{key}", "请输入完整的非负数值"))
    extensions = parameters.get("extensions", [])
    if not isinstance(extensions, list):
        return [*issues, ("payload.parameters.extensions", "补充参数必须是数组")]
    ranges = [(index, value) for index, value in enumerate(extensions) if isinstance(value, dict) and value.get("key") == "mu_star" and value.get("value_kind") == "range"]
    for index, value in ranges:
        path = f"payload.parameters.extensions.{index}"
        for field in ("value_min", "value_max"):
            if not valid(value.get(field)):
                issues.append((f"{path}.{field}", "请输入完整的非负 μ* 数值"))
        lower, upper = value.get("value_min"), value.get("value_max")
        if lower is not None and upper is not None and valid(lower) and valid(upper) and lower > upper:
            issues.append((f"{path}.value_max", "两组 Tc 与 μ* 的对应关系不一致，请检查输入"))
    if ranges and (parameters.get("mu_star") is not None or record.get("value_kind") != "range" or len(ranges) > 1):
        issues.append(("payload.parameters.mu_star", "μ* 数值与范围表示冲突，请检查输入"))
    return issues
