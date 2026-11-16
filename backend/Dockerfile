FROM python:3.13-slim

# uv: công cụ cài thư viện Python (nhanh, cài đúng phiên bản trong uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Cài thư viện trước, copy code sau: sửa code không phải cài lại thư viện
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY app ./app

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
