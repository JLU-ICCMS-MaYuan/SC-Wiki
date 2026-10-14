# Python 后端
ARG PYTHON_BASE=python:3.12-slim
FROM ${PYTHON_BASE}

WORKDIR /app

# 安装编译依赖 → pip install → 清理编译器（减小镜像体积）
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl libgomp1 libcurl4 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements.txt .
COPY scripts/setup_pdf_tools.py ./scripts/setup_pdf_tools.py
COPY backend/ingest/marker-requirements.txt ./backend/ingest/marker-requirements.txt
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir -r requirements.txt \
    && python scripts/setup_pdf_tools.py --root /opt/scwiki/pdf-tools \
    && apt-get purge -y build-essential gcc g++ cpp binutils \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 复制后端代码
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

EXPOSE 8000
ENV SC_WIKI_MARKER_PYTHON=/opt/scwiki/pdf-tools/marker/bin/python \
    SC_WIKI_LLAMA_SERVER=/opt/scwiki/pdf-tools/llama/llama-server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
