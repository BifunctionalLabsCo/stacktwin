FROM node:22-bookworm-slim AS frontend-build

ARG NEXT_PUBLIC_STACKTWIN_DEMO_MODE=false
ENV NEXT_PUBLIC_STACKTWIN_DEMO_MODE=${NEXT_PUBLIC_STACKTWIN_DEMO_MODE}

WORKDIR /app/src

COPY src/package.json src/package-lock.json ./
RUN npm ci

COPY src ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/root/.nebius/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl \
    && curl -sSL https://storage.eu-north1.nebius.cloud/cli/install.sh | bash \
    && ln -s /root/.nebius/bin/nebius /usr/local/bin/nebius \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .

COPY --from=frontend-build /app/src/out ./src/out

EXPOSE 8000

CMD ["uvicorn", "stacktwin.api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
