"""运行 python -m backend.community worker；只消费按需 AI 任务。"""
import argparse
import multiprocessing
import signal
import time
from .worker import consume


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["worker"])
    parser.parse_args()
    context = multiprocessing.get_context("spawn")
    children = [context.Process(target=consume) for _ in range(2)]
    try:
        for child in children:
            child.start()
        def stop(signum, frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop)
        from .service import reconcile
        while True:
            for index, child in enumerate(children):
                if not child.is_alive():
                    child.join()
                    replacement = context.Process(target=consume)
                    replacement.start()
                    children[index] = replacement
            try:
                reconcile()
            except Exception:
                pass  # 依赖短暂不可用时保留任务，下个周期重查。
            time.sleep(10)
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            child.join(timeout=10)


if __name__ == "__main__":
    main()
