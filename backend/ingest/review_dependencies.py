"""核对只依赖本字段实际读取的输入；状态同属关系不是依赖。"""

from copy import deepcopy

STATE_INPUTS = (
    "material",
    "material_name",
    "pressure_value_gpa",
    "pressure_min_gpa",
    "pressure_max_gpa",
    "reported_space_group_symbol",
    "state_kind",
    "temperature_value_k",
    "magnetic_field_t",
)


def state_paths(associations=()):
    keys = set(STATE_INPUTS)
    # 核处理仅在来源明确限定了该字段适用范围时成为依赖。
    if any((a.get("scope") or {}).get("structure_optimization") for a in associations):
        keys.add("structure_optimization")
    return sorted(keys)


def state_inputs(state, associations=()):
    return {
        k: deepcopy(state[k]) for k in state_paths(associations) if state.get(k) not in (None, "", "unknown")
    }


def record_inputs(record, path):
    """返回相对当前物性记录的直接输入路径，不使用整个条件对象。"""
    payload = record.get("payload") or {}
    parameters = payload.get("parameters") or {}
    dependencies = []
    is_value = path.startswith("value_")
    is_mu = path.startswith("payload.parameters.mu_star") or (
        path.startswith("payload.parameters.extensions.")
        and any(
            path.startswith(f"payload.parameters.extensions.{i}.") and e.get("key") == "mu_star"
            for i, e in enumerate(parameters.get("extensions") or [])
        )
    )
    if is_value or is_mu:
        dependencies.append("method_code")
    if is_value:
        dependencies.extend(
            "payload.parameters." + k for k in ("lambda_ep", "omega_log") if parameters.get(k) is not None
        )
        mu = next(
            (i for i, e in enumerate(parameters.get("extensions") or []) if e.get("key") == "mu_star"), None
        )
        dependencies.append(
            f"payload.parameters.extensions.{mu}." + ("value_max" if path == "value_min" else "value_min")
            if mu is not None and path in {"value_min", "value_max"}
            else "payload.parameters.mu_star"
        )
    elif is_mu:
        dependencies.extend(
            ["value_number"]
            if record.get("value_kind") == "number"
            else (
                ["value_min" if path.endswith(".value_max") else "value_max"]
                if ".extensions." in path
                else ["value_min", "value_max"]
            )
        )
    # λ/ωlog使用本记录所属EPC工作流；不读取结构优化或AIMD阶段。
    if path.startswith(("payload.parameters.lambda_ep", "payload.parameters.omega_log")):
        conditions = payload.get("calculation_conditions") or {}
        dependencies.extend(
            "payload.calculation_conditions." + k
            for k, v in conditions.items()
            if k not in {"extensions", "field_settings"} and v is not None
        )
        for i, e in enumerate(conditions.get("extensions") or []):
            stage = str(e.get("key") or "").split(".")[0]
            if (
                stage == "electron_phonon"
                or stage == "sscha"
                and payload.get("approximation") == "anharmonic"
            ):
                dependencies.append(f"payload.calculation_conditions.extensions.{i}")
    # 网格、截断能等设置只依赖同阶段软件/理论/泛函。
    if path.startswith("payload.calculation_conditions."):
        conditions = payload.get("calculation_conditions") or {}
        if ".extensions." in path:
            try:
                entry = conditions["extensions"][int(path.split(".extensions.")[1].split(".")[0])]
            except (KeyError, IndexError, ValueError):
                entry = {}
            stage = str(entry.get("key") or "").split(".")[0]
            if str(entry.get("key") or "").split(".")[-1] in {
                "calculation_code",
                "electronic_method",
                "exchange_correlation_functional",
            }:
                return []
            dependencies.extend(
                f"payload.calculation_conditions.extensions.{i}"
                for i, e in enumerate(conditions.get("extensions") or [])
                if str(e.get("key") or "").split(".")[0] == stage
                and str(e.get("key") or "").split(".")[-1]
                in {"calculation_code", "electronic_method", "exchange_correlation_functional"}
            )
        else:
            if path.split(".")[-1] in {
                "calculation_code",
                "electronic_method",
                "exchange_correlation_functional",
            }:
                return []
            dependencies.extend(
                "payload.calculation_conditions." + k
                for k in ("calculation_code", "electronic_method", "exchange_correlation_functional")
                if conditions.get(k) is not None
            )
    return sorted(set(dependencies) - {path})


def project_claim(claim, path=None):
    """用于有完整旧断言的有界兼容；不凭同一字段名称授予旧核对资格。"""
    result = deepcopy(claim)
    if "record" in result and "state" in result:
        result["state"] = state_inputs(result["state"])
    elif "context" in result:
        context = result["context"]
        # 旧子项的整套计算条件不能证明新直接输入，需由调用者重建检查。
        context.pop("structure_optimization", None)
    return result


def legacy_leaf_claim(record, state, path, field):
    from .legacy_review_context import review_context
    from .property_field_review import read_path

    context = review_context(record, state, path)
    from .association_review import _legacy_field_binding

    associations = []
    for association in (record.get("payload") or {}).get("source_associations") or []:
        pointer = str(association.get("target_path") or "").strip("/").replace("/", ".")
        if pointer == path or pointer.startswith(path + ".") or path.startswith(pointer + "."):
            associations.append(_legacy_field_binding(record, state, association))
    if associations:
        context["association_dependencies"] = associations
    return {"value": deepcopy(read_path(record, path)), "field": field, "context": context}
