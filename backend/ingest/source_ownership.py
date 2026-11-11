"""跨窗口汇总保留原来源身份和归属，不重复发送正文内容。"""


def source_identity_index(sources):
    return [{key: source.get(key) for key in (
        'source_id', 'file_id', 'file_role', 'section_role', 'page_start', 'page_end')}
        for source in sources]
