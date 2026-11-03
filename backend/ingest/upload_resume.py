"""只续跑已完成科学核对后中断的自动谱，不重建或覆盖用户草稿。"""
def resume_spectra(task_id):
    from .upload_tasks import get_state, get_draft, update_state
    from .evidence_audit import current_change_events
    state = get_state(task_id) or {}
    # retry是状态迁移参数，会被apply_state_changes消费，不是持久化标志。
    if state.get('status') != 'queued' or state.get('reading_state') != 'extracting_spectra':
        return None
    if current_change_events(state):
        return None
    draft = get_draft(task_id)
    if not draft or draft.get('_form_contract_version') != 1:
        return None
    review = draft.get('model_review_report') or {}
    if ((draft.get('form_filling_report') or {}).get('status') != 'completed'
            or review.get('unfinished_fields') != 0 or review.get('errors')
            or draft.get('field_suggestions_error') or current_change_events(draft)):
        return None
    from .upload_jobs import complete_parsing_state, _schedule_terminal_cleanup
    # #170的新一轮计时从extracting入口开始；随后仍显示实际的汇总/谱阶段。
    update_state(task_id, status='extracting', stage='summarizing', stage_index=4, processing_status='processing',
                 processing_error=None, error_code=None)
    update_state(task_id, status='summarizing', stage='summarizing', processing_status='processing',
                 processing_error=None, error_code=None)
    try:
        result = complete_parsing_state(task_id, draft, include_spectra=True)
    except Exception as exc:
        result = update_state(task_id, status='failed', processing_status='failed',
            processing_error=str(exc), error_code='automatic_spectra_incomplete', failed_stage='spectra')
    _schedule_terminal_cleanup(task_id)
    return result
