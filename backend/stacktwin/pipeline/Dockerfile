FROM vllm/vllm-openai:v0.18.0-cu130

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend

RUN python3 -m pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV STORAGE_BACKEND=nebius

ENTRYPOINT ["python3", "-m", "stacktwin.pipeline.job"]
