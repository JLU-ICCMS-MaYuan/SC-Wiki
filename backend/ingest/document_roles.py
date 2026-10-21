"""依据已解析文本识别正文与补充材料，不使用上传顺序。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


RULE_VERSION = "document-roles-v1"
TEXT_KINDS = {"pdf", "txt", "md"}
_SI_NAME = re.compile(r"(?i)(?:^|[\s._-])(?:si|supp(?:lement(?:ary|al)?)?|supporting|appendix|suppliment\w*|supplyment\w*)(?:[\s._-]|$)")
_SI_TITLE = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:supporting|supplementary|supplemental)\s+(?:information|material|data)\b")
_SI_ITEM = re.compile(r"(?im)\b(?:fig(?:ure)?|table)\.?\s*S\d+\b")
_ARTICLE_SECTION = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*[.)]?\s+)?(?:introduction|results(?:\s+and\s+discussion)?|discussion|conclusions?|methods?|materials\s+and\s+methods)\s*$")
_ABSTRACT = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:abstract|摘要)\s*$")
_DOI = re.compile(r"(?i)\b10\.\d{4,9}/[^\s<>]+")
_AUTHORS = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:authors?|affiliations?)\s*:?\s*$")
_TITLE = re.compile(r"(?m)^\s*#{1,3}\s+([^\n]{25,220})$")
_BYLINE = re.compile(r"(?i)\b(?:university|laboratory|institute|department|college|academy)\b")


def _signals(filename: str, content: str) -> tuple[list[str], list[str]]:
    head = content[:8000]
    article, supplement = [], []
    if _SI_NAME.search(filename):
        supplement.append("文件名标示补充材料")
    if _SI_TITLE.search(head):
        supplement.append("首页标示补充材料")
    if len(_SI_ITEM.findall(content[:20000])) >= 2:
        supplement.append("正文含连续 S 编号图表")
    titles = [m.group(1).strip() for m in _TITLE.finditer(head)]
    if any(not _SI_TITLE.search(title) and not re.match(r"(?i)(?:fig(?:ure)?|table|来源文件|page)\b", title)
           and len(title.split()) >= 4 for title in titles):
        article.append("首页有论文式标题")
    elif not supplement:
        lines = [line.strip() for line in head.splitlines()[:12] if line.strip()]
        if len(lines) >= 3 and 25 <= len(lines[0]) <= 180 and len(lines[0].split()) >= 4 \
                and _BYLINE.search(" ".join(lines[1:5])):
            article.append("首页有无 Markdown 标记的论文标题与署名单位")
    if _ABSTRACT.search(head):
        article.append("首页有摘要章节")
    if _AUTHORS.search(head):
        article.append("首页有作者或单位信息")
    if _ARTICLE_SECTION.search(content):
        article.append("正文有论文章节")
    if _DOI.search(head) and not _SI_TITLE.search(head):
        article.append("首页有 DOI")
    return article, supplement


def assess_roles(files: list[dict[str, Any]], texts: dict[str, str]) -> dict[str, Any]:
    """仅唯一且信号充分的论文主文自动生效；否则等待用户确认。"""
    assessments = []
    signature = []
    for item in files:
        file_id = str(item.get("file_id") or "")
        content = texts.get(file_id, "") if str(item.get("kind") or "").lower() in TEXT_KINDS else ""
        signature.append((file_id, item.get("sha256"), hashlib.sha256(content.encode()).hexdigest()))
        article, supplement = _signals(str(item.get("original_filename") or ""), content) if content else ([], [])
        assessments.append({"file_id": file_id, "declared_role": item.get("declared_role") or item.get("role"),
                            "article_signals": article, "supplement_signals": supplement,
                            "readable": bool(content.strip())})
    text_items = [entry for entry in assessments if entry["readable"]]
    candidates = [entry for entry in text_items if len(entry["article_signals"]) >= 2
                  and not (len(entry["supplement_signals"]) >= 2)]
    main = candidates[0] if len(candidates) == 1 else None
    if len(text_items) == 1 and not main and text_items[0]["article_signals"] \
            and not text_items[0]["supplement_signals"]:
        main = text_items[0]
    status = "resolved" if main and (len(text_items) == 1 or len(main["article_signals"]) >= 2) else "needs_review"
    main_id = main["file_id"] if status == "resolved" else None
    for entry in assessments:
        if not entry["readable"]:
            role = "attachment"
        elif entry["file_id"] == main_id:
            role = "main"
        elif len(entry["supplement_signals"]) >= 1:
            role = "supplementary"
        else:
            role = "attachment"
        entry["effective_role"] = role if status == "resolved" else None
    return {"status": status, "main_file_id": main_id, "files": assessments,
            "source_hash": hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest(),
            "rule_version": RULE_VERSION,
            "reason": "找到唯一论文正文" if status == "resolved" else "无法可靠确定唯一正文，请确认文件角色"}
