FROM python:3.12-slim

RUN pip install --no-cache-dir uv

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user:user pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=user:user app ./app

ENV PATH="$HOME/app/.venv/bin:$PATH"

EXPOSE 7860

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
