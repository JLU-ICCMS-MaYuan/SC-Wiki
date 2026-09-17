"""展示契约：历史关系来源与研究材料汇总。"""
import json
import asyncio
import copy
import os
import pytest

from backend.api.rag import _derived_research_materials
from backend.ingest.upload_jobs import _normalize_draft


def test_relation_history_keeps_all_source_fields():
    relations = [{"material": "Sn", "relation": "investigates", "page": 2,
                  "quote": "source", "evidence": {"file_id": "main"}}]
    for value in [relations, json.dumps(relations)]:
        result = _normalize_draft({"paper": {"material_relations": value}})
        assert result["paper"]["material_relations"] == relations
    assert _normalize_draft({"paper": {"material_relations": "invalid history"}})["paper"]["material_relations"] == "invalid history"


def test_summary_tracks_state_order_and_uses_name_before_formula():
    states = [{"material_name": " Tin ", "material": "Sn"}, {"material_name": "Tin", "material": "Sn"}, {"material": "Pb"}]
    assert _derived_research_materials(states) == ["Tin", "Pb"]
    states[0]["material_name"] = "Pure tin"
    assert _derived_research_materials(states) == ["Pure tin", "Tin", "Pb"]
    assert _derived_research_materials([]) == []


@pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='显式选择当前 MySQL 外层回滚验证')
def test_scientific_save_reload_updates_summary_and_preserves_relations(monkeypatch):
    from sqlalchemy import select
    from backend import models
    from backend.api.rag import rewrite_paper_scientific_draft
    from test_material_name_save_flow import isolated_paper

    async def run():
        async with isolated_paper(monkeypatch) as (factory, user, pid, payload):
            relation = [{"material": "Sn", "relation": "investigates", "page": 2, "quote": "source"}]
            async with factory() as session, session.begin():
                paper = await session.get(models.Paper, pid)
                paper.research_materials = ['legacy']
                paper.material_relations = relation
            for name, kind in [('Tin', 'experimental'), ('Pure tin', 'mixed')]:
                payload['material_states'][0].update(material_name=name, state_kind=kind)
                assert (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['ok']
                async with factory() as session:
                    paper = await session.get(models.Paper, pid)
                    state = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == pid))
                    assert paper.research_materials == [name]
                    assert paper.material_relations == relation
                    assert state.state_kind == kind
            assert (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['data']['unchanged']
    asyncio.run(run())
