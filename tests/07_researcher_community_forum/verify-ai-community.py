"""社区验收兼容入口：#143 已替代 #142 的自动回答语义。"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("verify-answer-threads.py")), run_name="__main__")
