"""当前模型的非流式结构化读图；独立于文本流式解析。"""
import base64
import io
import secrets
from PIL import Image, ImageDraw, ImageFont


def complete_image_json(system_prompt, user_prompt, *, images, read_timeout=180):
    from backend.rag.llm_context import get_llm_config
    from backend.rag.llm_client import get_llm_client
    from backend.rag.llm import _extract_json
    config=get_llm_config()
    response=get_llm_client(read_timeout=read_timeout).chat.completions.create(
        model=config.model, messages=[dict(role="system",content=system_prompt),
        dict(role="user",content=[dict(type="text",text=user_prompt),
             *(dict(type="image_url",image_url=dict(url=url)) for url in images)])],
        response_format={"type":"json_object"}, stream=False, max_tokens=8192)
    if response.choices[0].finish_reason != "stop":
        raise ValueError("模型标定输出未完整结束，保留原图，不采用截断结果")
    return _extract_json(response.choices[0].message.content or "")


def verify_image_capability():
    code="".join(str(secrets.randbelow(10)) for _ in range(6))
    image=Image.new("RGB",(480,130),"white")
    ImageDraw.Draw(image).text((70,20),code,fill="black",font=ImageFont.load_default(size=72))
    output=io.BytesIO();image.save(output,format="PNG")
    result=complete_image_json('只读取附图中的六位数字，返回 JSON {"code":"..."}；无法读取返回空字符串。',
        "图中的六位数字是什么？",images=["data:image/png;base64,"+base64.b64encode(output.getvalue()).decode()],read_timeout=60)
    return str(result.get("code") or "").strip()==code
