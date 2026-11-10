"""图片工具只登记当前原始对象；历史/派生科学事实保留在IR中。"""
from __future__ import annotations

SOURCE_CONTEXT_VERSION = 'current-original-context-v2'


def is_original_block(block):
    """原始识别（含备用Marker）与程序生成的图读/未读回执按实际元数据区分。"""
    return not {'chart_reading', 'chart_unresolved'} & set(block.metadata)


def original_source_blocks(ir, *, page=None):
    return [block for block in ir.blocks
        if (page is None or block.pdf_page == page)
        and block.metadata.get('selected_for_reading') is not False
        and is_original_block(block)]


def visual_objects(ir):
    """整表已完整包含单元格时只列父表；孤立或越界单元格继续保留入口。"""
    blocks = [block for block in original_source_blocks(ir) if block.bbox]
    parents = {block.block_id: block for block in blocks if block.block_type == 'table'}
    by_table = {(table.table_id, table.pdf_page): table.block_id for table in ir.tables}
    by_cell = {cell.block_id: table.block_id for table in ir.tables for cell in table.cells
               if cell.block_id}
    result = []
    for block in blocks:
        if block.block_type == 'table_cell':
            keys = (block.parent_block_id, by_table.get((block.table_id, block.pdf_page)),
                    by_cell.get(block.block_id))
            child = block.bbox
            covered = False
            for key in keys:
                parent = parents.get(key)
                if parent and parent.pdf_page == block.pdf_page:
                    box = parent.bbox
                    if box[0] <= child[0] <= child[2] <= box[2] and box[1] <= child[1] <= child[3] <= box[3]:
                        covered = True
                        break
            if covered:
                continue
        result.append(block)
    return result
