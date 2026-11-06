"""#225：原引文身份核对、候选约束和持久快照；读页面不运行模型。"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import re
import unicodedata


VERSION = 'citation-matching.v1'
BOOK_FIELDS = ('title', 'doi', 'year', 'authors')
REFERENCE_FIELDS = ('reference_index', 'raw_citation', *BOOK_FIELDS)
SYSTEM = '''核对原始参考文献是否对应给定的库内候选论文，不是判断主题相似性。
仅根据给出的原始引文、题名、作者、年份、DOI判断作品身份。允许排版空格、上下标、连字符和姓名缩写差异；同材料、同年份或作者部分重合不代表同一论文。不能依靠记忆补造引用。证据不足或不对应任何候选时返回paper_id=null。
matches对象的每个键由程序给定，必须逐个填写；paper_id只能取该条给定候选ID或null。不要把引文编号当论文ID。reason用简短中文说明书目信息依据。只输出JSON对象，键名由程序规定。'''


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      separators=(',', ':'), default=str).encode()).hexdigest()


def normalize_doi(value):
    if not isinstance(value, str):
        return None
    value = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value.strip().lower())
    value = re.sub(r'^doi\s*:\s*', '', value)
    return value.strip(' \t\r\n.,;:)]}>"') or None


def normalize_title(value):
    """只兼容书目排版，保留元素与数字，不把全文去空格当作身份规则。"""
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize('NFKC', value).replace('\u00ad', '')
    value = re.sub(r'\bT\s+c\b', 'Tc', value)
    value = re.sub(r'\b([A-Z][a-z]?)\s+(\d+)', r'\1\2', value)
    value = re.sub(r'(\d)\s+(?=[A-Z])', r'\1', value)
    value = re.sub(r'([)\]])\s+(\d)', r'\1\2', value)
    value = re.sub(r'[^\w]+', ' ', value.casefold(), flags=re.UNICODE)
    return ' '.join(value.split())[:512] or None


def authors(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = [value]
    return [str(x) for x in (value or [])] if isinstance(value, list) else []


def author_key(value):
    names = authors(value)
    if not names:
        return None
    name = names[0]
    if ',' in name:
        family, given = name.split(',', 1)
        return (normalize_title(family), (normalize_title(given) or '')[:1])
    parts = re.findall(r'\w+', unicodedata.normalize('NFKC', name).casefold())
    if not parts:
        return None
    if len(parts) > 1 and len(parts[-1]) == 1 and len(parts[0]) > 1:
        return parts[0], parts[-1]
    return parts[-1], parts[0][:1] if len(parts) > 1 else ''


def paper_record(paper):
    return {'paper_id': paper.get('paper_id', paper.get('id')),
            'revision': paper.get('revision', paper.get('content_revision', 1)),
            'title': paper.get('title') or '', 'doi': normalize_doi(paper.get('doi')),
            'year': paper.get('year'), 'authors': authors(paper.get('authors'))}


def paper_signature(paper):
    p = paper_record(paper)
    # #81：引用目标归属论文身份；无关科学内容升版不改变书目身份。
    return fingerprint({'title': normalize_title(p['title']), 'doi': p['doi'], 'year': p['year'],
                        'authors': [normalize_title(name) for name in p['authors']]})


def reference_signature(reference):
    value = {k: reference.get(k) for k in REFERENCE_FIELDS}
    value['doi'] = normalize_doi(value.get('doi'))
    value['authors'] = authors(value.get('authors'))
    value['raw_citation'] = str(value.get('raw_citation') or '').strip()
    value['title'] = str(value['title']).strip() if value.get('title') else None
    return fingerprint(value)


def source_signature(draft):
    paper = draft.get('paper') or {}
    return fingerprint({'paper': {k: paper.get(k) for k in BOOK_FIELDS},
                        'references': [{k: r.get(k) for k in REFERENCE_FIELDS}
                                       for r in (draft.get('citation_extraction') or {}).get('references', [])]})


def snapshot_cache_key(namespace):
    return fingerprint({'version': VERSION, 'snapshot': namespace})


def preserve_matching_snapshot(updated, previous):
    """表单整体保存只能继承服务端快照，不能接收浏览器伪造或丢弃它。"""
    from copy import deepcopy
    updated.pop('citation_matching', None)
    if isinstance(previous.get('citation_matching'), dict):
        updated['citation_matching'] = deepcopy(previous['citation_matching'])


def compatible(reference, candidate):
    if reference.get('year') and candidate.get('year') and reference['year'] != candidate['year']:
        return False
    a, b = author_key(reference.get('authors')), author_key(candidate.get('authors'))
    return not (a and b and (a[0] != b[0] or (a[1] and b[1] and a[1] != b[1])))


def grams(value):
    text = normalize_title(value) or ''
    return {text[i:i + 3] for i in range(max(0, len(text) - 2))}


class CitationCatalog:
    def __init__(self, papers):
        self.papers = {p['paper_id']: p for p in map(paper_record, papers)}
        self.by_doi, self.by_title, self.by_gram = defaultdict(list), defaultdict(list), defaultdict(set)
        for p in self.papers.values():
            if p['doi']:
                self.by_doi[p['doi']].append(p)
            self.by_title[normalize_title(p['title'])].append(p)
            for gram in grams(p['title']):
                self.by_gram[gram].add(p['paper_id'])

    def decide(self, reference, exclude_id=None):
        doi = normalize_doi(reference.get('doi'))
        base = {'paper_id': None, 'method': None, 'reason': '尚未匹配到库内论文',
                'reference_signature': reference_signature(reference), 'candidates': []}
        if doi:
            candidates = [p for p in self.by_doi[doi] if p['paper_id'] != exclude_id]
            if len(candidates) == 1:
                return self.matched(reference, candidates[0], 'doi', 'DOI唯一对应')
            return {**base, 'candidates': candidates, 'reason': 'DOI未命中或对应多个候选'}
        title = normalize_title(reference.get('title') or reference.get('normalized_title'))
        exact_all = [p for p in self.by_title[title] if p['paper_id'] != exclude_id]
        exact = [p for p in exact_all if compatible(reference, p)]
        if title and len(exact) == 1:
            return self.matched(reference, exact[0], 'title_year', '题名排版规范化后唯一对应，作者及年份不冲突')
        if len(exact) > 1:
            return {**base, 'candidates': exact[:5], 'reason': '书目信息对应多个候选'}
        if title and exact_all:
            return {**base, 'candidates': exact_all[:5], 'reason': '题名对应，但提取作者或年份需结合原始引文核对'}
        query = reference.get('title') or reference.get('raw_citation')
        query_title = normalize_title(query) or ''
        counts = Counter(pid for gram in grams(query) for pid in self.by_gram[gram])
        near = []
        for pid, _ in counts.most_common(16):
            p = self.papers[pid]
            if pid == exclude_id or not compatible(reference, p):
                continue
            score = SequenceMatcher(None, query_title, normalize_title(p['title']) or '').ratio()
            if score >= 0.58:
                near.append((score, p))
        near.sort(key=lambda pair: (-pair[0], pair[1]['paper_id']))
        return {**base, 'candidates': [p for _, p in near[:5]]}

    @staticmethod
    def matched(reference, paper, method, reason):
        return {'paper_id': paper['paper_id'], 'method': method, 'reason': reason,
                'reference_signature': reference_signature(reference),
                'candidate_signature': paper_signature(paper), 'paper': paper, 'candidates': []}


def llm2_model_tag():
    from backend.rag.llm_context import catalog_config
    config = catalog_config('LLM2')
    return fingerprint({'catalog_id': config.catalog_id, 'model': config.model, 'endpoint': config.base_url})


def call_llm2(system, user, **options):
    from backend.rag.llm import complete_json, call_phase
    from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
    token = set_llm_config(catalog_config('LLM2'))
    try:
        with call_phase('citation_matching'):
            return complete_json(system, user, **options)
    finally:
        reset_llm_config(token)


def match_references(references, catalog, *, namespace, model=None, cache_get=None, cache_put=None,
                     exclude_id=None, check_cancelled=lambda: None, model_tag=None):
    """一次构造目录；每条决定单独缓存，只有候选发生变化的疑难项重新判断。"""
    memory = {}
    get, put = cache_get or memory.get, cache_put or memory.__setitem__
    decisions, pending = [], []
    for position, reference in enumerate(references):
        decision = catalog.decide(reference, exclude_id)
        decisions.append(decision)
        if decision['paper_id'] is not None or not decision['candidates']:
            continue
        if model_tag is None:
            model_tag = 'injected-model' if model is not None else llm2_model_tag()
        key = fingerprint({'version': VERSION, 'namespace': namespace, 'model': model_tag,
                           'reference': reference_signature(reference),
                           'candidates': [{'paper_id': p['paper_id'], 'identity': paper_signature(p)}
                                          for p in decision['candidates']]})
        cached = get(key)
        if cached and cached.get('state') == 'completed':
            decisions[position] = cached['decision']
        else:
            pending.append((position, reference, decision['candidates'], key))
    for start in range(0, len(pending), 16):
        check_cancelled()
        batch = pending[start:start + 16]
        payload = {'matcher_version': VERSION, 'matching_model_tag': model_tag, 'references': [
            {'reference_index': index, 'reference': {k: ref.get(k) for k in REFERENCE_FIELDS},
             'candidates': candidates} for index, ref, candidates, _ in batch]}
        entries = {str(index): {
                      'type': 'object', 'additionalProperties': False,
                      'properties': {'paper_id': {'type': ['integer', 'null'],
                                                 'enum': [*[p['paper_id'] for p in candidates], None]},
                                     'reason': {'type': 'string', 'minLength': 1}},
                      'required': ['paper_id', 'reason']}
                   for index, _, candidates, _ in batch}
        schema = {'type': 'object', 'additionalProperties': False,
                  'properties': {'matches': {'type': 'object', 'additionalProperties': False,
                                             'properties': entries, 'required': list(entries)}},
                  'required': ['matches']}
        response, raw = None, []
        try:
            response = (model or call_llm2)(SYSTEM, json.dumps(payload, ensure_ascii=False),
                                           response_schema=schema,
                                           on_partial=lambda s: raw.__setitem__(slice(None), [s]))
            import jsonschema
            try:
                jsonschema.validate(response, schema)
            except jsonschema.ValidationError as error:
                raise ValueError('引用匹配结果不符合程序规定的结构') from error
            by_index = response['matches']
            updates = []
            for index, reference, candidates, key in batch:
                answer = by_index[str(index)]
                paper = next((p for p in candidates if p['paper_id'] == answer['paper_id']), None)
                if answer['paper_id'] is not None and paper is None:
                    raise ValueError('引用匹配结果选择了本条候选之外的论文')
                decision = (catalog.matched(reference, paper, 'llm2', answer['reason']) if paper else
                            {**decisions[index], 'reason': answer['reason'], 'candidates': []})
                decision.update(model_catalog_id='LLM2', model_tag=model_tag, cache_key=key)
                updates.append((index, key, decision))
            for index, key, decision in updates:
                put(key, {'state': 'completed', 'decision': decision})
                decisions[index] = decision
        except Exception as error:
            failed_key = fingerprint({'namespace': namespace, 'batch': payload, 'model': model_tag,
                                      'response': response, 'raw': raw[-1] if raw else ''})
            put(failed_key, {'state': 'failed', 'response': response, 'raw_response': raw[-1] if raw else '',
                             'error': type(error).__name__, 'request': payload})
            raise
        check_cancelled()
    return decisions


def load_catalog(session):
    from sqlalchemy import select
    from backend.models import Paper
    return [dict(r._mapping) for r in session.execute(select(
        Paper.id, Paper.title, Paper.doi, Paper.year, Paper.authors, Paper.content_revision,
    ).where(Paper.review_status == 'approved', Paper.approved_revision == Paper.content_revision))]


def related_reference_scope(paper):
    from sqlalchemy import or_
    from backend.models import PaperReference
    conditions = [PaperReference.year == paper.get('year'), PaperReference.year.is_(None)]
    doi = normalize_doi(paper.get('doi'))
    if doi:
        conditions.append(PaperReference.doi == doi)
    title = normalize_title(paper.get('title'))
    if title:
        conditions.append(PaperReference.normalized_title == title)
    return or_(*conditions)


def reusable_incoming(reference, center, cache_get):
    decision = reference.get('match_evidence') or {}
    if decision.get('method') != 'llm2' or not reference.get('cited_paper_id'):
        return None
    if (decision.get('reference_signature') != reference_signature(reference) or
        decision.get('candidate_signature') != paper_signature(center)):
        return None
    cached = cache_get(decision.get('cache_key')) if decision.get('cache_key') else None
    saved = (cached or {}).get('decision') or {}
    if (cached or {}).get('state') != 'completed' or any(saved.get(k) != decision.get(k) for k in
        ('paper_id', 'method', 'reference_signature', 'candidate_signature', 'model_tag', 'reason')):
        return None
    return {**decision, 'paper_id': -1, 'paper': center}


def prepare_upload_matching(draft, namespace, *, session_factory=None, model=None,
                            check_cancelled=lambda: None):
    """网络请求不占有论文事务；每次缓存写入都是独立短事务。"""
    from sqlalchemy import select, or_
    from backend.database import SessionLocal
    from backend.models import Paper, PaperReference, CitationMatchCache
    factory = session_factory or SessionLocal
    with factory() as session:
        papers = load_catalog(session)
        current = CitationCatalog(papers).decide(draft.get('paper') or {})['paper_id']
        applicable = PaperReference.match_status.in_(('unmatched', 'ambiguous'))
        if current is not None:
            applicable = or_(applicable, PaperReference.cited_paper_id == current)
        incoming = [dict(r._mapping) for r in session.execute(select(
            PaperReference.id, PaperReference.paper_id, PaperReference.paper_revision,
            PaperReference.reference_index, PaperReference.raw_citation, PaperReference.title,
            PaperReference.doi, PaperReference.year, PaperReference.authors,
            PaperReference.cited_paper_id, PaperReference.match_method, PaperReference.match_evidence,
        ).join(Paper, Paper.id == PaperReference.paper_id).where(
            Paper.review_status == 'approved', Paper.approved_revision == Paper.content_revision,
            PaperReference.paper_revision == Paper.content_revision,
            related_reference_scope(draft.get('paper') or {}),
            applicable))]

    def get(key):
        with factory() as session:
            row = session.get(CitationMatchCache, key)
            return row.payload if row else None

    def put(key, payload):
        with factory.begin() as session:
            session.merge(CitationMatchCache(cache_key=key, payload=payload))

    extraction = draft.get('citation_extraction') or {}
    references = extraction.get('references') or []
    center = paper_record({**draft.get('paper', {}), 'paper_id': -1})
    catalog = CitationCatalog(papers)
    options = dict(namespace=namespace, model=model, cache_get=get, cache_put=put,
                   check_cancelled=check_cancelled)
    upstream = match_references(references, catalog, **options)
    downstream_decisions = [reusable_incoming(r, center, get) for r in incoming]
    pending_indices = [i for i, d in enumerate(downstream_decisions) if d is None]
    newly_matched = match_references([incoming[i] for i in pending_indices], CitationCatalog([center]), **options)
    for index, decision in zip(pending_indices, newly_matched):
        downstream_decisions[index] = decision
    downstream = []
    seen = set()
    for reference, decision in zip(incoming, downstream_decisions):
        if decision['paper_id'] is None:
            continue
        if reference['paper_id'] in seen:
            continue
        seen.add(reference['paper_id'])
        downstream.append({'paper': catalog.papers[reference['paper_id']],
                           'reference_id': reference['id'], 'paper_revision': reference['paper_revision'],
                           'reference_index': reference['reference_index'],
                           'raw_citation': reference['raw_citation'],
                           'reference_signature': reference_signature(reference), 'decision': decision})
    snapshot = {'version': VERSION, 'status': 'completed' if extraction.get('status') in ('succeeded', 'partial') else 'unavailable',
            'source_signature': source_signature(draft), 'paper': center,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'references': [{**r, 'decision': d, 'matched_paper': d.get('paper')} for r, d in zip(references, upstream)],
            'downstream': sorted(downstream, key=lambda r: r['paper']['paper_id']),
            'parser_status': extraction.get('status'), 'parser_error': extraction.get('error_message')}
    check_cancelled()
    put(snapshot_cache_key(namespace), {'state': 'snapshot', 'snapshot': snapshot})
    return snapshot


def complete_upload_matching(task_id, draft):
    """上传汇总与ready之间的唯一引用阶段入口，复用原执行停止信号。"""
    from backend.ingest.upload_jobs import _ensure_not_cancelled, UploadCancelled
    from backend.ingest.upload_tasks import update_state
    _ensure_not_cancelled(task_id)
    update_state(task_id, citation_matching_status='running')
    try:
        snapshot = prepare_upload_matching(draft, f'upload:{task_id}',
                                          check_cancelled=lambda: _ensure_not_cancelled(task_id))
    except UploadCancelled:
        update_state(task_id, citation_matching_status='cancelled')
        raise
    except Exception:
        update_state(task_id, citation_matching_status='failed')
        raise
    _ensure_not_cancelled(task_id)
    draft['citation_matching'] = snapshot
    update_state(task_id, citation_matching_status=snapshot['status'])
    return snapshot


def read_matching_snapshot(task_id, draft, session_factory=None):
    """只核验实际依赖，不发模型、不重跑候选扫描，不清空其他命中。"""
    from copy import deepcopy
    from sqlalchemy import select, tuple_
    from backend.database import SessionLocal
    from backend.models import Paper, PaperReference, CitationMatchCache
    factory = session_factory or SessionLocal
    with factory() as session:
        snapshot = draft.get('citation_matching')
        if not isinstance(snapshot, dict):
            row = session.get(CitationMatchCache, snapshot_cache_key(f'upload:{task_id}'))
            snapshot = (row.payload if row else {}).get('snapshot')
        if not isinstance(snapshot, dict):
            return None
        result = deepcopy(snapshot)
        if result.get('source_signature') != source_signature(draft):
            result['status'] = 'stale'
            return result
        ids = {(r.get('matched_paper') or {}).get('paper_id') for r in result.get('references', [])}
        ids.update((r.get('paper') or {}).get('paper_id') for r in result.get('downstream', []))
        ids.discard(None)
        rows = session.execute(select(Paper.id, Paper.title, Paper.doi, Paper.year, Paper.authors,
                                      Paper.content_revision).where(Paper.id.in_(ids),
            Paper.review_status == 'approved', Paper.approved_revision == Paper.content_revision))
        current = {r['paper_id']: r for r in (paper_record(dict(p._mapping)) for p in rows)}
        stale = 0
        for entry in result.get('references', []):
            saved = entry.get('matched_paper')
            if saved and (saved['paper_id'] not in current or
                          paper_signature(saved) != paper_signature(current[saved['paper_id']])):
                entry['decision']['stale'] = True
                stale += 1
        keys = [(r['paper']['paper_id'], current.get(r['paper']['paper_id'], {}).get('revision'),
                 r.get('reference_index')) for r in result.get('downstream', [])]
        refs = session.scalars(select(PaperReference).where(tuple_(PaperReference.paper_id,
            PaperReference.paper_revision, PaperReference.reference_index).in_(keys))).all() if keys else []
        by_key = {(r.paper_id, r.paper_revision, r.reference_index): r for r in refs}
        for entry in result.get('downstream', []):
            saved = entry['paper']
            ref = by_key.get((saved['paper_id'], current.get(saved['paper_id'], {}).get('revision'),
                              entry.get('reference_index')))
            ref_value = {k: getattr(ref, k) for k in REFERENCE_FIELDS} if ref else None
            if (saved['paper_id'] not in current or
                paper_signature(saved) != paper_signature(current[saved['paper_id']]) or
                ref_value is None or reference_signature(ref_value) != entry.get('reference_signature')):
                entry['decision']['stale'] = True
                stale += 1
        result['stale_count'] = stale
        return result
