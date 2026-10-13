"""生成独立四路表单与来源核对页面，不把未核对候选算正确。"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

from .parsers import write_json

ARMS = ("docling", "mineru", "marker", "complementary")
INTERNAL = {"evidence", "evidences", "sources", "record_key", "module_key", "candidate_id", "basis_kind", "scope",
            "definition_key", "definition_version", "schema_version", "material_state_ref", "status", "validation"}


def leaves(value, prefix="", evidence=None):
    if isinstance(value, dict):
        evidence = value.get("evidences") or value.get("sources") or evidence or []
        for key, child in value.items():
            if key not in INTERNAL:
                yield from leaves(child, f"{prefix}/{key}", evidence)
    elif isinstance(value, list):
        if not value:
            yield prefix, [], evidence or []
        for index, child in enumerate(value):
            yield from leaves(child, f"{prefix}/{index}", evidence)
    else:
        yield prefix, value, evidence or []


def state_identity(state):
    keys = ("material", "reported_space_group_symbol", "pressure_value_gpa", "pressure_min_gpa", "pressure_max_gpa",
            "temperature_value_k", "magnetic_field_t", "state_kind")
    return " | ".join(str(state.get(k) if state.get(k) is not None else "?") for k in keys)


def fields_for(arm, form):
    rows = []

    def add(section, title, key_prefix, path_prefix, obj, evidence=None):
        for path, value, sources in leaves(obj, "", evidence):
            full_path = path_prefix + path
            identity = json.dumps([arm, form.get("attempt"), full_path, value, sources], ensure_ascii=False, sort_keys=True)
            identifier = hashlib.sha256(identity.encode()).hexdigest()[:24]
            rows.append({"id": identifier, "arm": arm, "section": section, "group": title,
                         "path": full_path, "key": key_prefix + path, "value": value, "evidences": sources})
    for name, value in form.get("paper", {}).items():
        add("paper", "论文信息", f"paper/{name}", f"paper/{name}", value, form.get("paper_evidences", {}).get(name, []))
    counts = defaultdict(int)
    for index, state in enumerate(form.get("material_states", [])):
        identity = state_identity(state)
        counts[identity] += 1
        key = f"state/{identity}/occurrence-{counts[identity]}"
        title = f"{state.get('material') or state.get('material_name') or '未命名'} · {state.get('reported_space_group_symbol') or '相未知'} · {state.get('pressure_value_gpa') if state.get('pressure_value_gpa') is not None else state.get('pressure_raw') or '压力未知'} GPa"
        add("state", title, key, f"material_states/{index}", {k: v for k, v in state.items() if k != "property_modules"})
        occurrences = defaultdict(int)
        for mi, module in enumerate(state.get("property_modules", [])):
            for ri, record in enumerate(module.get("records", [])):
                ridentity = "|".join(str(record.get(k) or "?") for k in ("property_code", "record_type", "method_code", "criterion_code"))
                occurrences[ridentity] += 1
                add("record", f"{title} / {record.get('name_raw') or record.get('property_code')} / {record.get('method_code')}",
                    f"{key}/record/{ridentity}/occurrence-{occurrences[ridentity]}",
                    f"material_states/{index}/property_modules/{mi}/records/{ri}", record)
    for index, structure in enumerate(form.get("structure_candidates", [])):
        add("structure", f"结构候选 {index + 1}", f"structure/{index}", f"structure_candidates/{index}", structure)
    return rows


def load_forms(run):
    from .extraction import form_issues
    forms = {}
    for arm in ARMS:
        pointer = run / "extractions" / arm / "latest.json"
        if pointer.exists():
            attempt = json.loads(pointer.read_text())["attempt"]
            forms[arm] = json.loads((pointer.parent / attempt / "form.json").read_text())
            call = pointer.parent / attempt / "call.json"
            forms[arm]["call"] = json.loads(call.read_text()) if call.exists() else None
            # 早期响应仍用当前同一报告规则复核，但不覆盖其原始 form.json。
            validation = forms[arm]["validation"]
            record_valid = validation.get("record_contract_valid", validation.get("contract_valid", False))
            issues = form_issues(forms[arm])
            validation.update(record_contract_valid=record_valid, contract_valid=record_valid and not issues,
                              form_issues=issues, production_ready=False)
        else:
            forms[arm] = {"arm": arm, "status": "not_run", "validation": {}, "paper": {}, "material_states": []}
    return forms


def build_report(run, manifest):
    import pymupdf
    forms = load_forms(run)
    sources, pages, routing = {}, {}, []
    for item in manifest["case"]["files"]:
        with pymupdf.open(item["path"]) as pdf:
            for index, page in enumerate(pdf):
                name = f"pages/{item['file_id']}-{index + 1}.png"
                output = run / name
                output.parent.mkdir(exist_ok=True)
                if not output.exists():
                    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(output)
                pages[f"{item['file_id']}:{index + 1}"] = {"image": name, "width": page.rect.width, "height": page.rect.height}
        for engine in ARMS[:3]:
            path = run / engine / item["file_id"] / "ir.json"
            if path.exists():
                ir = json.loads(path.read_text())
                for block in ir["blocks"]:
                    sources[f"{item['file_id']}:{block['block_id']}"] = {**block, "file_id": item["file_id"], "engine": engine}
        path = run / "complementary" / item["file_id"] / "routing.json"
        if path.exists():
            routing.extend(json.loads(path.read_text()))
    fields = [r for arm, form in forms.items() for r in fields_for(arm, form)]
    comparisons = defaultdict(dict)
    for field in fields:
        comparisons[field["key"]][field["arm"]] = field
    # 缺字段与字段值不同分别可见；此处只统计差异，不判断对错。
    differences = [{"key": key, "fields": arms, "different": len({json.dumps(arms[a]["value"], sort_keys=True, ensure_ascii=False)
                    if a in arms else "__absent__" for a in ARMS}) > 1} for key, arms in comparisons.items()]
    evaluation_path = run / "evaluation.json"
    report = {"schema_version": 1, "run_id": manifest["run_id"], "case": manifest["case"], "parses": manifest.get("parses", []),
              "forms": forms, "fields": fields, "comparisons": differences, "sources": sources, "pages": pages, "routing": routing,
              "evaluation": json.loads(evaluation_path.read_text()) if evaluation_path.exists() else None,
              "limitations": ["科学语义尚需原文核对，模型和定位校验不能代替人工验收。",
                              "三路全量执行用于实验比较，尚未实现生产按需调度。",
                              "按材料、相、条件和记录方法对齐；重复同条件记录及结构候选仍需人工确认对应关系。"]}
    write_json(run / "report.json", report)
    template = Path(__file__).with_name("template.html").read_text()
    payload = json.dumps(report, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (run / "index.html").write_text(template.replace("__REPORT_JSON__", payload), encoding="utf-8")
    print(f"HTML={run / 'index.html'}", flush=True)
