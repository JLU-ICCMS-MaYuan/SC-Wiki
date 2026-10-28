"""同步准备请求的轻量进度；不存科学结果，也不改变任务所有权。"""
import re

from fastapi import HTTPException
from backend.ingest.upload_tasks import redis_client

TTL = 3600


def key(identity, owner):
    if not re.fullmatch(r'[0-9a-f]{32}', identity or ''):
        raise HTTPException(422, detail='准备进度标识无效')
    return f'evidence-preparation:{owner}:{identity}'


def advance(identity, owner, scope, percent):
    if not identity:  # 旧客户端和非交互调用不新增Redis依赖。
        return
    result = redis_client().eval("""
        if redis.call('hget', KEYS[1], 'cancelled') == '1' then return -1 end
        local scope = redis.call('hget', KEYS[1], 'scope')
        if scope and scope ~= ARGV[1] then return -2 end
        local previous = tonumber(redis.call('hget', KEYS[1], 'percent') or '0')
        redis.call('hset', KEYS[1], 'scope', ARGV[1], 'percent', math.max(previous, tonumber(ARGV[2])))
        redis.call('expire', KEYS[1], ARGV[3])
        return 1
    """, 1, key(identity, owner), scope, percent, TTL)
    if result < 0:
        raise HTTPException(409, detail={
            'code': 'evidence_preparation_cancelled' if result == -1 else 'evidence_preparation_conflict',
            'message': '本次核对准备已取消' if result == -1 else '准备进度标识已用于其他请求'})


def read(identity, owner):
    state = redis_client().hgetall(key(identity, owner))
    if not state:
        raise HTTPException(404, detail='准备进度尚未建立或已过期')
    return {'percent': int(state.get('percent', 0)), 'cancelled': state.get('cancelled') == '1'}


def cancel(identity, owner):
    # 即使DELETE先到，也保留墓碑，后来的POST不能恢复准备。
    redis_client().eval("""
        redis.call('hset', KEYS[1], 'cancelled', '1')
        redis.call('expire', KEYS[1], ARGV[1])
    """, 1, key(identity, owner), TTL)
    return {'cancelled': True}
