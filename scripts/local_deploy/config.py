"""不执行 shell 的本地配置读取与生成。"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
from urllib.parse import quote, unquote, urlparse

FORBIDDEN = {'PATH', 'HOME', 'SHELL', 'BASH_ENV', 'ENV', 'PYTHONPATH', 'PYTHONHOME',
             'LD_PRELOAD', 'LD_LIBRARY_PATH', 'CONDA_EXE', 'CONDA_PREFIX'}


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, sep, value = line.partition('=')
        key = key.strip()
        if not sep or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'.env 第 {number} 行不是有效赋值')
        if key in values or key in FORBIDDEN or key.startswith(('BASH_FUNC_', 'LD_', 'SCWIKI_DEPLOY_')):
            raise ValueError(f'.env 第 {number} 行重复或使用受保护的变量名')
        value = value.strip()
        if '$(' in value or '`' in value or '\x00' in value:
            raise ValueError(f'.env 第 {number} 行含不支持的 shell 表达式')
        literal = value.startswith("'")
        if value.startswith(('"', "'")):
            delimiter = value[0]
            match = re.fullmatch(r"(['\"])((?:\\.|[^\\])*?)\1\s*(?:#.*)?", value)
            if not match:
                raise ValueError(f'.env 第 {number} 行引号不完整')
            value = match[2]
            if delimiter == '"':
                value = re.sub(r'\\([\\"$])', r'\1', value)
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
        if not literal:
            def expand(match):
                if match[1] not in values:
                    raise ValueError(f'.env 第 {number} 行引用未定义变量')
                return values[match[1]]
            value = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', expand, value)
        values[key] = value
    return values


def read_config(root: Path) -> dict[str, str]:
    path = root / '.env'
    if not path.is_file() or path.is_symlink():
        raise ValueError('缺少普通文件 .env，请先执行 make deploy')
    return parse_env(path.read_text(encoding='utf-8'))


def ensure_config(root: Path, database: str = 'scwiki') -> dict[str, str]:
    path = root / '.env'
    if path.exists() or path.is_symlink():
        return read_config(root)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', database):
        raise ValueError('业务数据库名称不受支持')
    password = secrets.token_hex(24)
    data = root.resolve() / '.data'
    values = {
        'MYSQL_DATABASE': database, 'MYSQL_USER': 'scwiki', 'MYSQL_PASSWORD': password,
        'MYSQL_ROOT_PASSWORD': secrets.token_hex(24),
        'DATABASE_URL': f'mysql+pymysql://scwiki:{quote(password)}@127.0.0.1:3307/{database}?charset=utf8mb4',
        'RAG_DATABASE_URL': f'mysql+asyncmy://scwiki:{quote(password)}@127.0.0.1:3307/{database}?charset=utf8mb4',
        'JWT_SECRET_KEY': secrets.token_hex(32), 'REDIS_URL': 'redis://127.0.0.1:6379/0',
        'NEO4J_URI': 'bolt://127.0.0.1:17687', 'NEO4J_USER': 'neo4j',
        'NEO4J_PASSWORD': secrets.token_hex(24), 'QDRANT_HOST': '127.0.0.1',
        'QDRANT_PORT': '6333', 'QDRANT_GRPC_PORT': '6334',
        'SC_WIKI_DATA_DIR': str(data), 'AVATAR_DIR': str(data / 'avatars'),
        'PYTHON_BACKEND_URL': 'http://127.0.0.1:8000', 'GROBID_URL': 'http://127.0.0.1:8070',
        'PORT': '8080', 'BIND_HOST': '127.0.0.1', 'DEBUG': 'false',
        'LLM_API_KEY': '', 'EMBEDDING_API_KEY': '', 'SMTP_PASSWORD': '',
    }
    if any("'" in v or '\n' in v for v in values.values()):
        raise ValueError('部署路径不支持单引号或换行')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write('# SC-Wiki 本机配置；外部模型及 SMTP 凭据请在本机补充。\n')
        stream.writelines(f"{k}='{v}'\n" for k, v in values.items())
    return values


def validate_local(values: dict[str, str], root: Path, *, target: bool = False) -> None:
    for key in ('DATABASE_URL', 'RAG_DATABASE_URL', 'REDIS_URL', 'NEO4J_URI'):
        url = urlparse(values.get(key, ''))
        if url.hostname not in ('localhost', '127.0.0.1'):
            raise ValueError(f'{key} 必须指向本机独占实例')
    main, rag = (urlparse(values[k]) for k in ('DATABASE_URL', 'RAG_DATABASE_URL'))
    if (main.hostname, main.port, main.path) != (rag.hostname, rag.port, rag.path):
        raise ValueError('DATABASE_URL 与 RAG_DATABASE_URL 必须指向同一业务库')
    if not re.fullmatch(r'/[A-Za-z][A-Za-z0-9_]{0,63}', main.path):
        raise ValueError('业务数据库名称不受支持')
    if main.path[1:] in {'mysql', 'sys', 'performance_schema', 'information_schema'}:
        raise ValueError('不允许操作系统数据库')
    if values.get('QDRANT_HOST') not in ('localhost', '127.0.0.1'):
        raise ValueError('Qdrant 必须为本机独占实例')
    if target:
        required = ('MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD',
                    'JWT_SECRET_KEY', 'NEO4J_PASSWORD')
        missing = [name for name in required if not values.get(name)]
        if missing:
            raise ValueError('已有 .env 缺少必要配置：' + ', '.join(missing) + '；请补齐后重试，原文件未修改')
        if Path(values.get('SC_WIKI_DATA_DIR', '')).resolve() != root.resolve() / '.data':
            raise ValueError('目标 SC_WIKI_DATA_DIR 必须为本项目 .data')
        if main.port != 3307 or urlparse(values['REDIS_URL']).port != 6379:
            raise ValueError('目标配置必须使用部署契约中的默认端口')
        if (main.path[1:], unquote(main.username or ''), unquote(main.password or '')) != (
                values['MYSQL_DATABASE'], values['MYSQL_USER'], values['MYSQL_PASSWORD']):
            raise ValueError('DATABASE_URL 与 MYSQL_* 账号配置不一致')
        if (rag.username, rag.password) != (main.username, main.password):
            raise ValueError('RAG_DATABASE_URL 与 DATABASE_URL 必须使用同一本机账号')
        if (urlparse(values['NEO4J_URI']).port != 17687 or values.get('QDRANT_PORT') != '6333'
                or values.get('QDRANT_GRPC_PORT') != '6334' or values.get('PORT') != '8080'
                or values.get('BIND_HOST') != '127.0.0.1'):
            raise ValueError('目标服务端口或回环监听配置与部署契约不一致')


def export_null(root: Path) -> None:
    import sys
    for key, value in read_config(root).items():
        sys.stdout.buffer.write(f'{key}={value}'.encode() + b'\0')


if __name__ == '__main__':
    import sys
    try:
        export_null(Path(sys.argv[1]))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
