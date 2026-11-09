"""#227/#211：参考文献标题不能切掉SI后续科学图表，造成前置范围误排。"""
def test_scope_sources_keep_scientific_appendix_after_references(tmp_path, monkeypatch):
    from backend.ingest import upload_tasks
    from backend.ingest.upload_source_bundle import text_sources
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda _task, path: path)
    directory = tmp_path / 'task'; directory.mkdir()
    content = ('Methods and current-paper results.\nReferences\n[1] A referenced work.\n'
               '<!-- page: 6 -->\nFig. S1: Detailed current-paper data.\n'
               'CALIBRATED ORIGINAL FIGURE READING: ScH6 ~100 K at 300 GPa.')
    (directory / 'si.md').write_text(content)
    values = text_sources('task', {'files': [{'file_id': 'si', 'role': 'supplementary',
        'kind': 'pdf', 'original_filename': 'SI.pdf'}]}, tmp_path, trim_references=True)
    assert values[0]['content'] == content
    assert values[0]['role'] == 'supplementary'
