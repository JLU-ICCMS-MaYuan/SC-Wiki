"""#232/#235：真实PDF区域、完整图注、坐标与可清理缓存。"""
from copy import deepcopy
import hashlib
import io

import pymupdf
from PIL import Image
import pytest

from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash
from backend.ingest.pdf_regions import complete_figure, region_locator, render_region_image, render_page_image, RegionError


def test_blank_crop_is_not_an_observed_figure(tmp_path):
    from backend.ingest.image_reading import ImageReadingTools
    path,ir=source(tmp_path)
    tools=ImageReadingTools({'main':ir},{'main':path})
    full,_=tools.call('read_complete_object',{'file_id':'main','block_id':'fig'})
    with pytest.raises(ValueError,match='没有可见内容'):
        tools.call('adjust_image_region',{'region_id':full['locator']['region_id'],
            'bbox_page':[1,1,20,20],'dpi':600,'reason':'核对误裁到的空白区'})


def test_explicit_cross_page_table_keeps_separate_page_parts(tmp_path):
    from backend.ingest.pdf_regions import object_region
    path=tmp_path/'table.pdf'
    with pymupdf.open() as pdf:
        for index in range(2):
            page=pdf.new_page(width=200,height=200)
            page.insert_text((20,40),f'Table 1. Tc (K) continued {index}',fontsize=8)
            page.draw_rect((20,50,180,150));page.insert_text((30,70),'ScH6 100',fontsize=8)
        pdf.save(path)
    ir=DocumentIR(document_id='t',source_file_id='main',source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        parse_profile='complementary',pages=[PageGeometry(pdf_page=n,width=200,height=200) for n in (1,2)],
        blocks=[DocumentBlock(block_id='table-'+str(n),block_type='table',table_id='continued-table-1',
            pdf_page=n,reading_order=n,bbox=(18,25,182,152),content_hash=content_hash(n)) for n in (1,2)])
    locator=object_region(ir,path,'table-1')
    rendered=render_region_image(path,locator)
    assert [p['pdf_page'] for p in rendered['parts']]==[1,2]
    assert locator['related_regions'][0]['bbox_page']==[18,25,182,152]


def source(tmp_path, *, rotation=0):
    path = tmp_path / 'source.pdf'
    pdf = pymupdf.open(); page = pdf.new_page(width=240, height=300)
    page.draw_rect((30, 35, 210, 180), color=(0, 0, 0))
    page.draw_rect((60, 90, 85, 175), fill=(0, 1, 0))
    page.insert_text((32, 204), 'Fig. 1. Complete caption, first line.', fontsize=8)
    page.insert_text((32, 215), 'Second line: ScH6 at 300 GPa.', fontsize=8)
    page.set_rotation(rotation); pdf.save(path); pdf.close()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        ir = DocumentIR(document_id='regions', source_file_id='main', source_sha256=sha,
            parse_profile='complementary', pages=[PageGeometry(pdf_page=1, width=page.rect.width, height=page.rect.height)],
            blocks=[DocumentBlock(block_id='fig', block_type='figure', pdf_page=1, reading_order=0,
                bbox=(30, 35, 210, 180), content_hash=content_hash('fig')),
                DocumentBlock(block_id='caption', block_type='caption', pdf_page=1, reading_order=1,
                bbox=(30, 192, 211, 218), text='Fig. 1. Complete caption, first line.\nSecond line: ScH6 at 300 GPa.',
                content_hash=content_hash('caption'))])
    return path, ir


def test_complete_figure_keeps_full_caption_then_child_keeps_parent(tmp_path):
    path, ir = source(tmp_path)
    locator = complete_figure(ir, path, {'page': 1, 'bbox': [55, 80, 90, 175], 'label': 'Fig. 1 (b)'})
    assert locator['caption_status'] == 'located'
    assert 'Second line' in locator['caption_text']
    assert locator['bbox_page'][0] <= 30 and locator['bbox_page'][3] >= 218
    assert locator['dpi'] >= 600


def test_overlapping_caption_variants_keep_one_physical_context_and_all_provenance(tmp_path):
    path,ir=source(tmp_path)
    variant=ir.blocks[1].model_copy(deep=True)
    variant.block_id='ocr-caption'
    variant.text='Fig. 1. Complete caption, first line. Second line: \\mathrm{ScH6} at 300 GPa.'
    variant.bbox=(31,193,210,217)
    variant.content_hash=content_hash(variant.text)
    variant.reading_order=2
    ir.blocks.append(variant)
    before=ir.model_dump(mode='json')
    locator=complete_figure(ir,path,{'page':1,'bbox':[30,35,210,180],'label':'Fig. 1'})
    assert locator['caption_status']=='located'
    assert locator['bbox_page'][3]<300
    assert {v['block_id']for v in locator['caption_variants']} >= {'caption','ocr-caption'}
    assert all(v['text']for v in locator['caption_variants'])
    assert ir.model_dump(mode='json')==before
    child = region_locator(path, ir.source_file_id, ir.source_sha256, 1, [55, 80, 90, 175],
        kind='figure', parent_region_id=locator['region_id'])
    assert child['parent_region_id'] == locator['region_id']
    assert child['region_id'] != locator['region_id']


def test_same_page_second_caption_is_not_used_for_first_figure(tmp_path):
    path, ir = source(tmp_path)
    ir.blocks.append(DocumentBlock(block_id='other-caption', block_type='caption', pdf_page=1,
        reading_order=2, bbox=(30, 181, 211, 190), text='Fig. 2. Wrong nearby caption.', content_hash=content_hash('other')))
    locator = complete_figure(ir, path, {'page': 1, 'bbox': [30, 35, 210, 180], 'label': 'Fig. 1'})
    assert 'Second line' in locator['caption_text'] and 'Wrong nearby' not in locator['caption_text']


def test_missing_caption_uses_explicit_full_page_context_not_fake_complete_crop(tmp_path):
    path, ir = source(tmp_path); ir.blocks = ir.blocks[:1]
    # 原PDF中存在图注，允许从真实文字层补找。
    located = complete_figure(ir, path, {'page': 1, 'bbox': [30, 35, 210, 180], 'label': 'Fig. 1'})
    assert located['caption_status'] == 'located' and 'Second line' in located['caption_text']
    missing = complete_figure(ir, path, {'page': 1, 'bbox': [30, 35, 210, 180], 'label': 'Fig. 9'})
    assert missing['caption_status'] == 'unlocated'
    assert missing['bbox_page'] == [0, 0, 240, 300]


def test_partial_parser_caption_is_extended_with_actual_pdf_paragraph(tmp_path):
    path,ir=source(tmp_path)
    ir.blocks[1].text='Fig. 1. Complete caption, first line.'
    ir.blocks[1].bbox=(30,192,211,207)
    locator=complete_figure(ir,path,{'page':1,'bbox':[30,35,210,180],'label':'Fig. 1'})
    assert locator['caption_status']=='located' and 'Second line' in locator['caption_text']
    assert locator['bbox_page'][3]>215


def test_render_cache_rebuild_has_same_pixels_and_does_not_modify_pdf(tmp_path):
    path, ir = source(tmp_path); before = path.read_bytes()
    loc = complete_figure(ir, path, {'page': 1, 'bbox': [30, 35, 210, 180], 'label': 'Fig. 1'})
    cache = tmp_path / 'cache'
    first = render_region_image(path, loc, cache_dir=cache)
    second = render_region_image(path, loc, cache_dir=cache)
    assert first['cache_hit'] is False and second['cache_hit'] is True
    assert first['png'] == second['png'] and first['dpi'] == 600
    image = Image.open(io.BytesIO(first['png']))
    assert image.width == pytest.approx((loc['bbox_page'][2] - loc['bbox_page'][0]) * 600 / 72, abs=2)
    assert image.height == pytest.approx((loc['bbox_page'][3] - loc['bbox_page'][1]) * 600 / 72, abs=2)
    from backend.ingest.pdf_regions import clear_region_cache
    sentinel=cache/'other-task.txt';sentinel.write_text('保留其他任务内容')
    assert len(clear_region_cache(cache,[loc]))==2
    assert sentinel.read_text()=='保留其他任务内容'
    rebuilt = render_region_image(path, loc, cache_dir=cache)
    assert rebuilt['png'] == first['png'] and not rebuilt['cache_hit']
    assert path.read_bytes() == before
    assert not any('base64' in str(value) for value in loc.values())


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_rotated_page_locator_and_pixel_transform_roundtrip(tmp_path, rotation):
    path, ir = source(tmp_path, rotation=rotation)
    with pymupdf.open(path) as pdf:
        width, height = pdf[0].rect.width, pdf[0].rect.height
    loc = region_locator(path, 'main', ir.source_sha256, 1, [0, 0, width, height], kind='text')
    result = render_region_image(path, loc)
    assert result['width'] == pytest.approx(width * 600 / 72, abs=1)
    assert result['height'] == pytest.approx(height * 600 / 72, abs=1)
    assert loc['rotation'] == rotation
    scale = result['pixel_to_page']
    assert result['width'] * scale[0] + scale[2] == pytest.approx(width)
    assert result['height'] * scale[1] + scale[3] == pytest.approx(height)


def test_source_digest_locator_tampering_and_invalid_region_rejected(tmp_path):
    path, ir = source(tmp_path)
    with pytest.raises(RegionError): region_locator(path, 'main', '0' * 64, 1, [0, 0, 20, 20])
    for box in [[-1, 0, 20, 20], [20, 0, 0, 20], [0, 0, 0, 20], [0, 0, 241, 301]]:
        with pytest.raises(RegionError): region_locator(path, 'main', ir.source_sha256, 1, box)
    loc = region_locator(path, 'main', ir.source_sha256, 1, [0, 0, 20, 20])
    changed = deepcopy(loc); changed['bbox_page'][2] = 21
    with pytest.raises(RegionError): render_region_image(path, changed)


def test_discovery_page_is_at_least_300_dpi(tmp_path):
    path, ir = source(tmp_path)
    result = render_page_image(path, ir.source_sha256, 1)
    assert result['dpi'] >= 300 and result['width'] == 1000


def test_fractional_crop_uses_actual_pixel_origin_not_ideal_box(tmp_path):
    path, ir = source(tmp_path)
    loc = region_locator(path, 'main', ir.source_sha256, 1, [30.07, 35.09, 90.11, 180.13])
    result = render_region_image(path, loc)
    scale_x, scale_y, left, top = result['pixel_to_page']
    assert scale_x == pytest.approx(72 / 600) and scale_y == pytest.approx(72 / 600)
    assert left == pytest.approx(int(30.07 * 600 / 72) * 72 / 600)
    assert top == pytest.approx(int(35.09 * 600 / 72) * 72 / 600)


def test_cache_receipt_corruption_is_rebuilt(tmp_path):
    import json
    path, ir = source(tmp_path)
    loc = region_locator(path, 'main', ir.source_sha256, 1, [30, 35, 90, 180])
    cache = tmp_path / 'cache'
    first = render_region_image(path, loc, cache_dir=cache)
    receipt = next(cache.glob('*.json')); value = json.loads(receipt.read_text())
    value.update(region_id='wrong', width=1); receipt.write_text(json.dumps(value))
    result = render_region_image(path, loc, cache_dir=cache)
    assert not result['cache_hit'] and result['width'] == first['width']


def test_parent_identity_change_does_not_rerender_same_physical_image(tmp_path):
    path,ir=source(tmp_path)
    a=region_locator(path,'main',ir.source_sha256,1,[30,35,210,180])
    b=region_locator(path,'formal-file',ir.source_sha256,1,[30,35,210,180],parent_region_id='parent')
    cache=tmp_path/'cache'
    first=render_region_image(path,a,cache_dir=cache)
    second=render_region_image(path,b,cache_dir=cache)
    assert second['cache_hit'] and second['png']==first['png']
    assert second['region_id']==b['region_id']
    assert len(list(cache.glob('*.png')))==1


def test_object_regions_keep_table_notes_and_formula_context(tmp_path):
    from backend.ingest.pdf_regions import object_region
    path, ir = source(tmp_path)
    ir.blocks += [DocumentBlock(block_id='table', block_type='table', pdf_page=1, reading_order=2,
        text='Pressure GPa | Tc K\n300 | 99', bbox=(20, 230, 180, 270), content_hash=content_hash('table')),
        DocumentBlock(block_id='table-note', block_type='caption', pdf_page=1, reading_order=3,
        text='Table 1. mu*=0.1', bbox=(20, 275, 180, 289), content_hash=content_hash('note')),
        DocumentBlock(block_id='formula', block_type='formula', pdf_page=1, reading_order=4,
        text='Tc = f(lambda) (1)', bbox=(5, 5, 130, 25), content_hash=content_hash('formula'))]
    table = object_region(ir, path, 'table')
    assert table['kind'] == 'table' and table['bbox_page'][3] >= 289
    formula = object_region(ir, path, 'formula')
    assert formula['kind'] == 'formula' and formula['bbox_page'][0] <= 5


def test_multiple_panels_share_complete_figure_context(tmp_path):
    path, ir = source(tmp_path); ir.blocks = ir.blocks[1:]
    targets = [{'page': 1, 'bbox': [30, 35, 110, 100], 'label': 'Fig. 1 (a)'},
               {'page': 1, 'bbox': [130, 120, 210, 180], 'label': 'Fig. 1 (b)'}]
    loc = complete_figure(ir, path, targets[0], related_targets=targets)
    assert loc['bbox_page'][2] >= 210 and loc['bbox_page'][3] >= 218


def test_cross_page_caption_keeps_both_original_page_transforms(tmp_path):
    path=tmp_path/'two.pdf';pdf=pymupdf.open()
    pdf.new_page(width=200,height=200).draw_rect((20,20,180,180))
    pdf.new_page(width=200,height=200).insert_text((15,30),'Fig. 2. Complete caption on next page.',fontsize=8)
    pdf.save(path);pdf.close();sha=hashlib.sha256(path.read_bytes()).hexdigest()
    ir=DocumentIR(document_id='cross-page',source_file_id='main',source_sha256=sha,parse_profile='complementary',
        pages=[PageGeometry(pdf_page=i,width=200,height=200) for i in [1,2]],
        blocks=[DocumentBlock(block_id='body',block_type='figure',pdf_page=1,reading_order=0,bbox=(20,20,180,180),content_hash=content_hash('body')),
            DocumentBlock(block_id='caption',block_type='caption',pdf_page=2,reading_order=1,bbox=(15,20,185,35),
                text='Fig. 2. Complete caption on next page.',content_hash=content_hash('cap'))])
    locator=complete_figure(ir,path,{'page':1,'bbox':[20,20,180,180],'label':'Fig. 2'})
    assert locator['caption_status']=='located_across_pages'
    result=render_region_image(path,locator)
    assert [p['pdf_page'] for p in result['parts']]==[1,2]
    assert result['pixel_to_page'] is None
    assert all(p['pixel_to_page'] for p in result['parts'])


def test_figure_and_table_number_are_not_conflated(tmp_path):
    path,ir=source(tmp_path)
    ir.blocks.append(DocumentBlock(block_id='table-cap',block_type='caption',pdf_page=1,reading_order=2,
        bbox=(30,182,210,192),text='Table 1. Not Figure 1.',content_hash=content_hash('table-cap')))
    locator=complete_figure(ir,path,{'page':1,'bbox':[30,35,210,180],'label':'Fig. 1'})
    assert locator['caption_status']=='located' and 'Second line' in locator['caption_text']


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_nonzero_cropbox_partial_pixels_match_full_page(tmp_path,rotation):
    from PIL import ImageChops
    path=tmp_path/'cropped.pdf';pdf=pymupdf.open();page=pdf.new_page(width=300,height=340)
    page.set_cropbox(pymupdf.Rect(50,60,250,280))
    page.draw_rect((10,15,70,100),fill=(1,0,0));page.draw_rect((100,120,180,200),fill=(0,0,1))
    page.set_rotation(rotation);pdf.save(path);pdf.close()
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    with pymupdf.open(path) as pdf:
        page=pdf[0];bbox=[0,0,page.rect.width/2,page.rect.height/2]
        whole=page.get_pixmap(dpi=600,alpha=False)
        expected=Image.open(io.BytesIO(whole.tobytes('png'))).crop((0,0,
            int(__import__('math').ceil(bbox[2]*600/72)),int(__import__('math').ceil(bbox[3]*600/72))))
    loc=region_locator(path,'main',sha,1,bbox)
    actual=Image.open(io.BytesIO(render_region_image(path,loc)['png']))
    assert actual.size==expected.size and ImageChops.difference(actual,expected).getbbox() is None
