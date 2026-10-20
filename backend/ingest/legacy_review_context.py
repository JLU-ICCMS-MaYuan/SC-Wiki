"""只用于精确重建v7旧字段断言，不进入新核对主路径。"""

from copy import deepcopy
from .property_field_review import read_path


def review_context(record, state, path):
    """仅真实上下文进入版本；修改别的结果值不使本字段失效。"""
    context = deepcopy(state)
    payload = record.get("payload") or {}
    is_mu = path.startswith("payload.parameters.mu_star") or path.startswith("payload.parameters.extensions.")
    if path == "method_code" or path.startswith("value_") or is_mu:
        context["definition"] = [record.get("definition_key"), record.get("definition_version")]
    if payload.get("approximation"):
        context["approximation"] = payload["approximation"]
    annotations = None
    if path.startswith("payload.parameters."):
        name = path.split(".")[2].replace("omega_log_k", "omega_log")
        annotations = (
            (payload.get("field_settings") or {}).get("mu_star")
            if is_mu
            else (payload.get("parameters", {}).get("field_settings") or {}).get(name)
        )
    elif path.startswith("payload.calculation_conditions.") and ".extensions." not in path:
        annotations = (payload.get("calculation_conditions", {}).get("field_settings") or {}).get(
            path.split(".")[2]
        )
    elif path.startswith("value_"):
        annotations = (payload.get("field_settings") or {}).get("tc")
    if annotations:
        context["field_settings"] = deepcopy(annotations)
    if path.startswith("value_") and record.get("value_kind") in {"number", "range"} or "omega_log" in path:
        context["unit"] = "K"
    elif "lambda_ep" in path or is_mu:
        context["unit"] = "1"
    if path.startswith("value_"):
        parameters = payload.get("parameters") or {}
        mu = parameters.get("mu_star")
        if isinstance(mu, dict):
            mu = mu.get("value_number")
        for i, extension in enumerate(parameters.get("extensions") or []):
            if (
                extension.get("key") == "mu_star"
                and extension.get("value_kind") == "range"
                and path in {"value_min", "value_max"}
            ):
                mu = extension.get("value_max" if path == "value_min" else "value_min")
        context["paired_mu_star"] = mu
    elif is_mu:
        context["paired_tc"] = (
            record.get("value_number")
            if record.get("value_kind") == "number"
            else (
                record.get("value_min" if path.endswith(".value_max") else "value_max")
                if ".extensions." in path
                else [record.get("value_min"), record.get("value_max")]
            )
        )
    if (
        path.startswith(("value_", "payload.parameters.mu_star"))
        or ".extensions." in path
        and path.startswith("payload.parameters.")
    ):
        context["method_code"] = record.get("method_code")
    if path.startswith(("value_", "payload.parameters.")):
        conditions = deepcopy(payload.get("calculation_conditions") or {})
        conditions["extensions"] = [
            e
            for e in conditions.get("extensions") or []
            if not str(e.get("key") or "").startswith(("structural_relaxation.", "aimd."))
        ]
        context["calculation_conditions"] = conditions
        context["approximation"] = payload.get("approximation")
    if ".sscha." in path:
        context["approximation"] = payload.get("approximation")
    return context
