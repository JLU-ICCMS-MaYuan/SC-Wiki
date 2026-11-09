"""论文级材料清单不能在正式入库时被状态列表悄悄替换。"""
import asyncio
import pytest

from backend.tests.test_upload_workflow import FakePaperSession, _minimal_non_review_draft, _state_with_material


@pytest.mark.parametrize('materials,bound,expected', [
    (['Reviewed calcium hydrides'], False, ['Reviewed calcium hydrides']), ([], False, []),
    (None, False, ['CaH6']), (None, True, []),
])
def test_formal_creation_keeps_explicit_paper_materials(tmp_path, monkeypatch, materials, bound, expected):
    from backend.api import rag
    from backend.models import Paper
    from backend.rag import database
    from backend.ingest import upload_jobs, upload_tasks, scientific_drafts
    from backend.services import spectra, classification_catalog
    class Session(FakePaperSession):
        def add_all(self, values):
            self.added.extend(values)
    session = Session()
    async def noop(*_a, **_kw):
        return []
    monkeypatch.setattr(database, 'async_session_factory', lambda: session)
    monkeypatch.setattr(upload_jobs, '_normalize_draft', lambda draft: draft)
    monkeypatch.setattr(rag, '_resolve_draft_classifications', noop)
    monkeypatch.setattr(scientific_drafts, 'persist_scientific_draft', noop)
    monkeypatch.setattr(spectra, 'bind_to_paper', noop)
    monkeypatch.setattr(classification_catalog, 'save_paper_material_families', noop)
    monkeypatch.setattr(upload_tasks, 'markdown_path', lambda _: tmp_path / 'missing.md')
    draft = _minimal_non_review_draft([_state_with_material('CaH6')], research_materials=materials)
    if bound:
        from backend.ingest.parsing_workflows import CURRENT
        draft['_parsing_workflow'] = CURRENT.binding()
    asyncio.run(rag._create_pending_paper('c' * 32, {'user_id': 1}, draft))
    paper = next(row for row in session.added if isinstance(row, Paper))
    assert paper.research_materials == expected
