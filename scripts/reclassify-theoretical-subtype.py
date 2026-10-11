"""对指定的已完成上传草稿重跑全文理论二级类型；需给出预期文件名。"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from backend.ingest.theoretical_subtype import rerun_ready_upload  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--expected-filename", required=True)
    args = parser.parse_args()
    result = rerun_ready_upload(args.task_id, expected_filename=args.expected_filename)
    print(json.dumps({"status": result["assessment"]["status"],
                      "value": result["current_value"], "reason": result["assessment"]["reason"],
                      "preserved_user_edit": result["preserved_user_edit"], "checked": result["checked"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
