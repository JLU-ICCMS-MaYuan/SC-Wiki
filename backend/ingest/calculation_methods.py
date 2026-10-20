"""计算方法的字段语义：只阻止明确类别错置，不限定电子理论白名单。"""
from copy import deepcopy
import re
import unicodedata


METHOD_SEMANTICS_PROMPT = """
CALCULATION METHOD SEMANTICS: electronic_method means the underlying electronic-structure
theory, e.g. DFT (density functional theory), HF (Hartree-Fock), or another reported theory.
DFPT (density functional perturbation theory), finite displacement and frozen phonon are
phonon/response methods, NEVER electronic_method. Extract them as key=phonon_method in the
appropriate phonon/EPC stage; in record payloads use calculation_conditions.extensions with
key=electron_phonon.phonon_method, value_kind=text and value_raw as reported.
PBE/LDA/GGA/HSE are exchange-correlation functionals/approximations, not the electronic
theory field. Quantum ESPRESSO/VASP are calculation_code, not a method or functional.
If a sentence mentions software and DFPT, extract the software AND phonon_method separately.
Separate mixed descriptions into their fields. Do not silently replace DFPT with DFT:
only extract electronic_method when supported by an applicable source, otherwise leave it
unknown. Never borrow a structural-relaxation functional/method for EPC without scope evidence.
Exception only in the separate association stage: a validated VASP-PBE / QE workflow may propose
QE PBE as paper_inference when QE omits its functional. Never invent this as a directly reported
QE atomic setting during extraction; explicit QE settings, conflicts and existing values take priority.
When reviewing evidence, matching a word in the source is insufficient: its scientific
category and calculation stage must match the target field as well.
"""


def _text(value):
    if isinstance(value, dict):
        value = value.get("value_text") or value.get("value_raw") or value.get("value") or ""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("\u00ad", "")
    return re.sub(r"[-‐‑–—_\s]+", " ", text).strip()


def electronic_method_issue(value):
    text = _text(value)
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
    return None


def condition_method_issue(conditions):
    if not isinstance(conditions, dict):
        return None
    issue = electronic_method_issue(conditions.get("electronic_method"))
    if issue:
        return issue
    for extension in conditions.get("extensions") or []:
        issue = method_field_issue("extensions", extension)
        if issue:
            return issue
    return None


def record_method_issue(record):
    return condition_method_issue((record.get("payload") or {}).get("calculation_conditions"))


def review_method_issue(record, values=None):
    """用于当前值、候选和旧核对；叶子核对不连带否定其他科学字段。"""
    values = values or {}
    if record.get("kind") == "property":
        candidate = deepcopy((record.get("claim") or {}).get("record") or {})
        candidate.update(values)
        return record_method_issue(candidate)
    value = values.get("", record.get("current_value"))
    path = record.get("record_field") or record.get("field", "")
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
