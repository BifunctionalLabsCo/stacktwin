import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from stacktwin.llm import app_mode


@dataclass(frozen=True)
class SubmittedJob:
    job_id: str
    name: str
    state: str


def submit_weekly_pipeline_job(user_id: str) -> SubmittedJob:
    """Submit one finite Nebius Job that generates a learner's weekly track."""
    return _submit_job(f"--user-id {user_id}", "weekly")


def submit_weekly_content_prefetch_job(owner_id: str) -> SubmittedJob:
    """Submit one finite Nebius Job that refreshes the shared weekly source pool."""
    return _submit_job(f"--prefetch-weekly-content --prefetch-owner {owner_id}", "prefetch")


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
        _job_setting("PLATFORM", "gpu-l40s-a"),
        "--preset",
        _job_setting("PRESET", "1gpu-8vcpu-32gb"),
        "--disk-size",
        _job_setting("DISK_SIZE", "100Gi"),
        "--shm-size",
        _job_setting("SHM_SIZE", "16Gi"),
        "--subnet-id",
        subnet_id,
        "--timeout",
        _job_setting("TIMEOUT", "2h"),
        "--restart-policy",
        "never",
        "--inject-file",
        f"{env_file}:/run/secrets/stacktwin.env",
        "--format",
        "json",
    ]
    if _job_setting("PREEMPTIBLE", "true").lower() == "true":
        command.append("--preemptible")

    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    return SubmittedJob(
        job_id=payload["metadata"]["id"],
        name=payload["metadata"]["name"],
        state=payload.get("status", {}).get("state", "STARTING"),
    )


def _job_setting(name: str, default: str) -> str:
    """Select isolated compute settings for the requested app model tier.

    The legacy generic setting remains a fallback so existing local deployments
    continue to work. Cloud jobs must not silently inherit a one-GPU local
    runner because the production map/reduce models require tensor parallelism.
    """
    tier = app_mode().upper()
    if tier == "CLOUD":
        default = {
            "PLATFORM": "gpu-h100-sxm",
            "PRESET": "8gpu-128vcpu-1600gb",
            "DISK_SIZE": "600Gi",
            "SHM_SIZE": "64Gi",
            "TIMEOUT": "4h",
            "PREEMPTIBLE": "false",
        }.get(name, default)
        # Generic STACKTWIN_JOB_* settings are the legacy local tier. Do not
        # let them downgrade a cloud run to an undersized one-GPU worker.
        return os.getenv(f"STACKTWIN_CLOUD_JOB_{name}", default)
    return os.getenv(
        f"STACKTWIN_LOCAL_JOB_{name}",
        os.getenv(f"STACKTWIN_JOB_{name}", default),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise OSError(f"{name} is required for Nebius Job execution")
    return value
