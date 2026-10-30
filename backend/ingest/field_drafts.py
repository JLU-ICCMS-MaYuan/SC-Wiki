"""局部草稿写入。只处理存储与并发，不读取来源或核对历史。"""
from copy import deepcopy
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import select
from backend import models


def fail(code, message, status=409):
    raise HTTPException(status, detail={'code': code, 'message': message})


def authorized_draft(session, target, target_id, user, *, lock=False, allow_new_cycle=False):
    if target == 'upload':
        from .upload_tasks import get_state, get_draft, authoritative_state
        state = authoritative_state(target_id,session) or get_state(target_id)
        if not state or int(state.get('user_id') or 0) != user.id or state.get('is_shadow'):
            fail('draft_forbidden', '无权编辑此草稿', 403)
        if state.get('paper_id'):
            fail('draft_already_submitted', '草稿已提交')
        from backend.services.workdrafts import row, require
        work = row(session,target,target_id,lock)
        if work is not None:
            require(session,target,target_id,user)
            from .tc_contexts import map_draft
            return map_draft(work.body), None
        draft = get_draft(target_id)
        if draft is None:
            fail('draft_not_ready', '草稿不存在或尚未完成解析')
        return draft, None
    if target == 'revision':
        query = select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == target_id)
        saved = session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
        if not saved or saved.owner_id != user.id:
            fail('draft_forbidden', '无权编辑此返修草稿', 403)
        from backend.services.workdrafts import require
        require(session,target,target_id,user)
        from backend.services.paper_revisions import require_rejected
        paper = session.get(models.Paper, saved.paper_id)
        require_rejected(paper, session=session, user=user)
        from backend.services.manuscript_handoffs import require_writer
        require_writer(session,paper,user,author=True)
        if saved.base_revision != paper.content_revision:
            fail('draft_version_conflict', '论文版本已变化，返修草稿保留')
        from .tc_contexts import map_draft
        return map_draft(saved.draft), saved
    if target == 'paper' and str(target_id).isdigit():
        query = select(models.Paper).where(models.Paper.id == int(target_id))
        paper = session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
        if not paper or user.role not in {'admin', 'superadmin'} or paper.uploaded_by_user_id == user.id:
            fail('draft_forbidden', '需要管理员权限且不能审核自己的论文', 403)
        from backend.services.manuscript_handoffs import require_writer
        require_writer(session,paper,user)
        from backend.services.workdrafts import row, require, cycle
        work = row(session,target,target_id,lock)
        if work is not None:
            if work.document_key == cycle(session,target,target_id):
                require(session,target,target_id,user)
            elif not allow_new_cycle:
                fail('workdraft_ended','此页面属于已结束的工作稿，请重新打开')
        from backend.services.paper_revisions import current_draft
        query = select(models.ScientificReviewDraft).where(models.ScientificReviewDraft.paper_id == paper.id)
        staged = session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
        if staged:
            if staged.owner_id != user.id:
                from backend.services.manuscript_handoffs import latest
                state = latest(session, paper.id)
                queued = state and state['holder'] == 'review' and staged.owner_id == state['actor_user_id']
                if not queued:
                    fail('workdraft_claimed', '工作稿已由其他审核员接手；可查看已交出快照')
                if lock and not allow_new_cycle:
                    staged.owner_id = user.id
                    session.flush()
            if staged.base_revision != paper.content_revision:
                fail('draft_version_conflict', '正式论文已变化，管理员草稿未覆盖新内容')
            from .tc_contexts import map_draft
            return map_draft(staged.draft), staged
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
    return digest({k: v for k, v in draft.items() if k not in {'_field_change_events', '_field_baselines', '_review_notes', '_review_notes_history'}})


IDENTITY_KEYS = ("state_key", "module_key", "record_key", "field_key", "candidate_id")
FORBIDDEN = {"__proto__", "constructor", "prototype", "field_evidence", "evidences", "evidence",
             "source_associations", "tc_context_ref", "tc_contexts", "paper_id", "review_status", "uploaded_by_user_id", "approved_revision"}
ROOTS = {"paper", "material_states", "structure_candidates", "structural_observations"}


def _identity_key(before, after):
    rows = [*before, *after]
    return next((key for key in IDENTITY_KEYS if rows and all(
        isinstance(row, dict) and isinstance(row.get(key), str) and row[key] for row in rows)
        and all(len({row[key] for row in values}) == len(values) for values in (before, after))), None)


def changed_leaves(before, after, path):
    """旧对象载荷也按实际差异展开，绝不把未修改旧值整包写回。"""
    if before == after:
        return []
    if isinstance(after, dict) and (before is None or isinstance(before, dict)):
        previous = before or {}
        changes = []
        for key in dict.fromkeys([*previous, *after]):
            if key not in after:
                changes.append({"path": [*path, key], "remove": True})
            else:
                changes.extend(changed_leaves(previous.get(key), after[key], [*path, key]))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        key = _identity_key(before, after)
        if key:
            old = {row[key]: row for row in before}
            new = {row[key]: row for row in after}
            changes = [{"op": "remove_item", "path": path, "identity": {"key": key, "value": item}}
                       for item in old if item not in new]
            for index, row in enumerate(after):
                item = row[key]
                if item not in old:
                    changes.append({"op": "insert", "path": path, "key": key, "value": row,
                                    "after": after[index - 1][key] if index else None})
                else:
                    changes.extend(changed_leaves(old[item], row, [*path, {"key": key, "value": item}]))
            if [row[key] for row in before] != [row[key] for row in after]:
                changes.append({"op": "reorder", "path": path, "key": key, "order": [row[key] for row in after]})
            return changes
    return [{"path": path, "value": deepcopy(after)}]


def _node(updated, path):
    node, owner = updated, None
    for part in path:
        if isinstance(part, dict):
            if set(part) != {"key", "value"} or part["key"] not in IDENTITY_KEYS:
                fail("draft_field_invalid", "字段身份无效", 400)
            matches = [row for row in node if isinstance(row, dict) and row.get(part["key"]) == part["value"]] if isinstance(node, list) else []
            if len(matches) != 1:
                fail("draft_field_missing", "字段已移除或身份不唯一")
            node = matches[0]
            if part["key"] == "record_key":
                owner = node
        elif isinstance(part, str) and part not in FORBIDDEN and not part.startswith("_") and isinstance(node, dict):
            node = node.setdefault(part, {})
        else:
            fail("draft_field_invalid", "字段路径无效", 400)
    return node, owner


def _structural_change(updated, change):
    rows, _ = _node(updated, change["path"])
    if not isinstance(rows, list):
        fail("draft_field_invalid", "结构操作目标必须是现有列表", 400)
    operation = change["op"]
    identity = change.get("identity") or {}
    key = identity.get("key") if operation == "remove_item" else change.get("key")
    if key not in IDENTITY_KEYS:
        fail("draft_field_invalid", "列表缺少稳定身份", 400)
    if operation == "remove_item":
        item = identity.get("value")
        matches = [row for row in rows if row.get(key) == item]
        if len(matches) > 1:
            fail("draft_field_missing", "删除目标身份不唯一")
        rows[:] = [row for row in rows if row.get(key) != item]
    elif operation == "insert":
        value = change.get("value")
        if not isinstance(value, dict) or not isinstance(value.get(key), str) or not value[key]:
            fail("draft_field_invalid", "新增对象必须有稳定身份", 400)
        existing = next((row for row in rows if row.get(key) == value[key]), None)
        if existing is not None:
            if existing != value:
                fail("draft_field_exists", "新增对象身份已存在，未覆盖当前内容")
            return
        anchor = change.get("after")
        position = 0 if anchor is None else next((i + 1 for i, row in enumerate(rows) if row.get(key) == anchor), len(rows))
        rows.insert(position, deepcopy(value))
    elif operation == "reorder":
        order = change.get("order")
        if not isinstance(order, list) or len(order) != len(set(order)) or any(not isinstance(item, str) for item in order):
            fail("draft_field_invalid", "排序身份无效", 400)
        by_id = {row.get(key): row for row in rows}
        ordered = iter(by_id[item] for item in order if item in by_id)
        requested = set(order)
        rows[:] = [next(ordered) if row.get(key) in requested else row for row in rows]
    else:
        fail("draft_field_invalid", "未知结构操作", 400)


def apply_changes(draft, changes):
    """同经手人按实际变化后保存覆盖；存在性、归属及科学核对门另行保持。"""
    updated = deepcopy(draft)
    normalized = []
    for change in changes:
        path = change.get("path") or []
        if not path or path[0] not in ROOTS:
            fail("draft_field_invalid", "字段不允许编辑", 400)
        if change.get("op") in {"insert", "remove_item", "reorder"}:
            normalized.append(change)
        elif change.get("remove"):
            normalized.append(change)
        elif isinstance(change.get("value"), (dict, list)):
            normalized.extend(changed_leaves(change.get("before"), change["value"], path))
        else:
            normalized.append(change)
    affected_methods, affected_parameters = {}, {}
    for change in normalized:
        path = change["path"]
        if change.get("op") in {"insert", "remove_item", "reorder"}:
            _structural_change(updated, change)
            continue
        node, owner = _node(updated, path[:-1])
        key = path[-1]
        if not isinstance(key, str) or key in FORBIDDEN or key.startswith("_") or not isinstance(node, dict):
            fail("draft_field_invalid", "字段路径无效", 400)
        if change.get("remove"):
            node.pop(key, None)
        else:
            node[key] = deepcopy(change.get("value"))
        from .calculation_methods import method_field_issue
        method_issue = method_field_issue(key, node.get(key))
        if key in {"value_raw", "value_text"} and node.get("key"):
            method_issue = method_field_issue("extension", node)
        if method_issue:
            fail("method_category_mismatch", method_issue, 400)
        parameter = str(node.get("key") or "").rsplit(".", 1)[-1] if key in {"value_raw", "value_text"} else key
        if "method_scope" in path:
            parameter = "method_scope"
        if owner is not None and parameter in {"phonon_method", "vibrational_treatment", "method_scope", "calculation_conditions"}:
            affected_methods[id(owner)] = owner
            affected_parameters.setdefault(id(owner), set()).add(parameter)
        if key == "structure_optimization_details":
            from .material_state_contract import optimization_details
            try:
                optimization_details(node.get(key) or {})
            except ValueError as exc:
                fail("invalid_optimization_details", str(exc), 400)
    from .calculation_methods import record_method_issue
    for identity, record in affected_methods.items():
        parameters = affected_parameters[identity]
        candidate = record
        if "calculation_conditions" not in parameters:
            conditions = (record.get("payload") or {}).get("calculation_conditions") or {}
            relevant = {"phonon_method", "vibrational_treatment"} if "method_scope" in parameters else parameters
            selected = {key: deepcopy(conditions[key]) for key in relevant if key in conditions}
            selected["method_scope"] = deepcopy(conditions.get("method_scope") or {})
            selected["extensions"] = [deepcopy(e) for e in conditions.get("extensions") or []
                if str(e.get("key") or "").rsplit(".", 1)[-1] in relevant]
            candidate = {**record, "payload": {"calculation_conditions": selected}}
        issue = record_method_issue(candidate, check_legacy=False)
        if issue:
            fail("method_scope_mismatch", issue, 400)
    return updated


def save_fields(session, target, target_id, user, expected_version, changes, *, field_scope=False):
    draft, saved = authorized_draft(session, target, target_id, user, lock=True)
    from backend.services import workdrafts
    epoch, _, content_version = expected_version.partition(':')
    lease = workdrafts.require(session, target, target_id, user, epoch if content_version else None)
    if lease is not None and not content_version:
        fail('workdraft_epoch_required', '请重新打开稿件以取得当前工作稿凭证')
    version = draft_version(draft)
    # 内容版本不是同经手人覆盖拒绝门；工作稿周期和权限由独立租约检查。
    updated = apply_changes(draft, changes)
    if updated == draft:
        return {'version': (lease.write_epoch + ':' if lease else '') + version, 'changed': False}
    if lease is None:
        lease=workdrafts.open_draft(session,target,target_id,user)
        draft,saved=authorized_draft(session,target,target_id,user,lock=True)
        updated=apply_changes(draft,changes)
    updated['_field_edit_format'] = 1
    from .tc_contexts import map_draft
    if target == 'upload':
        from .upload_tasks import save_draft
        save_draft(target_id, updated, editor=user, changes=changes, work_session=session)
    elif target == 'revision':
        from .evidence_audit import draft_change_events
        from .evidence_audit import update_field_baselines
        update_field_baselines(updated,draft_change_events(draft,updated,user,changes))
        saved.draft = map_draft(updated, compact=True)
        saved.draft_version += 1
        session.flush()
    else:
        from .evidence_audit import draft_change_events
        from .evidence_audit import update_field_baselines
        update_field_baselines(updated,draft_change_events(draft,updated,user,changes))
        if isinstance(saved, models.Paper):
            saved = models.ScientificReviewDraft(paper_id=saved.id, owner_id=user.id,
                base_revision=saved.content_revision, base_fingerprint=version, draft=map_draft(updated, compact=True))
            session.add(saved)
        else:
            saved.draft = map_draft(updated, compact=True)
            saved.owner_id = user.id
        session.flush()
    lease = workdrafts.touch(session, target, target_id, user, updated)
    return {'version': lease.write_epoch + ':' + draft_version(updated), 'revision': lease.revision, 'changed': True,
            **({'draft_version': saved.draft_version} if target == 'revision' else {})}


def save_note(session, target, target_id, user, item_key, reason, before):
    from .tc_contexts import map_draft
    from datetime import datetime, timezone
    draft, saved = authorized_draft(session, target, target_id, user, lock=True)
    notes = deepcopy(draft.get('_review_notes') or {})
    previous = notes.get(item_key) or {}
    if previous.get('reason', '') == reason:
        return {'saved': False}
    from backend.services import workdrafts
    if workdrafts.row(session,target,target_id) is None:
        workdrafts.open_draft(session,target,target_id,user)
        draft,saved=authorized_draft(session,target,target_id,user,lock=True)
        notes=deepcopy(draft.get('_review_notes') or {})
    entry = {'item_key': item_key, 'reason': reason, 'actor_user_id': user.id,
             'created_at': datetime.now(timezone.utc).isoformat()}
    notes[item_key] = entry
    updated = {**draft, '_review_notes': notes}
    if target == 'upload':
        from .upload_tasks import save_draft
        save_draft(target_id, updated, work_session=session)
    elif target == 'revision':
        saved.draft = map_draft(updated, compact=True)
    elif isinstance(saved, models.ScientificReviewDraft):
        saved.draft = map_draft(updated, compact=True)
    else:
        session.add(models.ScientificReviewDraft(paper_id=saved.id, owner_id=user.id,
            base_revision=saved.content_revision, base_fingerprint=draft_version(draft), draft=updated))
    from backend.services.workdrafts import touch
    touch(session, target, target_id, user, updated)
    session.flush()
    return {'saved': True}
