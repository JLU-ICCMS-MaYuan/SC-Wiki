"""仅通过受控 stdin/stdout 协议执行一次结构推理，无对外端口。"""
import contextlib
import json
import logging
import sys

from .artifacts import verify_bete_artifacts
from .inference import predict


def main():
    try:
        request = json.loads(sys.stdin.read(300 * 1024 + 1))
        if not isinstance(request, dict) or request.get("model_id") != "bete-cso":
            raise ValueError("结构模型请求不正确")
        try:
            verify_bete_artifacts()
        except (OSError, ValueError, KeyError) as exc:
            logging.exception("结构模型制品校验失败")
            print(json.dumps({"error": "模型制品未就绪或校验失败，请重新准备模型", "status": 503}, ensure_ascii=False))
            return
        with contextlib.redirect_stdout(sys.stderr):
            result = predict(request)
        print(json.dumps({"result": result}, ensure_ascii=False, allow_nan=False))
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "status": 400}, ensure_ascii=False))
    except Exception:
        logging.exception("结构推理失败")
        print(json.dumps({"error": "结构模型运行失败，请检查服务日志", "status": 503}, ensure_ascii=False))


if __name__ == "__main__":
    main()
