"""预先准备输入，复制请求上下文，并按原编号收集受限并发结果。"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextvars import copy_context


def ordered_extract(items, extract, *, max_workers=2, check=lambda: None, completed=lambda index, value: None):
    from .model_runtime import current_execution, execution_context
    prepared = list(items)
    max_workers = max(1, int(max_workers))
    runtime = current_execution()
    values = [None] * len(prepared)
    stopped = __import__('threading').Event()
    def invoke(index):
        check()
        if runtime:
            # 请求的连接、接收事件和关闭动作相互隔离；检查点和任务代次仍共享。
            child = runtime.fork()
            original_read = child.read_state
            child.read_state = lambda: {**(original_read() or {}), 'status': 'paused'} if stopped.is_set() else original_read()
            with execution_context(child):
                return extract(index, prepared[index])
        return extract(index, prepared[index])
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(prepared) or 1))) as pool:
        pending, next_index = {}, 0
        try:
            while next_index < len(prepared) or pending:
                check()
                while next_index < len(prepared) and len(pending) < max_workers:
                    context = copy_context()
                    pending[pool.submit(context.run, invoke, next_index)] = next_index
                    next_index += 1
                done, _ = wait(pending, timeout=.2, return_when=FIRST_COMPLETED)
                for future in done:
                    index = pending.pop(future)
                    values[index] = future.result()
                    completed(index, values[index])
        except BaseException:
            stopped.set()
            for future in pending:
                future.cancel()
            raise
    return values
