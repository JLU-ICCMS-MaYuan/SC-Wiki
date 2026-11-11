from pathlib import Path
import base64, io
import numpy as np
from PIL import Image


def test_actual_axis_detail_keeps_every_horizontal_pixel_and_reports_exact_mapping():
    from backend.ingest.image_feedback import _axis_label_detail
    raw = (Path(__file__).parent/'fixtures/s14-original-energy-axis.png').read_bytes()
    url, metadata = _axis_label_detail(raw, [{'reason_code': 'HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED',
        'suggested_crop_bbox_normalized': [140, 250, 950, 600]}])
    original = Image.open(io.BytesIO(raw)); detail = Image.open(io.BytesIO(base64.b64decode(url.split(',',1)[1])))
    left, top, right, bottom = metadata['bbox_pixels_in_image_2']
    assert left == 0 and right == original.width == detail.width
    assert np.array_equal(np.asarray(detail), np.asarray(original)[top:bottom])
    assert metadata['coordinate_transform']['x_offset'] == 0
    assert metadata['coordinate_transform']['x_scale'] == 1
    assert not metadata.get('tick_values')
