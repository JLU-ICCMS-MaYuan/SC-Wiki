"""将已批准科学来源转换为带归因限定的 RAG 材料。"""
import json


def source_chunk(source):
    result = source.result
    if result.get('required') is False and (result.get('status') != 'supported' or not result.get('current_value')):
        return None
    origin = result.get('provenance') or {}
    quotes = result.get('evidences') or []
    from backend.ingest.scientific_evidence import human_confirmed
    kind = 'human_review' if human_confirmed(result) else 'derived' if origin.get('kind') == 'derived' else 'paper_quote' if quotes else origin.get('kind', 'unknown')
    if kind == 'human_review':
        decision = result['decision']
        attribution = f"管理员人工确认的数据；判断人 ID：{decision['actor_user_id']}；判断理由：{decision['reason']}。论文未直接支持该结论，不能表述为论文报告或 AI 已验证的结论。"
    elif kind == 'contributor_structure':
        attribution = f"提供者提交的数据；论文中未提供明确支持。实际提交者：{origin.get('submitted_by_name') or '未知'}；原始文件：{origin.get('filename') or '未知'}。不得表述为该论文报告的晶体结构或晶格参数。"
    elif kind == 'derived':
        attribution = f"程序派生数据；计算依据：{origin.get('rule') or '见来源记录'}。"
    else:
        attribution = '来源为当前论文及附件的可核验引句。'
    basis = result.get('adopted_basis') or (result.get('decision') or {}).get('basis_kind')
    if basis in {'general_knowledge', 'paper_inference'}:
        attribution = ('建议最初来自通用知识推测。' if basis == 'general_knowledge' else '建议来自根据论文内容的推断。') + attribution
    value = result.get('current_value', result.get('claim', ''))
    content = f"{attribution}\n{result.get('label', source.field_path)}：{json.dumps(value, ensure_ascii=False)}\n"
    content += '\n'.join(f"第 {e.get('page_start') or '未知'} 页：{e.get('quote', '')}" for e in quotes)
    if result.get('resolution'):
        content += '\n审核员裁决说明：' + result['resolution']
    return dict(id=str((1 << 62) + source.id), paper_id=source.paper_id,
                paper_revision=source.paper_revision, source_kind=kind,
                source_id=source.id, attribution=attribution,
                chunk_index=-1, section_name='已审核科学来源', content=content)


def citation(chunk):
    return {k: chunk[k] for k in ('paper_id', 'paper_revision', 'source_kind', 'source_id', 'attribution') if k in chunk}
