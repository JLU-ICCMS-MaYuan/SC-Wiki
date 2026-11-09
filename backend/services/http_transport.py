"""本机服务回环直连，其余目标保留原环境代理选择。"""
from ipaddress import ip_address
from urllib.parse import urlsplit


def uses_environment_proxy(url: str) -> bool:
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    if host == 'localhost':
        return False
    try:
        return not ip_address(host).is_loopback
    except ValueError:
        return True
