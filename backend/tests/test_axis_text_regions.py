from PIL import Image,ImageDraw
from backend.ingest.image_geometry import axis_text_regions


def test_text_from_adjacent_panel_is_not_borrowed_when_its_box_overlaps_frame():
    image=Image.new('RGB',(100,160),'white');draw=ImageDraw.Draw(image)
    for box in [(15,32,22,44),(15,70,22,82),(15,120,22,132)]:draw.rectangle(box,outline='black')
    regions=axis_text_regions(image,45,[250,900])
    assert len(regions)==2
    assert all(250<=(box[1]+box[3])/2<=900 for box in regions)


def test_printed_endpoint_label_can_straddle_a_real_frame_boundary():
    image=Image.new("RGB",(100,160),"white");draw=ImageDraw.Draw(image)
    for box in [(15,32,22,44),(15,70,22,82),(15,120,22,132)]:draw.rectangle(box,outline="black")
    draw.line((45,40,98,40),fill="black",width=1)
    regions=axis_text_regions(image,45,[250,900])
    assert len(regions)==3
    assert regions[0][1]<=250<=regions[0][3]
