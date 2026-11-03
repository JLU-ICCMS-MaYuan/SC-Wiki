"""仅用于隔离Redis的并发容量探针，不解析PDF、不调用模型。"""
import time
from redis import Redis


def hold_form_slot(redis_url, prefix):
    client = Redis.from_url(redis_url)
    client.eval("""
local current=redis.call('INCR',KEYS[1])
local peak=tonumber(redis.call('GET',KEYS[2]) or '0')
if current>peak then redis.call('SET',KEYS[2],current) end
return current
""", 2, prefix + ':active', prefix + ':peak')
    try:
        deadline = time.monotonic() + 90
        while not client.exists(prefix + ':release'):
            if time.monotonic() >= deadline:
                raise TimeoutError('隔离容量探针等待释放超时')
            time.sleep(0.05)
        return True
    finally:
        client.decr(prefix + ':active')
        client.close()
