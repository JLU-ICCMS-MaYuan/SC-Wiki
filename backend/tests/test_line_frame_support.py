import pytest
from PIL import Image,ImageDraw
from backend.ingest.chart_calibration import ChartReadingError


def test_frame_ink_cannot_prove_a_curve_point_but_visible_curve_branch_can():
    from backend.ingest.chart_calibration import verify_line_point_support
    image=Image.new('RGB',(400,400),'white');draw=ImageDraw.Draw(image)
    draw.rectangle((50,50,350,350),outline='blue',width=3)
    draw.line((100,300,250,90),fill='blue',width=3)
    point={'x':875,'y':125,'pixel_error':15}
    with pytest.raises(ChartReadingError) as error:
        verify_line_point_support(image,point,[125,125,875,875],localization_error=15)
    assert error.value.details['reason_code']=='LINE_POINT_ONLY_FRAME_INK'
    assert error.value.details['stroke_geometry_candidates']
    draw.line((300,100,350,50),fill='blue',width=3)
    assert verify_line_point_support(image,point,[125,125,875,875],localization_error=15)['supported']
