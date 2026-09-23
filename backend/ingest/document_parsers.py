"""PDF 解析器适配器和运行时能力探测。

解析方案由调用方显式选择。适配器失败时只返回 ParserError，不能在内部
偷偷切换另一个解析方案，也不允许直接写入业务数据库。
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .document_ir import BlockType, DocumentBlock, DocumentIR, PageGeometry, ParseMode, content_hash


class ParserProfile:
    TEXT = "text"
    LAYOUT = "layout"
    OCR = "ocr"
    VISION = "vision"
    NATIVE_PDF_LLM = "native_pdf_llm"


@dataclass(frozen=True)
class RuntimeCapabilities:
    gpu: bool = False
    ocr: bool = False
    vision: bool = False
    native_pdf_llm: bool = False
    installed: frozenset[str] = frozenset()

    @classmethod
    def detect(cls) -> "RuntimeCapabilities":
        installed: set[str] = set()
        for package in ("fitz", "docling", "mineru"):
            try:
                importlib.import_module(package)
            except Exception:
                continue
            installed.add(package)
        gpu = False
        try:
            torch = importlib.import_module("torch")
            gpu = bool(torch.cuda.is_available())
        except Exception:
            pass
        return cls(gpu=gpu, installed=frozenset(installed))


@dataclass(frozen=True)
class DocumentSource:
    path: Path
    file_id: str
    role: str = "main"
    sha256: str | None = None
    source_version: int = 1
    media_type: str = "application/pdf"

    def resolved_sha256(self) -> str:
        if self.sha256:
            return self.sha256
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


@dataclass(frozen=True)
class ParseOptions:
    profile: str = ParserProfile.TEXT
    task_id: str | None = None
    parser_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParserDecision:
    supported: bool
    profile: str
    mode: str
    reason: str
    required_capabilities: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass
class ParserRun:
    task_id: str | None
    file_id: str
    profile: str
    parser: str
    version: str
    mode: str
    status: str = "queued"
    reading_state: str | None = None
    error_code: str | None = None
    error_summary: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    ir_schema_version: str = "1"
    rule_version: str = "1"
    model_version: str | None = None

    def start(self, reading_state: str = "parsing") -> None:
        self.status = "running"
        self.reading_state = reading_state
        self.started_at = time.time()

    def finish(self, status: str = "succeeded", reading_state: str | None = None) -> None:
        self.status = status
        self.reading_state = reading_state or self.reading_state
        self.ended_at = time.time()

    def fail(self, error_code: str, summary: str, *, reading_state: str = "failed") -> None:
        self.status = "failed"
        self.reading_state = reading_state
        self.error_code = error_code
        self.error_summary = summary[:500]
        self.ended_at = time.time()


class ParserError(RuntimeError):
    def __init__(self, code: str, message: str, *, profile: str, parser: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.profile = profile
        self.parser = parser


class DocumentParser(Protocol):
    name: str
    version: str

    def can_parse(self, source: DocumentSource, capabilities: RuntimeCapabilities) -> ParserDecision: ...

    def parse(self, source: DocumentSource, options: ParseOptions) -> DocumentIR: ...


def _profile_for_mode(profile: str) -> str:
    return ParseMode.VLM.value if profile in {ParserProfile.VISION, ParserProfile.NATIVE_PDF_LLM} else ParseMode.TEXT.value


class PyMuPDFParser:
    name = "pymupdf"
    version = "optional"

    def can_parse(self, source: DocumentSource, capabilities: RuntimeCapabilities) -> ParserDecision:
        if source.media_type != "application/pdf":
            return ParserDecision(False, ParserProfile.TEXT, ParseMode.TEXT.value, "仅支持 PDF")
        if "fitz" not in capabilities.installed:
            return ParserDecision(False, ParserProfile.TEXT, ParseMode.TEXT.value, "PyMuPDF 不可用", ("fitz",))
        return ParserDecision(True, ParserProfile.TEXT, ParseMode.TEXT.value, "可用")

    def parse(self, source: DocumentSource, options: ParseOptions) -> DocumentIR:
        if source.media_type != "application/pdf":
            raise ParserError("parser_unsupported_media", "PyMuPDF 方案只支持 PDF", profile=options.profile, parser=self.name)
        try:
            fitz = importlib.import_module("fitz")
        except Exception as exc:
            raise ParserError("parser_dependency_unavailable", "PyMuPDF 不可用", profile=options.profile, parser=self.name) from exc
        try:
            doc = fitz.open(str(source.path))
            pages: list[PageGeometry] = []
            blocks: list[DocumentBlock] = []
            order = 0
            for page_number, page in enumerate(doc, start=1):
                rect = page.rect
                pages.append(PageGeometry(pdf_page=page_number, width=float(rect.width), height=float(rect.height)))
                for raw in page.get_text("dict").get("blocks", []):
                    if raw.get("type") == 0:
                        lines = ["".join(span.get("text", "") for span in line.get("spans", [])) for line in raw.get("lines", [])]
                        text = " ".join(line.strip() for line in lines if line.strip())
                        block_type = BlockType.PARAGRAPH
                    elif raw.get("type") == 1:
                        text = ""
                        block_type = BlockType.FIGURE
                    else:
                        continue
                    if not text and block_type is BlockType.PARAGRAPH:
                        continue
                    bbox = tuple(float(value) for value in raw.get("bbox", (0, 0, 0, 0)))
                    block_id = f"{source.file_id}:{source.source_version}:{page_number}:{order}:{content_hash(block_type.value, text, bbox)[:16]}"
                    blocks.append(DocumentBlock(
                        block_id=block_id, block_type=block_type, pdf_page=page_number,
                        reading_order=order, text=text, bbox=bbox,
                        page_width=float(rect.width), page_height=float(rect.height),
                        content_hash=content_hash(block_type.value, text, bbox),
                    ))
                    order += 1
            doc.close()
        except ParserError:
            raise
        except Exception as exc:
            raise ParserError("parser_invalid_output", "PyMuPDF 解析失败", profile=options.profile, parser=self.name) from exc
        return DocumentIR(
            document_id=f"{source.file_id}:{source.source_version}:{self.name}",
            source_file_id=source.file_id, source_sha256=source.resolved_sha256(),
            source_version=source.source_version, parse_profile=options.profile,
            parser={"name": self.name, "version": self.version, "mode": ParseMode.TEXT.value},
            pages=pages, blocks=blocks,
        )


class OptionalParser:
    """Docling/MinerU 的受控可选适配器骨架。

    依赖未安装或供应商 API 不兼容时返回明确错误，绝不调用另一解析器。
    """

    def __init__(self, *, name: str, package: str, profile: str, mode: str = "text"):
        self.name, self.package, self.profile, self.mode = name, package, profile, mode
        self.version = "optional"

    def can_parse(self, source: DocumentSource, capabilities: RuntimeCapabilities) -> ParserDecision:
        if source.media_type != "application/pdf":
            return ParserDecision(False, self.profile, self.mode, "仅支持 PDF")
        if self.package not in capabilities.installed:
            return ParserDecision(False, self.profile, self.mode, f"{self.name} 依赖不可用", (self.package,))
        return ParserDecision(True, self.profile, self.mode, "可用")

    def parse(self, source: DocumentSource, options: ParseOptions) -> DocumentIR:
        try:
            importlib.import_module(self.package)
        except Exception as exc:
            raise ParserError("parser_dependency_unavailable", f"{self.name} 依赖不可用", profile=options.profile, parser=self.name) from exc
        raise ParserError("parser_invalid_output", f"{self.name} 适配器尚未实现供应商输出映射", profile=options.profile, parser=self.name)


class NativePdfLlmParser:
    name = "native_pdf_llm"
    version = "adapter"

    def __init__(self, parse_document: Callable[..., DocumentIR] | None = None):
        self._parse_document = parse_document

    def can_parse(self, source: DocumentSource, capabilities: RuntimeCapabilities) -> ParserDecision:
        supported = source.media_type == "application/pdf" and capabilities.native_pdf_llm and self._parse_document is not None
        reason = "可用" if supported else "PDF 原生 LLM 适配器不可用"
        return ParserDecision(supported, ParserProfile.NATIVE_PDF_LLM, ParseMode.VLM.value, reason, ("native_pdf_llm",))

    def parse(self, source: DocumentSource, options: ParseOptions) -> DocumentIR:
        if self._parse_document is None:
            raise ParserError("parser_model_unavailable", "PDF 原生 LLM 适配器不可用", profile=options.profile, parser=self.name)
        result = self._parse_document(source, options)
        if not isinstance(result, DocumentIR):
            raise ParserError("parser_invalid_output", "PDF 原生 LLM 必须返回 DocumentIR", profile=options.profile, parser=self.name)
        return result


class ParserRegistry:
    def __init__(self, parsers: list[DocumentParser] | None = None):
        self.parsers = parsers or [
            PyMuPDFParser(),
            OptionalParser(name="docling", package="docling", profile=ParserProfile.LAYOUT),
            OptionalParser(name="mineru", package="mineru", profile=ParserProfile.OCR),
            NativePdfLlmParser(),
        ]

    def choose(self, profile: str, source: DocumentSource, capabilities: RuntimeCapabilities) -> DocumentParser:
        for parser in self.parsers:
            decision = parser.can_parse(source, capabilities)
            if decision.profile == profile:
                if not decision.supported:
                    raise ParserError("parser_profile_unavailable", decision.reason, profile=profile, parser=getattr(parser, "name", "unknown"))
                return parser
        raise ParserError("parser_profile_unavailable", f"未注册解析方案：{profile}", profile=profile, parser="registry")


def parse_with_profile(source: DocumentSource, options: ParseOptions, *, registry: ParserRegistry | None = None, capabilities: RuntimeCapabilities | None = None) -> tuple[DocumentIR, ParserRun]:
    registry = registry or ParserRegistry()
    capabilities = capabilities or RuntimeCapabilities.detect()
    parser = registry.choose(options.profile, source, capabilities)
    run = ParserRun(None, source.file_id, options.profile, parser.name, parser.version, _profile_for_mode(options.profile))
    run.start()
    try:
        ir = parser.parse(source, options)
        run.finish("succeeded", "ir_ready")
        return ir, run
    except ParserError as exc:
        run.fail(exc.code, exc.message)
        raise
