"""计算方法的字段语义：只阻止明确类别错置，不限定电子理论白名单。"""
from copy import deepcopy
import re
import unicodedata

from .vibrational_terms import canonical_vibrational_wording


METHOD_SEMANTICS_PROMPT = """
CALCULATION METHOD SEMANTICS: electronic_method means the underlying electronic-structure
theory, e.g. DFT (density functional theory), HF (Hartree-Fock), or another reported theory.
DFPT (density functional perturbation theory), finite displacement and frozen phonon are
phonon/response methods, NEVER electronic_method. Extract them as key=phonon_method in the
appropriate phonon/EPC stage; in record payloads use calculation_conditions.extensions with
key=electron_phonon.phonon_method, value_kind=text and value_raw as reported.
The field's display name is "phonon method" (声子方法), without an EPC prefix.
calculation_conditions.extensions MUST be an array of objects, for example:
[{"key":"electron_phonon.phonon_method","value_kind":"text","value_raw":"DFPT"}].
Use [] when absent. Never output an object grouped by stage; the stage stays in key.
The EPC calculation_code, electronic_method and exchange_correlation_functional are flat
calculation_conditions fields. Other stages use stage.parameter extension keys.
Never put a known condition under an unqualified extension key (e.g. exchange_correlation_functional).
For phonon_method, preserve the method wording actually reported in value_raw. Do not replace
it with an acronym absent from the source: a reported linear-response method must retain that
wording rather than becoming an unsupported literal "DFPT" claim.
PBE/LDA/GGA/HSE are exchange-correlation functionals/approximations, not the electronic
theory field. Quantum ESPRESSO/VASP are calculation_code, not a method or functional.
If a sentence mentions software and DFPT, extract the software AND phonon_method separately.
Separate mixed descriptions into their fields. A clearly applicable DFPT phonon workflow
may justify electronic_method=DFT by the method definition in the separate association/review stage.
Keep DFPT in phonon_method and record this as an inference, not a direct quotation.
Never infer a functional from DFPT, software defaults, or another software's settings.
VASP-PBE does NOT justify QE-PBE. Require an applicable report for the specific software or leave empty.
When reviewing evidence, matching a word in the source is insufficient: its scientific
category and calculation stage must match the target field as well.

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
    if record.get("property_code") in {"band_gap", "dos_fermi"}:
        vibrational = any(conditions.get(k) for k in ("phonon_method", "vibrational_treatment")) or any(
            str(e.get("key") or "").rsplit(".", 1)[-1] in {"phonon_method", "vibrational_treatment"}
            for e in conditions.get("extensions") or [])
        if vibrational and not electronic_vibration_relation(conditions, record.get("evidences") or []):
            return "普通电子带隙或电子DOS不能继承声子/EPC条件；需明确的电子—声子修正关系及原文依据。"
        legacy = (record.get("payload") or {}).get("approximation")
        if check_legacy and legacy not in (None, "", "unknown"):
            return "历史混装近似字段的科学含义未明确；保留原值和来源，请按电子理论及具体工作流核对。"
    return None


def electronic_vibration_relation(conditions, evidences):
    scope = conditions.get("method_scope") or {}
    if scope.get("relation") != "electron_phonon_renormalization":
        return False
    relations = scope.get("relation_evidences") or []
    def supported(relation):
        quote = str(relation.get("quote") or "").strip()
        return quote and any(quote in str(e.get("quote") or "")
            and all(relation.get(k) is None or relation.get(k) == e.get(k) for k in ("file_id", "block_id"))
            for e in evidences)
    if not relations or not all(supported(e) for e in relations):
        return False
    text = " ".join(str(e.get("quote") or "") for e in relations)
    return bool(re.search(r"band.?gap|electronic.*(?:DOS|density of states)|电子.*(?:带隙|态密度)", text, re.I)
        and re.search(r"phonon|声子", text, re.I)
        and re.search(r"renorm|correct|shift|modify|modified|修正|重整|改变", text, re.I))



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
    if validation.get("property_code") in {"band_gap", "dos_fermi"} and (
            path.endswith((".phonon_method", ".vibrational_treatment")) or isinstance(value, dict)
            and str(value.get("key") or "").rsplit(".", 1)[-1] in {"phonon_method", "vibrational_treatment"}):
        conditions = (validation.get("payload") or {}).get("calculation_conditions") or {}
        candidate = deepcopy(validation)
        candidate["evidences"] = deepcopy(record.get("legacy_evidences") or record.get("evidences") or [])
        candidate["payload"] = {"calculation_conditions": {"method_scope": conditions.get("method_scope") or {}}}
        if isinstance(value, dict):
            candidate["payload"]["calculation_conditions"]["extensions"] = [value]
        else:
            candidate["payload"]["calculation_conditions"][path.rsplit(".", 1)[-1]] = value
        return record_method_issue(candidate)
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

# 新调用采用明确字段；旧approximation不按字符串自动迁移。
METHOD_SEMANTICS_PROMPT += """
PHYSICAL METHOD SCOPE v181: electronic_method is the electronic theory (DFT, HF, DFT+U),
phonon_method is the response/force-constant technique (DFPT, finite displacement, SSCHA or a
reported composite workflow); vibrational_treatment is harmonic, quasi_harmonic, anharmonic,
anharmonic_quantum or anharmonic_classical, as reported, never infer quantum from 0 K.
Store these separately in calculation_conditions; do not generate payload.approximation.
Each condition must belong to this material/phase, stage, workflow and specific result.
method_scope carries physical_object, stage and workflow_id when explicitly known.
Ordinary electronic band_gap/dos_fermi NEVER inherit EPC/phonon approximations. An explicitly
reported electron-phonon renormalization of electronic results is allowed only with
method_scope.relation=electron_phonon_renormalization and exact relation_evidences quotes.
Do not label a phononic band gap or phonon DOS as an electronic result; exclude unsupported
phononic results with their original source. Do not change scientific numbers to fix labels.
No whole-state propagation and no inference of electronic theory, functional or U from
harmonic, finite displacement, SSCHA or a software name. Separate unreported, ambiguous,
conflicting, unreadable and technical-failure cases and preserve their sources.
"""


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
