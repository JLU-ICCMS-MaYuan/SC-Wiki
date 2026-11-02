"""计算方法的字段语义：只阻止明确类别错置，不限定电子理论白名单。"""
from copy import deepcopy
import re
import unicodedata

from .vibrational_terms import canonical_vibrational_wording


from .fixed_form_contract import MODEL_PROMPT
METHOD_SEMANTICS_PROMPT = MODEL_PROMPT + """
electronic_method is the electronic theory (DFT, HF, DFT+U), not DFPT or software.
phonon_method is the reported phonon/response method (DFPT, finite displacement, SSCHA);
vibrational_treatment is the reported physical vibrational treatment, not electronic theory.
Preserve original wording and each field's exact source. Never infer quantum treatment from 0 K.

For vibrational_treatment only, the reported phrase "harmonic approximation" has the canonical
value "harmonic". Preserve the exact original wording in evidence quotes; do not rewrite quotes.
Do not infer this value from DFT, DFPT, software, or 0 K, and do not discard extra physical qualifiers.
"""


def _text(value):
    if isinstance(value, dict):
        value = value.get("value_text") or value.get("value_raw") or value.get("value") or ""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("\u00ad", "")
    return re.sub(r"[-‐‑–—_\s]+", " ", text).strip()


def electronic_method_issue(value):
    text = _text(value)
    if re.search(r"\b(?:harmonic|anharmonic|quasi harmonic|sscha|qha)\b|简谐|非谐|准简谐", text):
        return "振动处理或SSCHA不能作为电子结构理论；请分别记录电子理论、声子技术和振动处理层次。"
    if re.search(r"\bdfpt\b|density functional perturbation|finite displacement|frozen phonon|密度泛函微扰|有限位移|冻结声子", text):
        return "DFPT／有限位移等属于声子或响应方法，请单独记录；电子结构方法应按原文填写DFT、HF等理论，不能直接替换或猜测。"
    if re.fullmatch(r"(?:quantum espresso|qe|vasp|abinit|quantum espresso software)(?:\s+v?[\d.]+)?", text):
        return "软件名称应填写计算软件，不能作为电子结构方法。"
    if re.fullmatch(r"(?:pbe(?:sol|0)?|lda|lsda|gga|meta gga|scan|rscan|r2scan|hse(?:03|06)?|b3lyp|perdew burke ernzerhof)", text):
        return "泛函或交换关联近似应填写交换关联泛函，不能单独作为电子结构方法。"
    return None


def method_field_issue(path, value):
    path = str(path).replace("/", ".")
    if path.rsplit(".", 1)[-1] == "electronic_method":
        return electronic_method_issue(value)
    if isinstance(value, dict) and str(value.get("key") or "").rsplit(".", 1)[-1] == "electronic_method":
        return electronic_method_issue(value)
    key = str(value.get("key") or "").rsplit(".", 1)[-1] if isinstance(value, dict) else path.rsplit(".", 1)[-1]
    text = _text(value)
    if key == "approximation" and re.search(r"\bdft\b|\bdfpt\b|\bhf\b|hartree|density functional|电子结构", text):
        return "历史approximation混入了电子理论或声子技术，请分别填写；保留旧值，不按字符串迁移。"
    if key == "phonon_method" and (re.fullmatch(r"dft|hf|hartree fock|density functional theory", text)
            or re.search(r"\bharmonic\b|\banharmonic\b|简谐近似|非谐近似", text)
            and not re.search(r"self consistent harmonic|\bsscha\b|自洽谐", text)):
        return "声子计算技术应与电子理论、振动处理层次分开。"
    if key == "vibrational_treatment" and text:
        canonical = canonical_vibrational_wording(text)
        if canonical in {"unknown", "harmonic", "quasi harmonic", "anharmonic",
                         "anharmonic quantum", "anharmonic classical", "简谐", "准简谐", "量子非谐", "经典非谐"}:
            return None
        if re.search(r"\bdft\b|\bdfpt\b|\bhf\b|hartree|density functional|电子结构", text):
            return "振动处理层次不能填写DFT、HF、DFPT等电子理论或响应技术。"
        return "未识别的振动处理层次写法；请按原文核对规范表达，不要改成另一种物理近似。"
    return None


def condition_method_issue(conditions):
    if not isinstance(conditions, dict):
        return None
    issue = electronic_method_issue(conditions.get("electronic_method"))
    if issue:
        return issue
    for key in ("phonon_method", "vibrational_treatment"):
        issue = method_field_issue(key, conditions.get(key))
        if issue:
            return issue
    for extension in conditions.get("extensions") or []:
        issue = method_field_issue("extensions", extension)
        if issue:
            return issue
    return None


def record_method_issue(record, *, check_legacy=True):
    conditions = (record.get("payload") or {}).get("calculation_conditions") or {}
    issue = condition_method_issue(conditions)
    if issue:
        return issue
    if check_legacy:
        issue = method_field_issue("approximation", (record.get("payload") or {}).get("approximation"))
        if issue:
            return issue
    # 科学适用性由当前字段原文核对；不再要求额外的method_scope。
    return None


def review_method_issue(record, values=None):
    """用于当前值、候选和旧核对；叶子核对不连带否定其他科学字段。"""
    values = values or {}
    if record.get("kind") == "property":
        candidate = deepcopy((record.get("claim") or {}).get("record") or {})
        candidate.update(values)
        return record_method_issue(candidate)
    value = values.get("", record.get("current_value"))
    path = record.get("record_field") or record.get("field", "")
    validation = record.get("validation_record") or {}
    if path == "payload.approximation" and validation.get("property_code") in {"band_gap", "dos_fermi"} and value:
        return "历史混装近似标签需按电子理论或明确工作流核对；电子结果数值保持不变。"
    if path.endswith((".calculation_context", ".calculation_conditions")):
        return condition_method_issue(value)
    return method_field_issue(path, value)


def validate_extracted_methods(draft):
    """只在新提取入口拒绝错置；不改写历史草稿或用户输入。"""
    for index, state in enumerate(draft.get("material_states") or []):
        issue = condition_method_issue(state.get("calculation_context"))
        if issue:
            raise ValueError(f"material_states[{index}].calculation_context：{issue}")
        for record in state.get("tc_results") or []:
            issue = condition_method_issue(record.get("calculation_context"))
            if issue:
                raise ValueError(f"material_states[{index}].tc_results.calculation_context：{issue}")
        for module in state.get("property_modules") or []:
            for record in module.get("records") or []:
                issue = record_method_issue(record)
                if issue:
                    raise ValueError(f"material_states[{index}].calculation_conditions：{issue}")


def vibrational_treatment(record):
    """只读取当前结果的明确振动层次；旧字段仅作有界兼容，不写回科学值。"""
    payload = record.get("payload") or {}
    conditions = payload.get("calculation_conditions") or {}
    value = conditions.get("vibrational_treatment")
    if value:
        return value
    stages = {"electron_phonon"} if record.get("record_type") == "predicted_tc" else {"electronic_structure"}
    values = {e.get("value_text") or e.get("value_raw") for e in conditions.get("extensions") or []
              if e.get("key") in {stage + ".vibrational_treatment" for stage in stages}}
    if len(values) == 1:
        return next(iter(values))
    legacy = payload.get("approximation")
    return legacy if record.get("record_type") == "predicted_tc" and legacy in {
        "harmonic", "anharmonic", "quasi_harmonic", "anharmonic_quantum", "anharmonic_classical"} else None
