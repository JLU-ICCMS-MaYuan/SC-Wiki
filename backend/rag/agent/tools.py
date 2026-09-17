"""Agent Tools — 把 neo4j/chroma/mysql 函数包装为 LangChain Tool"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool, tool

from backend.rag.tools.neo4j import (
    search_papers as neo4j_search_papers,
    get_paper_context,
    traverse_graph,
    find_path,
)


@tool
def search_papers(query: str, limit: int = 10) -> str:
    """按标题模糊搜索论文。输入可以是材料化学式、方法名、作者名、或研究方向关键词。
    返回匹配的论文ID和标题列表。"""
    results = neo4j_search_papers(query, limit=limit)
    if not results:
        return "未找到匹配论文。"
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def paper_context(paper_id: int) -> str:
    """获取一篇论文的完整上下文：基本信息、研究材料、关联论文、前驱工作、作者。
    当你已获得 paper_id 并想了解该论文的详细内容时使用。"""
    ctx = get_paper_context(paper_id)
    if "error" in ctx:
        return ctx["error"]
    # 截断长文本
    ctx["paper"].pop("summary", None)
    return json.dumps(ctx, ensure_ascii=False, indent=2, default=str)


async def _material_info(formula: str) -> str:
    from backend.rag.tools.mysql import get_material_context

    try:
        return json.dumps(await get_material_context(formula), ensure_ascii=False, default=str)
    except Exception:
        return "材料数据查询失败，请稍后重试；不能据此判断没有材料记录。"


def _material_info_sync(formula: str) -> str:
    import asyncio
    return asyncio.run(_material_info(formula))


material_info = StructuredTool.from_function(
    func=_material_info_sync, coroutine=_material_info, name="material_info",
    description="获取材料的当前已批准物性记录及来源论文，保留各记录的压力、条件和参数。输入材料名或化学式，如 LaH10。",
)


@tool
def explore_graph(paper_id: int, depth: int = 2) -> str:
    """从一篇论文出发，在知识图谱中多跳遍历，发现关联论文和材料。
    用于探索研究脉络、发现相关工作时使用。"""
    result = traverse_graph(paper_id, depth=depth, limit=20)
    # 只返回摘要信息，不返回完整节点
    summary = {
        "center_paper_id": result["center"],
        "depth": result["depth"],
        "node_count": result["node_count"],
        "edge_count": len(result["edges"]),
        "nodes": [
            {"paper_id": n.get("paper_id"), "title": n.get("title", "")[:80]}
            for n in result["nodes"]
            if n.get("paper_id")
        ],
        "edges": result["edges"],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2, default=str)


@tool
def paper_path(from_id: int, to_id: int) -> str:
    """查找两篇论文之间的最短发展路径。展示 A 到 B 的学术脉络。
    当用户询问两篇论文之间的关系或发展历史时使用。"""
    result = find_path(from_id, to_id)
    if "message" in result:
        return result["message"]
    # 简化路径，只保留关键信息
    path_summary = {
        "length": result["length"],
        "path": [
            {"label": n.get("_label", []), "paper_id": n.get("paper_id"),
             "title": n.get("title", "")[:80] if n.get("title") else str(n.get("_label"))}
            for n in result["path"]
        ],
        "edges": result.get("edges", []),
    }
    return json.dumps(path_summary, ensure_ascii=False, indent=2, default=str)


@tool
def search_literature(question: str, top_k: int = 10) -> str:
    """语义搜索相关文献片段。输入完整的自然语言问题，返回相关论文的文本内容。
    当需要获取论文原文中的具体信息时使用。这是唯一能搜索论文正文内容的工具。"""
    from backend.rag.tools.chroma import search_chunks

    try:
        items = search_chunks(question, top_k=top_k)
        if not items:
            return "未找到相关文献片段。"
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"搜索失败: {e}"


async def _query_properties(predicate: str, condition: str = "", material: str | None = None) -> str:
    import re
    from backend.rag.tools.mysql import search_property_records

    operator, value = "=", None
    if condition.strip():
        match = re.fullmatch(r"\s*(>=|<=|>|<|=)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*", condition)
        if not match:
            return "查询失败：条件格式无效，请使用 >200、<=100 或 =0；不筛选数值时留空。"
        operator, value = match.groups()
    try:
        results = await search_property_records(predicate, operator=operator, value=value, material=material)
    except ValueError as exc:
        return f"查询失败：{exc}"
    except Exception:
        return "物性数据库查询失败，请稍后重试；不能据此判断没有匹配数据。"
    if not results:
        return "未找到匹配的当前已批准物性记录。"
    return json.dumps(results[:20], ensure_ascii=False, default=str)


def _query_properties_sync(predicate: str, condition: str = "", material: str | None = None) -> str:
    import asyncio
    return asyncio.run(_query_properties(predicate, condition, material))


query_properties = StructuredTool.from_function(
    func=_query_properties_sync, coroutine=_query_properties, name="query_properties",
    description=("查询当前已批准的物性记录。predicate 支持 Tc/超导温度、pressure/压力、"
                 "lambda/电声耦合，以及其他物性代码或名称。condition 如 >200、<=100、=0，"
                 "留空返回所有值类型；范围按上界比较并保留完整范围。material 可限定材料名或化学式。"
                 "Tc 单位 K，压力 GPa。lambda 查询独立物性记录，Tc 自带参数保留在其 payload 中。"),
)


# 所有可用 tool 列表
ALL_TOOLS = [
    search_papers,
    paper_context,
    material_info,
    explore_graph,
    paper_path,
    search_literature,
    query_properties,
]
