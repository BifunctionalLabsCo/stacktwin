import argparse
import json
import os
import subprocess
import sys
import time

import httpx
from dotenv import load_dotenv

from stacktwin.llm import app_mode, model_for


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one StackTwin weekly pipeline job")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--user-id")
    command.add_argument("--prefetch-weekly-content", action="store_true")
    parser.add_argument("--prefetch-owner")
    args = parser.parse_args()

    load_dotenv(os.getenv("STACKTWIN_JOB_ENV_PATH", "/run/secrets/stacktwin.env"))
    requested_model_mode = app_mode()
    # Jobs always use S3 so the app can observe their durable state. Preserve
    # the caller's tier separately: a local app run uses Qwen, cloud uses the
    # production map/reduce pair.
    os.environ["STACKTWIN_APP_MODE"] = "cloud"
    os.environ["STACKTWIN_MODEL_MODE"] = requested_model_mode
    port = int(os.getenv("STACKTWIN_JOB_VLLM_PORT", "8000"))
    base_url = f"http://127.0.0.1:{port}"

    os.environ["NEBIUS_API_URL"] = f"{base_url}/v1"
    os.environ["NEBIUS_API_KEY"] = "stacktwin-local-job"
    os.environ["NEBIUS_TOKEN"] = "stacktwin-local-job"
    if args.prefetch_weekly_content:
        _run_model_phase(model_for("map"), port, base_url, _prefetch(args.prefetch_owner))
        return 0

    run_id = _run_model_phase(model_for("map"), port, base_url, _score(args.user_id))
    _run_model_phase(model_for("reduce"), port, base_url, _generate(args.user_id, run_id))
    return 0


def _run_model_phase(model: str, port: int, base_url: str, work):
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            model,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--max-model-len",
            os.getenv("STACKTWIN_JOB_MAX_MODEL_LEN", "4096"),
        ]
    )
    try:
        _wait_for_vllm(server, f"{base_url}/health")
        return work()
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()


def _prefetch(owner_id: str | None):
    def work() -> None:
        from stacktwin.pipeline.ingest import prefetch_weekly_content
        from stacktwin.storage.factory import get_storage

        print(prefetch_weekly_content(get_storage(), owner_id=owner_id), flush=True)

    return work


def _score(user_id: str):
    def work() -> None:
        from stacktwin.api.routes.digest import _run_pipeline

        response = _run_pipeline(user_id=user_id, stop_after_scoring=True)
        print(response.body.decode("utf-8"), flush=True)
        return json.loads(response.body)["run"]["run_id"]

    return work


def _generate(user_id: str, run_id: str):
    def work() -> None:
        from stacktwin.api.routes.digest import _run_pipeline

        response = _run_pipeline(user_id=user_id, run_id=run_id)
        print(response.body.decode("utf-8"), flush=True)

    return work


def _wait_for_vllm(server: subprocess.Popen, health_url: str) -> None:
    deadline = time.monotonic() + int(os.getenv("STACKTWIN_JOB_STARTUP_TIMEOUT", "900"))
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"vLLM exited during startup with code {server.returncode}")
        try:
            if httpx.get(health_url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(5)
    raise TimeoutError("vLLM did not become healthy before the startup timeout")


if __name__ == "__main__":
    raise SystemExit(main())
