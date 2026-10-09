"""回答内来源链接必须由当前公开数据支撑。"""

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.models import Paper, PaperChunk, PaperFile, PropertyDefinition
from backend.rag.search.sql_search import (
    get_definition_detail, get_paper_fragment, list_paper_fragments, resolve_answer_links,
)


def test_links_and_fragments_follow_current_approved_revision():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            paper = Paper(id=1, title="LaH10 研究", year=2020, content_revision=1,
                          approved_revision=1, review_status="approved",
                          keywords_tags='["氢化物"]')
            pending = Paper(id=2, title="未批准", year=2020, content_revision=1, review_status="pending")
            another = Paper(id=3, title="另一篇氢化物研究", year=2021, content_revision=1,
                            approved_revision=1, review_status="approved", keywords_tags='["氢化物"]')
            session.add_all([paper, pending, another, PropertyDefinition(
                id=10, code="band_gap", display_name="带隙", value_kind="number",
                description="电子能带中的能量间隔", is_active=True,
            )])
            await session.flush()
            session.add(PaperFile(id=1, paper_id=1, paper_revision=1, role="main",
                                  original_filename="paper.pdf", stored_path="paper.pdf",
                                  sha256="a" * 64, size=100, sort_order=0))
            await session.flush()
            session.add(PaperChunk(id=100, paper_id=1, paper_revision=1,
                                   paper_file_id=1, chunk_index=0, content="LaH10 的原文片段",
                                   section_name="结果", page_start=3, page_end=3))
            await session.commit()

            links = await resolve_answer_links(session, "LaH10 是氢化物，带隙见 [PID_1]，无来源词。", [1, 2, 3])
            assert any(item["kind"] == "paper" and item["paper_id"] == 1 for item in links)
            assert not any(item.get("paper_id") == 2 for item in links)
            assert any(item["kind"] == "definition" and item["term"] == "带隙" for item in links)
            assert any(item["kind"] == "papers" and item["term"] == "氢化物"
                       and item["paper_ids"] == [1, 3] for item in links)
            assert await get_definition_detail(session, 10)
            assert (await list_paper_fragments(session, 1))[0]["id"] == 100
            assert (await get_paper_fragment(session, 1, 100))["content"] == "LaH10 的原文片段"

            paper.review_status = "pending"
            paper.approved_revision = None
            await session.commit()
            assert await get_paper_fragment(session, 1, 100) is None
            assert await list_paper_fragments(session, 1) is None
            assert not any(item.get("paper_id") == 1 for item in
                           await resolve_answer_links(session, "LaH10 [PID_1]", [1]))
            paper.review_status = "approved"
            paper.content_revision = 2
            paper.approved_revision = 2
            await session.commit()
            assert await get_paper_fragment(session, 1, 100) is None
            assert await list_paper_fragments(session, 1) == []
        await engine.dispose()

    asyncio.run(scenario())
