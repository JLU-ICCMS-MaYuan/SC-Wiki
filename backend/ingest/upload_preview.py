"""上传阶段只读快照。题录和科学区域分别更新，不写可编辑草稿。"""
from copy import deepcopy

PHASES = ('assembling', 'organizing', 'reviewing', 'saving')


def publish_preview(task_id, *, paper=None, states=None, phase='reviewing', read=None, write=None):
    from .upload_tasks import get_state, update_state
    state = (read or get_state)(task_id) or {}
    if state.get('status') not in {'queued', 'extracting', 'reading', 'summarizing'}:
        return
    previous = state.get('partial_draft') or {}
    preview = {'paper': {**deepcopy(previous.get('paper') or {}), **deepcopy(paper or {})},
               'material_states': deepcopy(previous.get('material_states') or []) if states is None else deepcopy(states)}
    if state.get('_parsing_workflow'):
        preview['_parsing_workflow'] = deepcopy(state['_parsing_workflow'])
    old_phase = state.get('preview_phase')
    if old_phase in PHASES and PHASES.index(old_phase) > PHASES.index(phase):
        phase = old_phase
    (write or update_state)(task_id, partial_draft=preview, preview_phase=phase)
