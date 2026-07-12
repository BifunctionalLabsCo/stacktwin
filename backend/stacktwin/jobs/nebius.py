import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubmittedJob:
    job_id: str
    name: str
    state: str


def submit_weekly_pipeline_job(user_id: str) -> SubmittedJob:
    """Submit one finite Nebius Job that generates a learner's weekly track."""
    return _submit_job(f"--user-id {user_id}", "weekly")


def submit_weekly_content_prefetch_job() -> SubmittedJob:
    """Submit one finite Nebius Job that refreshes the shared weekly source pool."""
    return _submit_job("--prefetch-weekly-content", "prefetch")


def _submit_job(job_args: str, job_kind: str) -> SubmittedJob:
    image = _required("STACKTWIN_JOB_IMAGE")
    subnet_id = _required("STACKTWIN_JOB_SUBNET_ID")
    env_file = Path(os.getenv("STACKTWIN_JOB_ENV_FILE", ".env")).resolve()
    if not env_file.is_file():
        raise OSError(f"StackTwin Job env file does not exist: {env_file}")

    name = f"stacktwin-{job_kind}-{uuid.uuid4().hex[:12]}"
    command = [
        os.getenv("NEBIUS_CLI", "nebius"),
        "ai",
        "job",
        "create",
        "--name",
        name,
        "--image",
        image,
        "--container-command",
        "python3 -m stacktwin.pipeline.job",
        "--args",
        job_args,
        "--platform",
        os.getenv("STACKTWIN_JOB_PLATFORM", "gpu-l40s-a"),
        "--preset",
        os.getenv("STACKTWIN_JOB_PRESET", "1gpu-8vcpu-32gb"),
        "--disk-size",
        os.getenv("STACKTWIN_JOB_DISK_SIZE", "100Gi"),
        "--shm-size",
        os.getenv("STACKTWIN_JOB_SHM_SIZE", "16Gi"),
        "--subnet-id",
        subnet_id,
        "--timeout",
        os.getenv("STACKTWIN_JOB_TIMEOUT", "2h"),
        "--restart-policy",
        "never",
        "--inject-file",
        f"{env_file}:/run/secrets/stacktwin.env",
        "--format",
        "json",
    ]
    if os.getenv("STACKTWIN_JOB_PREEMPTIBLE", "true").lower() == "true":
        command.append("--preemptible")

    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    return SubmittedJob(
        job_id=payload["metadata"]["id"],
        name=payload["metadata"]["name"],
        state=payload.get("status", {}).get("state", "STARTING"),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise OSError(f"{name} is required for Nebius Job execution")
    return value
