"""真实SDK请求与原图像素重放：超限分片不得缩放、丢图或改变坐标归属。"""
import base64
import io
import math
from PIL import Image, ImageDraw
from backend.rag import llm
from backend.tests.test_json_mode_request import install


def original():
    image = Image.new("RGB", (5100, 6600), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, 6600, 101):
        draw.line((0, y, 5099, y), fill=(y % 251, 23, 41), width=3)
    out = io.BytesIO(); image.save(out, format="PNG", dpi=(600, 600))
    return image, "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def decode(url):
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")


def test_actual_sdk_never_sends_the_failed_33120_patch_image(monkeypatch):
    image, url = original()
    client, requests = install(monkeypatch)
    try:
        assert llm.complete_json("Return JSON.", "Read original image 1.", images=[url]) == {"ok": True}
    finally:
        client.close()
    blocks = requests[0]["messages"][1]["content"]
    sizes = [decode(b["image_url"]["url"]).size for b in blocks if b["type"] == "image_url"]
    assert sizes and all(math.ceil(w / 32) * math.ceil(h / 32) <= 30000 for w, h in sizes), sizes
    assert len(sizes) > 1


def test_tiles_keep_every_original_pixel_overlap_and_image_roles():
    import json
    from backend.rag.image_inputs import prepare_image_inputs
    image, url = original()
    small = io.BytesIO(); Image.new("RGB", (31, 47), "blue").save(small, format="PNG")
    second = "data:image/png;base64," + base64.b64encode(small.getvalue()).decode()
    options = {"images": [url, second], "tool_history": [{"role": "tool", "tool_call_id": "original-id", "content": "source"}]}
    prompt, prepared = prepare_image_inputs("Image 1 context; image 2 calibration.", options)
    manifest = json.loads(prompt.split("IMAGE_TILE_MANIFEST=", 1)[1])
    coverage = Image.new("1", image.size)
    draw = ImageDraw.Draw(coverage)
    first = [row for row in manifest if row["original_image"] == 1]
    assert len(first) == 2 and first[0]["bbox_pixels"][3] > first[1]["bbox_pixels"][1]
    for row in first:
        tile = decode(prepared["images"][row["attachment"] - 1])
        box = row["bbox_pixels"]
        assert tile.tobytes() == image.crop(box).tobytes()
        draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=1)
        # 片内位置回到原图；没有重采样或将第二片当另一材料。
        x, y = (box[2] - box[0]) * .37, (box[3] - box[1]) * .61
        assert 0 <= 1000 * (box[0] + x) / image.width <= 1000
        assert 0 <= 1000 * (box[1] + y) / image.height <= 1000
    assert coverage.getextrema() == (1, 1)
    assert manifest[-1]["original_image"] == 2 and manifest[-1]["attachment"] == 3
    assert prepared["images"][-1] == second and options["images"] == [url, second]
    assert prepared["tool_history"] is options["tool_history"]
    # 再次通过入口不重复分片或重复增加说明。
    again_prompt, again = prepare_image_inputs(prompt, prepared)
    assert again_prompt == prompt and again is prepared


def test_unaffected_images_and_remote_urls_stay_byte_equal():
    from backend.rag.image_inputs import prepare_image_inputs
    png = io.BytesIO(); Image.new("RGB", (32, 32)).save(png, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()
    options = {"images": [url, "https://not-fetched.invalid/source.png"]}
    prompt, prepared = prepare_image_inputs("existing JSON prompt", options)
    assert prompt == "existing JSON prompt" and prepared is options


def test_runtime_archives_actual_tiles_and_reuses_same_request(tmp_path, monkeypatch):
    import json
    from backend.tests.test_model_runtime import setup_runtime
    _, url = original()
    client, requests = install(monkeypatch)
    try:
        runtime, context, _ = setup_runtime(tmp_path, monkeypatch)
        with context(runtime):
            assert llm.complete_json("Return JSON.", "Original image 1.", images=[url]) == {"ok": True}
        stored = json.loads(next(tmp_path.rglob("prepared-request.json")).read_text())["request"]
        assert len(stored["images"]) == 2 and "IMAGE_TILE_MANIFEST=" in stored["system_prompt"]
        runtime, context, _ = setup_runtime(tmp_path, monkeypatch)
        with context(runtime):
            assert llm.complete_json("Return JSON.", "Original image 1.", images=[url]) == {"ok": True}
        assert len(requests) == 1
    finally:
        client.close()
