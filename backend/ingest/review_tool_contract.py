"""字段核对的只读工具目录：只提供当前来源实际拥有的能力。"""


def tool_definitions(documents, manifest, *, bibliography=False):
    definitions = []
    def add(name, description, properties):
        definitions.append({"type": "function", "function": {
            "name": name, "description": description, "strict": True,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False}}})

    file_ids = list(documents)
    text = {"type": "string"}
    if file_ids:
        file = {"type": "string", "enum": file_ids}
        add("read_document", "读取当前文档的文本块，不提供页面图像。", {"file_id": file})
        add("read_page", "读取PDF页码对应的文本，不是看图；图中曲线应使用read_original_page。",
            {"file_id": file, "page": {"type": "integer", "minimum": 1}})
        blocks = [b.block_id for ir in documents.values() for b in ir.blocks]
        if blocks:
            add("read_region", "读取给定block_id的原文文本。", {"file_id": file, "block_id": {"type": "string", "enum": blocks}})
        tables = [t.table_id for ir in documents.values() for t in ir.tables]
        if tables:
            add("extract_table", "读取真实table_id对应的表格。", {"file_id": file, "table_id": {"type": "string", "enum": tables}})
        figures = [b.block_id for ir in documents.values() for b in ir.blocks if b.block_type == "figure"]
        if figures:
            add("inspect_figure", "读取真实图块的文字和定位，不返回像素；看原图使用read_original_page。",
                {"file_id": file, "block_id": {"type": "string", "enum": figures}})
        add("search_within_document", "在当前文档文本中搜索原词。", {"file_id": file, "query": {"type": "string", "minLength": 1, "maxLength": 500}})
    pdf_ids = list(dict.fromkeys(item["file_id"] for item in manifest if item.get("kind") == "pdf" and item.get("file_id")))
    if pdf_ids:
        add("read_original_page", "实际读取指定PDF原页图像，包括曲线、图例和插图；page为PDF页码，不是图号。",
            {"file_id": {"type": "string", "enum": pdf_ids}, "page": {"type": "integer", "minimum": 1}})
    if bibliography:
        add("lookup_bibliography", "按已知DOI读取正式题录。", {"doi": text})
    return definitions
