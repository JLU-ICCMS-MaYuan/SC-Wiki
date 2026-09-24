"""受限文档工具：仅操作本任务 IR，预算包含失败与重试，不提供数据库或公网工具。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from .claim_evidence import Claim, validate_claim
from .coverage_audit import audit_coverage
from .document_ir import DocumentIR, content_hash


class AgentStopped(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass
class ActionBudget:
    max_actions: int = 12
    max_retries: int = 2
    actions: int = 0
    retries: dict[str, int] = field(default_factory=dict)

    def consume(self, tool: str, retry: bool = False):
        if self.actions >= self.max_actions:
            raise AgentStopped("agent_budget_exhausted")
        if retry:
            if self.retries.get(tool, 0) >= self.max_retries:
                raise AgentStopped("agent_retry_exhausted")
            self.retries[tool] = self.retries.get(tool, 0) + 1
        self.actions += 1


TOOLS = frozenset({"read_document", "read_page", "read_region", "extract_table",
                   "inspect_figure", "search_within_document", "validate_claim", "check_coverage"})


class DocumentTools:
    def __init__(self, documents: dict[str, DocumentIR], *, cancelled: Callable[[], bool] = lambda: False):
        self.documents = documents
        self.budget = ActionBudget()
        self.cancelled = cancelled
        self.audit: list[dict] = []
        self.read_pages = {key: set() for key in documents}

    def call(self, name: str, arguments: dict, *, retry: bool = False):
        if self.cancelled():
            raise AgentStopped("cancelled")
        if name not in TOOLS:
            raise AgentStopped("tool_not_allowed")
        self.budget.consume(name, retry)
        # 参数仅允许当前文件标识，不接受路径、URL 或其他任务 ID。
        allowed = {"file_id", "page", "block_id", "table_id", "query", "claim", "claims"}
        if set(arguments) - allowed:
            raise AgentStopped("invalid_tool_arguments")
        file_id = arguments.get("file_id")
        if file_id not in self.documents:
            raise AgentStopped("file_not_in_task")
        ir = self.documents[file_id]
        event = {"tool": name, "file_id": file_id, "action": self.budget.actions, "status": "failed",
                 "arguments": {k: arguments[k] for k in ("page", "block_id", "table_id") if k in arguments}}

        self.audit.append(event)
        if name == "validate_claim":
            result = validate_claim(Claim.model_validate(arguments["claim"]), self.documents).model_dump(mode="json")
        elif name == "check_coverage":
            result = audit_coverage(ir, [Claim.model_validate(c) for c in arguments.get("claims", [])],
                                    processed_pages=list(self.read_pages[file_id])).model_dump(mode="json")
        elif name == "extract_table":
            table = next((t for t in ir.tables if t.table_id == arguments.get("table_id")), None)
            if table is None:
                raise AgentStopped("table_not_found")
            result = table.model_dump(mode="json")
        else:
            blocks = ir.blocks
            if name == "read_page":
                page = arguments.get("page")
                if page not in {p.pdf_page for p in ir.pages}:
                    raise AgentStopped("page_not_found")
                blocks = [b for b in blocks if b.pdf_page == page]
                self.read_pages[file_id].add(page)
            elif name in {"read_region", "inspect_figure"}:
                blocks = [b for b in blocks if b.block_id == arguments.get("block_id")]
                if not blocks or (name == "inspect_figure" and blocks[0].block_type != "figure"):
                    raise AgentStopped("region_not_found")
            elif name == "search_within_document":
                query = str(arguments.get("query", ""))
                if not query or len(query) > 500:
                    raise AgentStopped("invalid_query")
                blocks = [b for b in blocks if query.casefold() in b.text.casefold()]
            # 每次工具观察有限大小，截断时不声称已读完整文档。
            selected, size = [], 0
            for block in blocks:
                size += len(block.text)
                if len(selected) >= 100 or size > 50000:
                    break
                selected.append(block.model_dump(mode="json"))
            truncated = len(selected) != len(blocks)
            if name == "read_document" and not truncated:
                self.read_pages[file_id].update(p.pdf_page for p in ir.pages)
            if name == "read_page" and truncated:
                self.read_pages[file_id].discard(arguments["page"])
            result = {"file_id": file_id, "blocks": selected, "truncated": truncated}
        event["status"] = "completed"
        event["result_summary"] = {k: result[k] for k in ("valid", "status", "truncated") if k in result}
        return result


def repair_claims(documents, claims, decide, *, cancelled=lambda: False):
    """最多 12 次动态行动，仅允许为既有同值科学候选补充已验证证据。"""
    tools = DocumentTools(documents, cancelled=cancelled)
    by_path = {claim.target_path: claim for claim in claims}
    observation = {"documents": [{"file_id":key,"pages":len(ir.pages)} for key,ir in documents.items()],
                   "claims": [claim.model_dump(mode="json") for claim in claims],
                   "tools": sorted(TOOLS)}
    stop = "agent_budget_exhausted"
    last_failed = None
    for _ in range(12):
        if cancelled():
            stop = "cancelled"
            break
        try:
            decision = decide(observation)
            for raw in decision.get("claims", []):
                candidate = Claim.model_validate(raw)
                previous = by_path.get(candidate.target_path)
                if previous is None or content_hash(previous.value) != content_hash(candidate.value):
                    continue
                validated = validate_claim(candidate, documents)
                if validated.valid:
                    by_path[candidate.target_path] = validated.claim
            if decision.get("done") is True:
                stop = "model_stopped"
                break
            action = decision["action"]
            name = action["name"]
            result = tools.call(name, action["arguments"], retry=name == last_failed)
            last_failed = None
            # 下一次继续携带当前候选；不保存模型自由思考文字。
            observation = {"result":result,"claims":[c.model_dump(mode="json") for c in by_path.values()],
                           "remaining_actions":12-tools.budget.actions, "tools":sorted(TOOLS)}
        except AgentStopped as exc:
            stop = exc.reason
            if stop in {"agent_budget_exhausted","agent_retry_exhausted","cancelled"}:
                break
            last_failed = name if "name" in locals() else None
            observation = {"error":stop,"remaining_actions":12-tools.budget.actions,"tools":sorted(TOOLS)}
        except Exception:
            stop = "agent_invalid_response_or_model_unavailable"
            break
    return list(by_path.values()), {"stop_reason":stop,"actions":tools.budget.actions,"calls":tools.audit}
