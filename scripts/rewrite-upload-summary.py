"""只重算一份指定 H3S 上传草稿的论文总结及来源核对。"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from backend.ingest.paper_summary import rerun_ready_upload  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--expected-filename", required=True)
    parser.add_argument("--expected-main-sha256", required=True)
    args = parser.parse_args()
    result = rerun_ready_upload(args.task_id, expected_filename=args.expected_filename,
                                expected_main_sha256=args.expected_main_sha256)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
