"""同一论文VASP-PBE到QE的有界推断；原子事实保留原软件/阶段。"""
from copy import deepcopy
import re
import unicodedata


RULE = "vasp_pbe_to_qe_v1"
FUNCTIONAL = "exchange_correlation_functional"


def _compact(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", str(value or "")).casefold())


def _pbe(value):
    return _compact(value) in {"pbe", "perdewburkeernzerhof"}


def _software(value):
    value = _compact(value)
    if value in {"vasp", "viennaabinitiosimulationpackage", "viennaabinitiosimulationpackagecode"}:
        return "vasp"
    if value in {"qe", "quantumespresso", "quantumespressopackage"}:
        return "qe"
    return None


def _applies(setting, target):
    from .scientific_context import _scope_matches
    scope = setting.get("scope") or {}
    if not isinstance(scope, dict):
        return False
    material = target["state"].get("material")
    if scope.get("materials") and material not in scope["materials"]:
        return False
    known = {key: value for key, value in scope.items()
             if key in {"material", "pressure_value_gpa", "pressure_min_gpa", "pressure_max_gpa",
                        "reported_space_group_symbol", "structure_optimization", "method_code"}
             and value not in (None, "", "unknown")}
    return _scope_matches({"material": material, **known}, target["state"], target["record"])


def functional_inference_targets(settings, targets):
    """只找需要模型判断的目标，不预先判定可以继承泛函。"""
    values = list(settings.values())
    if not (any(s.get("key") == FUNCTIONAL and _pbe(s.get("value")) for s in values)
            and any(s.get("key") == "calculation_code" and _software(s.get("value")) == "vasp" for s in values)
            and any(s.get("key") == "calculation_code" and _software(s.get("value")) == "qe" for s in values)):
        return set()
    pending = set()
    for key, target in targets.items():
        conditions = target["record"].get("payload", {}).get("calculation_conditions") or {}
        if conditions.get(FUNCTIONAL) not in (None, ""):
            continue
        if conditions.get("calculation_code") and _software(conditions["calculation_code"]) != "qe":
            continue
        if any(s.get("key") == FUNCTIONAL and s.get("stage") == "electron_phonon" and _applies(s, target) for s in values):
            continue
        pending.add(key)
    return pending


def functional_inference_candidates(requests, settings, targets, context):
    """模型选择关系；服务器限定PBE、两端软件、来源、范围和仅补空。"""
    from .scientific_context import located, scientific_fingerprint, _scope_matches
    candidates, gaps = [], []
    if not isinstance(requests, list):
        return [], [{"reason": "functional_inference_invalid"}]
    for request in requests:
        reason = None
        if not isinstance(request, dict):
            gaps.append({"reason": "functional_inference_invalid"})
            continue
        target_id = request.get("target")
        target = targets.get(target_id) if isinstance(target_id, str) else None
        selected = [settings.get(request.get(name)) if isinstance(request.get(name), str) else None
                    for name in ("vasp_software_setting_id", "vasp_functional_setting_id", "qe_software_setting_id")]
        vasp, functional, qe = selected
        if not context.get("complete"):
            reason = "context_incomplete"
        elif not target or not all(selected):
            reason = "functional_inference_source_missing"
        elif (vasp.get("key") != "calculation_code" or _software(vasp.get("value")) != "vasp"
              or qe.get("key") != "calculation_code" or _software(qe.get("value")) != "qe"
              or qe.get("stage") != "electron_phonon" or functional.get("key") != FUNCTIONAL
              or not _pbe(functional.get("value"))
              or functional.get("stage") not in {"structural_relaxation", "electronic_structure"}
              or vasp.get("stage") != functional.get("stage")):
            reason = "functional_inference_source_mismatch"
        elif (not str(request.get("explanation") or "").strip()
              or not _scope_matches(request.get("scope"), target["state"], target["record"])
              or any(not _applies(s, target) or s.get("exceptions") for s in selected)):
            reason = "functional_inference_scope_ambiguous"
        if not reason:
            conditions = target["record"].get("payload", {}).get("calculation_conditions") or {}
            if conditions.get(FUNCTIONAL) not in (None, ""):
                reason = "functional_inference_existing_value"
            elif conditions.get("calculation_code") and _software(conditions["calculation_code"]) != "qe":
                reason = "functional_inference_source_mismatch"
            else:
                for other in settings.values():
                    if other.get("key") != FUNCTIONAL or not _applies(other, target):
                        continue
                    if other.get("stage") == "electron_phonon":
                        reason = "functional_inference_explicit_qe"
                        break
                    if other.get("stage") in {"structural_relaxation", "electronic_structure"} and not _pbe(other.get("value")):
                        reason = "functional_inference_conflict"
                        break
        facts, scopes = [], []
        if not reason:
            for setting in selected:
                for ref in setting.get("fact_evidences") or []:
                    source = located(ref, context["sources"])
                    if not source:
                        reason = "quote_unlocated"
                    elif source not in facts:
                        facts.append(source)
                if not setting.get("fact_evidences"):
                    reason = "quote_unlocated"
            for ref in request.get("scope_evidences") or []:
                source = located(ref, context["sources"])
                if not source:
                    reason = "quote_unlocated"
                elif source not in scopes:
                    scopes.append(source)
            if not scopes:
                reason = "quote_unlocated"
            # 明确PBE才可推断；PBEsol/PBE0不能因子串相同被当作PBE。
            donor_text = " ".join(e.get("quote", "") for e in functional.get("fact_evidences") or [])
            if not (re.search(r"\bpbe\b", donor_text, re.I) or "perdewburkeernzerhof" in _compact(donor_text)):
                reason = "functional_inference_source_missing"
        if reason:
            gaps.append({"target": target_id, "reason": reason, "inference_rule": RULE})
            continue
        candidates.append({
            "target": target_id, "expected_fingerprint": scientific_fingerprint(target["record"]),
            "target_path": "/payload/calculation_conditions/" + FUNCTIONAL,
            "value": "PBE", "stage": "electron_phonon", "basis_kind": "paper_inference",
            "scope": deepcopy(request["scope"]), "fact_evidences": facts, "scope_evidences": scopes,
            "explanation": "QE泛函未直接报告；依据本文VASP-PBE及同一计算流程，推测QE也使用PBE。"
                           + str(request["explanation"]).strip(),
            "reported_value_raw": str(functional.get("reported_value_raw") or functional["value"]),
            "unit_raw": "", "inference_rule": RULE,
            "source_setting_ids": {name: request[name] for name in
                                   ("vasp_software_setting_id", "vasp_functional_setting_id", "qe_software_setting_id")},
        })
    return candidates, gaps
