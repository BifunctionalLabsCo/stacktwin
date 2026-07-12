import argparse
import os
import subprocess
import sys
import time

import httpx
from dotenv import load_dotenv

from stacktwin.llm import model_for, model_mode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one StackTwin weekly pipeline job")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--user-id")
    command.add_argument("--prefetch-weekly-content", action="store_true")
    args = parser.parse_args()

    load_dotenv(os.getenv("STACKTWIN_JOB_ENV_PATH", "/run/secrets/stacktwin.env"))
    mode = model_mode()
    if mode != "test":
        raise RuntimeError(
            "Production map/reduce mode requires separate model phases; "
            "run this single-model Job with NEBIUS_MODEL_MODE=test"
        )
    model = model_for("map")
    port = int(os.getenv("STACKTWIN_JOB_VLLM_PORT", "8000"))
    base_url = f"http://127.0.0.1:{port}"

    os.environ["NEBIUS_API_URL"] = f"{base_url}/v1"
    os.environ["NEBIUS_API_KEY"] = "stacktwin-local-job"
    os.environ["NEBIUS_TOKEN"] = "stacktwin-local-job"
    os.environ["STORAGE_BACKEND"] = "nebius"
    os.environ["STACKTWIN_PIPELINE_EXECUTION"] = "local"

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
        if args.prefetch_weekly_content:
            from stacktwin.pipeline.ingest import prefetch_weekly_content
            from stacktwin.storage.factory import get_storage

            print(prefetch_weekly_content(get_storage()), flush=True)
        else:
            from stacktwin.api.routes.digest import run_pipeline

            response = run_pipeline(user_id=args.user_id)
            print(response.body.decode("utf-8"), flush=True)
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()


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
