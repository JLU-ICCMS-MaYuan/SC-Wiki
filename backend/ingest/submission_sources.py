"""正式保存采用当前字段审核的来源；旧展示引句只保留历史，不冒充原文支持。"""
from copy import deepcopy
import re

from .field_review import valid_field_decision
from .property_evidence import locate_with_reason
from .scientific_drafts import ScientificEvidenceTarget
from .scientific_evidence import item_identity


def reviewed_legacy_targets(targets, checks, draft, chunks):
    """旧空间群/结构入口不再与当前逐字段结果形成第二套门禁。"""
    if checks is None:
        return targets  # 未提供经过门禁的结果时，保留原来的严格定位要求。
    by_field = {row['field']: row for row in checks}
    by_item = {row['item_key']: row for row in checks}
    output, emitted = [], set()
    for target in targets:
        owner = None
        if target.field_path.endswith('.reported_space_group'):
            owner = by_field.get(target.field_path + '_symbol')
        elif target.kind == 'structure' and target.entity.review_key:
            match = re.match(r'material_states\[(\d+)\]', target.field_path)
            if match:
                state = draft['material_states'][int(match[1])]
                owner = by_item.get(item_identity('structure', state['state_key'], target.entity.review_key))
        if not owner or owner.get('status') != 'supported':
            output.append(target)
            continue
        _, old_error = locate_with_reason(target.evidence, chunks)
        if old_error:
            history = owner.setdefault('legacy_source_history', [])
            entry = {'field': target.field_path, 'evidence': deepcopy(target.evidence),
                     'reason': old_error, 'status': 'historical_unlocated'}
            if entry not in history:
                history.append(entry)
        current = owner.get('evidences') or []
        # 人工通过可以保留无原文支持的值，但不能把未定位文字写成已验证 PaperEvidence。
        human = valid_field_decision(owner, owner, 'approve')
        if not current and not human:
            output.append(target)
            continue
        if owner['item_key'] in emitted:
            continue
        emitted.add(owner['item_key'])
        for evidence in current:
            located, error = locate_with_reason(evidence, chunks)
            if error and human:
                history = owner.setdefault('legacy_source_history', [])
                entry = {'field': owner['field'], 'evidence': deepcopy(evidence),
                         'reason': error, 'status': 'historical_unlocated'}
                if entry not in history:
                    history.append(entry)
                continue
            output.append(ScientificEvidenceTarget(target.field_path, located or evidence, target.kind, target.entity))
    return output
