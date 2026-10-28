"""从正式提交历史读取作者角色及待确认分类；不自动创建目录项。"""
from copy import deepcopy
from sqlalchemy import select
from backend import models

AUTHOR_ROLES = ('co_first_authors', 'corresponding_authors')


def submitted_metadata(session, paper):
    newer = []
    rows = session.scalars(select(models.PaperHistoryEvent).where(
        models.PaperHistoryEvent.paper_id == paper.id,
        models.PaperHistoryEvent.paper_revision <= paper.content_revision,
    ).order_by(models.PaperHistoryEvent.id.desc()))
    for event in rows:
        payload = event.classification_snapshot or {}
        saved = payload.get('revision_submission') or payload.get('upload_submission')
        if saved:
            result = deepcopy(saved)
            result['_changed_fields'] = set()
            for changes in reversed(newer):
                for change in changes:
                    result['_changed_fields'].add(change.get('field'))
                    for name in AUTHOR_ROLES:
                        if change.get('field') == 'paper.' + name:
                            result.setdefault('paper', {})[name] = change.get('after_value') or []
            return result
        newer.append(payload.get('field_changes') or [])
    return {}


def pending_selections(metadata, field, current, saved):
    if field in metadata.get('_changed_fields', set()):
        return current
    names = {str(item.get('name') or '') for item in current}
    return [*current, *[deepcopy(item) for item in saved or [] if item.get('status') == 'pending'
                       and item.get('id') is None and item.get('name') not in names]]
