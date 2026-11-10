"""公开链接证据的有界读取；保存地址不触发模型或网络读取。"""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
import requests
import urllib3


def validate_url(value, *, resolve=False):
    parts=urlsplit(value.strip())
    if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('证据链接必须是无账号密码的HTTP或HTTPS地址')
    if parts.port not in (None,80,443):raise ValueError('证据链接不支持非标准端口')
    if len(value)>8192:raise ValueError('证据链接过长')
    if resolve:public_addresses(parts)
    return value.strip()


def public_addresses(parts):
    addresses=socket.getaddrinfo(parts.hostname,parts.port or (443 if parts.scheme=='https' else 80),type=socket.SOCK_STREAM)
    ips=list(dict.fromkeys(a[4][0] for a in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('证据链接只能读取公开网络地址')
    return ips


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','head','nav'}:self.hidden+=1
        elif tag in {'p','div','br','section','article','h1','h2','li'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','head','nav'}:self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def read_public_link(url, *, max_bytes=10*1024*1024, max_chars=100000):
    current=url
    for _ in range(4):
        validate_url(current)
        parts=urlsplit(current);address=public_addresses(parts)[0]
        # 固定连接到已验证的公网IP，TLS仍校验原主机，避免两次DNS解析的重绑定。
        kwargs={'host':address,'port':parts.port or (443 if parts.scheme=='https' else 80),
                'timeout':urllib3.Timeout(connect=4,read=12),'retries':False}
        if parts.scheme=='https':
            pool=urllib3.HTTPSConnectionPool(**kwargs,server_hostname=parts.hostname,
                assert_hostname=parts.hostname,cert_reqs='CERT_REQUIRED',ca_certs=requests.certs.where())
        else:pool=urllib3.HTTPConnectionPool(**kwargs)
        try:
            path=parts.path or '/'
            if parts.query:path+='?'+parts.query
            response=pool.urlopen('GET',path,headers={'Host':parts.hostname,'User-Agent':'SC-Wiki evidence reader/1.0'},
                redirect=False,preload_content=False)
            try:
                if response.status in {301,302,303,307,308}:
                    current=urljoin(current,response.headers.get('Location',''));continue
                if response.status>=400:raise ValueError('链接读取失败：HTTP '+str(response.status))
                data=bytearray()
                for block in response.stream(65536,decode_content=True):
                    data.extend(block)
                    if len(data)>max_bytes:raise ValueError('链接内容超过10 MiB读取边界')
                media=response.headers.get('content-type','').split(';')[0].lower()
                if media=='application/pdf' or data[:4]==b'%PDF':
                    import pymupdf
                    with pymupdf.open(stream=bytes(data),filetype='pdf') as pdf:
                        if pdf.is_encrypted or pdf.page_count>20:raise ValueError('链接PDF加密或超过20页')
                        content='\\n'.join(page.get_text('text') for page in pdf)
                elif media.startswith('text/') or media in {'','application/xhtml+xml'}:
                    raw=bytes(data).decode('utf-8',errors='replace')
                    if 'html' in media or '<html' in raw[:1000].lower():
                        parser=TextExtractor();parser.feed(raw);content=''.join(parser.parts)
                    else:content=raw
                else:raise ValueError('链接返回的内容类型不支持读取')
                content='\\n'.join(line.strip() for line in content.splitlines() if line.strip())
                if not content:raise ValueError('链接没有可读取正文')
                if len(content)>max_chars:raise ValueError('链接正文超过100000字符，请提供对应原文片段')
                return content
            finally:response.release_conn()
        finally:pool.close()
    raise ValueError('链接重定向次数过多')
