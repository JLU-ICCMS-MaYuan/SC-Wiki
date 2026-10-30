"""把HTTP打开时凭证带入同步处理；后台写回使用快照中的凭证。"""
from contextvars import ContextVar
from fastapi import Header
epoch = ContextVar('workdraft_epoch',default=None)

async def request_workdraft(x_workdraft_epoch: str | None = Header(default=None)):
    token=epoch.set(x_workdraft_epoch)
    try:yield
    finally:epoch.reset(token)
