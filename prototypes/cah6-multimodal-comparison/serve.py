"""只读本机Demo：只暴露对照结果和两份原PDF的页面，不代理业务API或模型。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlparse


def source_path(data, route):
    if route == "/api/report":
        return data / "report.json", "application/json"
    match = re.fullmatch(r"/page/(main|supplementary)/([1-9]\d*)\.jpg", route)
    if match:
        return data / "pages" / match[1] / (match[2] + ".jpg"), "image/jpeg"
    match = re.fullmatch(r"/source/(main|supplementary)\.pdf", route)
    if match:
        return data / "sources" / (match[1] + ".pdf"), "application/pdf"
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--port", type=int, default=5197)
    args = p.parse_args()
    data = args.data.resolve()
    html = Path(__file__).with_name("index.html")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlparse(self.path).path
            source = (html, "text/html; charset=utf-8") if route == "/" else source_path(data, route)
            if not source or not source[0].is_file():
                self.send_error(404)
                return
            payload = source[0].read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", source[1])
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    print(f"Demo: http://127.0.0.1:{args.port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
