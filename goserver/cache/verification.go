package cache

import "time"

// ReserveVerificationSend 原子预留冷却及邮箱/IP额度；拒绝请求不扣减其他额度。
func ReserveVerificationSend(email, ip string, now time.Time) (int, error) {
	now = now.UTC()
	hour := now.Truncate(time.Hour).Add(time.Hour).Sub(now)
	day := time.Date(now.Year(), now.Month(), now.Day()+1, 0, 0, 0, 0, time.UTC).Sub(now)
	keys := []string{
		"verify:cooldown:" + email,
		"verify:rate:email:hour:" + email + ":" + now.Format("2006010215"),
		"verify:rate:email:day:" + email + ":" + now.Format("20060102"),
		"verify:rate:ip:hour:" + ip + ":" + now.Format("2006010215"),
		"verify:rate:ip:day:" + ip + ":" + now.Format("20060102"),
	}
	return rdb.Eval(ctx, `
local wait = math.max(0, redis.call('PTTL', KEYS[1]))
local limits = {5, 10, 5, 10}
for i = 2, 5 do
  if tonumber(redis.call('GET', KEYS[i]) or '0') >= limits[i-1] then
    wait = math.max(wait, redis.call('PTTL', KEYS[i]))
  end
end
if wait > 0 then return math.ceil(wait / 1000) end
redis.call('SET', KEYS[1], '1', 'PX', 60000)
for i = 2, 5 do
  local value = redis.call('INCR', KEYS[i])
  if value == 1 then
    redis.call('PEXPIRE', KEYS[i], ARGV[(i % 2) + 1])
  end
end
return 0
`, keys, hour.Milliseconds(), day.Milliseconds()).Int()
}

// PublishVerificationCode 仅在邮件发送成功后调用；新码替换旧码并重置尝试次数。
func PublishVerificationCode(email, digest string, ttl time.Duration) error {
	return rdb.Eval(ctx, `
redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
redis.call('DEL', KEYS[2])
return 1
`, []string{"verify:code:" + email, "verify:attempts:" + email}, digest, ttl.Milliseconds()).Err()
}
