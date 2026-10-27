"""只从当前材料状态提取同条件参考和可核验原胞；不让读图模型猜模式数。"""
from __future__ import annotations
from collections import Counter
import math
from .contracts import fingerprint, conventional_structure_text


def reference_choices(state):
    if not state:
        return {}, {k:"当前材料没有可用论文参考" for k in ("lambda","omega_log")}
    references = {"lambda": [], "omega_log": []}
    for module in state.get("property_modules") or []:
        for record in module.get("records") or []:
            payload = record.get("payload") or {}
            parameters = payload.get("parameters") or {}
            evidence = record.get("evidences") or ([record["evidence"]] if record.get("evidence") else [])
            source = next((e for e in evidence if isinstance(e, dict) and e.get("quote") and
                           (e.get("page") or e.get("page_start") or e.get("section"))), None)
            if source is None:
                continue
            conditions=payload.get("calculation_conditions") or {}
            if any(conditions.get(k) is not None and state.get(k) is not None and
                   str(conditions[k]) != str(state[k]) for k in
                   ("pressure_value_gpa", "temperature_value_k", "reported_space_group_symbol")):
                continue
            for name, keys in (("lambda", ("lambda", "lambda_ep")), ("omega_log", ("omega_log", "omega_log_k"))):
                raw = next((parameters[k] for k in keys if k in parameters), None)
                value = raw.get("value_number") if isinstance(raw, dict) else raw
                if record.get("property_code") in keys:
                    value = record.get("value_number")
                if isinstance(value, (float, int)) and not isinstance(value,bool) and math.isfinite(value):
                    references[name].append(dict(value=float(value), source=source, same_conditions=True,
                        record_key=record.get("record_key"), method=record.get("method_code")))
    values, reasons = {}, {}
    for key, choices in references.items():
        if not choices:
            reasons[key]="缺少同条件、可定位的论文"+("λ" if key=="lambda" else "ωlog")
        elif len({(v["value"],v["method"]) for v in choices})!=1:
            reasons[key]="同条件存在多个不同的"+("λ" if key=="lambda" else "ωlog")+"参考，尚未确定唯一输入"
        else:
            values[key]=choices[0]
    return values,reasons


def references_for(state):
    return reference_choices(state)[0]


def composition_for(state):
    """化学式只提供元素比例，不推断原胞倍数或原胞 N。"""
    formula = (state or {}).get("material")
    if not isinstance(formula, str) or not formula.strip():
        return None
    from pymatgen.core import Composition
    try:
        counts = Composition(formula, strict=True).get_el_amt_dict()
    except (ValueError, TypeError):
        return None
    if not counts or any(not math.isfinite(v) or v <= 0 for v in counts.values()):
        return None
    return dict(species_counts=counts, source=dict(kind="material_formula", formula=formula,
                                                  state_key=state.get("state_key")))


def primitive_for(state, draft):
    if not state:
        return None
    source = state.get("structure")
    if not isinstance(source, dict) or not source.get("structure_text"):
        states=draft.get("material_states") or []
        index=next((i for i,s in enumerate(states) if (s.get("state_key") or f"state-{i+1}")==state.get("state_key")),None)
        candidates=[c for c in draft.get("structure_candidates") or [] if c.get("confirmation")=="confirmed"
                    and c.get("material_state_ref")==f"material_states[{index}]"]
        # 多个不同结构对应一个材料条件时不能任意选取模式数来源。
        sources=[]
        for c in candidates:
            text=conventional_structure_text(c)
            if text:sources.append(dict(structure_format="cif",structure_text=text,evidence=c.get("sources")))
        if len({s["structure_text"] for s in sources})!=1:
            return None
        source=sources[0]
    from backend.services.structure_candidates import read_atoms
    import spglib
    try:
        atoms = read_atoms(source.get("structure_format") or "cif", source["structure_text"])
        p = spglib.find_primitive((atoms.cell.array, atoms.get_scaled_positions(), atoms.numbers), symprec=1e-4)
        if p is None:
            return None
        from ase.data import chemical_symbols
        return dict(primitive_atoms=len(p[2]), species_counts=dict(Counter(chemical_symbols[z] for z in p[2])),
                    structure_hash=fingerprint(source), method="ASE/spglib", symprec_angstrom=1e-4,
                    source=source.get("evidence"))
    except (ValueError, TypeError, RuntimeError):
        return None
