"""局部草稿写入。只处理存储与并发，不读取来源或核对历史。"""
from copy import deepcopy
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import select
from backend import models


def fail(code, message, status=409):
    raise HTTPException(status, detail={'code': code, 'message': message})


def authorized_draft(session, target, target_id, user, *, lock=False):
    if target == 'upload':
        from .upload_tasks import get_state, get_draft
        state = get_state(target_id)
        if not state or int(state.get('user_id') or 0) != user.id or state.get('is_shadow'):
            fail('draft_forbidden', '无权编辑此草稿', 403)
        if state.get('paper_id'):
            fail('draft_already_submitted', '草稿已提交')
        draft = get_draft(target_id)
        if draft is None:
            fail('draft_not_ready', '草稿不存在或尚未完成解析')
        return draft, None
    if target == 'revision':
        query = select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == target_id)
        saved = session.scalar(query.with_for_update() if lock else query)
        if not saved or saved.owner_id != user.id:
            fail('draft_forbidden', '无权编辑此返修草稿', 403)
        from backend.services.paper_revisions import require_rejected
        paper = session.get(models.Paper, saved.paper_id)
        require_rejected(paper)
        if saved.base_revision != paper.content_revision:
            fail('draft_version_conflict', '论文版本已变化，返修草稿保留')
        return deepcopy(saved.draft), saved
    if target == 'paper' and str(target_id).isdigit():
        query = select(models.Paper).where(models.Paper.id == int(target_id))
        paper = session.scalar(query.with_for_update() if lock else query)
        if not paper or user.role not in {'admin', 'superadmin'} or paper.uploaded_by_user_id == user.id:
            fail('draft_forbidden', '需要管理员权限且不能审核自己的论文', 403)
        from backend.services.paper_revisions import current_draft
        query = select(models.ScientificReviewDraft).where(models.ScientificReviewDraft.paper_id == paper.id)
        staged = session.scalar(query.with_for_update() if lock else query)
        if staged:
            if staged.base_revision != paper.content_revision:
                fail('draft_version_conflict', '正式论文已变化，管理员草稿未覆盖新内容')
            return deepcopy(staged.draft), staged
        return current_draft(session, paper), paper
    fail('draft_target_invalid', '草稿目标无效', 400)


@contextmanager
def target_lock(target, target_id):
    if target == 'upload':
        from .upload_tasks import upload_task_lock
        with upload_task_lock(target_id):
            yield
    else:
        yield


def draft_version(draft):
    from .property_evidence import digest
    return digest({k: v for k, v in draft.items() if k not in {'_field_change_events', '_review_notes', '_review_notes_history'}})


def apply_changes(draft, changes):
    """数组成员按稳定键选择，索引只能作为显示位置；原始编辑文本原样保存。"""
    updated = deepcopy(draft)
    forbidden = {'__proto__', 'constructor', 'prototype', 'field_evidence', 'evidences', 'evidence',
                 'source_associations', 'paper_id', 'review_status', 'uploaded_by_user_id'}
    allowed_roots = {'paper', 'material_states', 'structure_candidates', 'structural_observations'}
    for change in changes:
        path = change.get('path') or []
        if not path or path[0] not in allowed_roots:
            fail('draft_field_invalid', '字段不允许编辑', 400)
        node = updated
        for part in path[:-1]:
            if isinstance(part, dict):
                if set(part) != {'key', 'value'} or part['key'] not in {'state_key', 'module_key', 'record_key', 'field_key', 'candidate_id'}:
                    fail('draft_field_invalid', '字段身份无效', 400)
                matches = [v for v in node if isinstance(v, dict) and v.get(part['key']) == part['value']] if isinstance(node, list) else []
                if len(matches) != 1:
                    fail('draft_field_missing', '字段已移除或身份不唯一')
                node = matches[0]
            elif isinstance(part, str) and part not in forbidden and not part.startswith('_') and isinstance(node, dict):
                node = node.setdefault(part, {})
            else:
                fail('draft_field_invalid', '字段路径无效', 400)
        key = path[-1]
        if not isinstance(key, str) or key in forbidden or key.startswith('_') or not isinstance(node, dict):
            fail('draft_field_invalid', '字段路径无效', 400)
        if node.get(key) != change.get('before'):
            fail('draft_version_conflict', '内容已在其他页面修改，当前输入保留，请重新打开后合并')
        if change.get('remove'):
            node.pop(key, None)
        else:
            node[key] = deepcopy(change.get('value'))
    return updated


def save_fields(session, target, target_id, user, expected_version, changes):
    draft, saved = authorized_draft(session, target, target_id, user, lock=True)
    version = draft_version(draft)
    if expected_version != version:
        fail('draft_version_conflict', '草稿版本已变化，当前输入未被覆盖')
    updated = apply_changes(draft, changes)
    if updated == draft:
        return {'version': version, 'changed': False}
    updated['_field_edit_format'] = 1
    if target == 'upload':
        from .upload_tasks import save_draft
        save_draft(target_id, updated, editor=user, changes=changes)
    elif target == 'revision':
        from .evidence_audit import draft_change_events
        updated['_field_change_events'] = [*(draft.get('_field_change_events') or []),
                                            *draft_change_events(draft, updated, user, changes)]
        saved.draft = updated
        saved.draft_version += 1
        session.flush()
    else:
        from .evidence_audit import draft_change_events
        updated['_field_change_events'] = [*(draft.get('_field_change_events') or []),
                                            *draft_change_events(draft, updated, user, changes)]
        if isinstance(saved, models.Paper):
            saved = models.ScientificReviewDraft(paper_id=saved.id, owner_id=user.id,
                base_revision=saved.content_revision, base_fingerprint=version, draft=updated)
            session.add(saved)
        else:
            saved.draft = updated
            saved.owner_id = user.id
        session.flush()
    return {'version': draft_version(updated), 'changed': True,
            **({'draft_version': saved.draft_version} if target == 'revision' else {})}


def save_note(session, target, target_id, user, item_key, reason, before):
    from datetime import datetime, timezone
    draft, saved = authorized_draft(session, target, target_id, user, lock=True)
    notes = deepcopy(draft.get('_review_notes') or {})
    previous = notes.get(item_key) or {}
    if previous.get('reason', '') != before:
        fail('draft_note_conflict', '字段说明已在其他窗口修改，当前输入保留')
    if previous.get('reason', '') == reason:
        return {'saved': False}
    entry = {'item_key': item_key, 'reason': reason, 'actor_user_id': user.id,
             'created_at': datetime.now(timezone.utc).isoformat()}
    notes[item_key] = entry
    updated = {**draft, '_review_notes': notes,
               '_review_notes_history': [*(draft.get('_review_notes_history') or []), entry]}
    if target == 'upload':
        from .upload_tasks import save_draft
        save_draft(target_id, updated)
    elif target == 'revision':
        saved.draft = updated
    elif isinstance(saved, models.ScientificReviewDraft):
        saved.draft = updated
    else:
        session.add(models.ScientificReviewDraft(paper_id=saved.id, owner_id=user.id,
            base_revision=saved.content_revision, base_fingerprint=draft_version(draft), draft=updated))
    session.flush()
    return {'saved': True}
