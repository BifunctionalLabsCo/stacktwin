import json
from pathlib import Path
from subprocess import CompletedProcess

from stacktwin.api.routes import digest
from stacktwin.jobs.nebius import (
    SubmittedJob,
    submit_weekly_content_prefetch_job,
    submit_weekly_pipeline_job,
)


def test_submit_weekly_pipeline_job_builds_finite_job_command(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("STACKTWIN_APP_MODE=cloud\n")
    monkeypatch.setenv("STACKTWIN_JOB_IMAGE", "registry.example/stacktwin-job:test")
    monkeypatch.setenv("STACKTWIN_JOB_SUBNET_ID", "subnet-test")
    monkeypatch.setenv("STACKTWIN_JOB_ENV_FILE", str(env_file))
    monkeypatch.setenv("NEBIUS_CLI", "/bin/nebius")

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        payload = {
            "metadata": {"id": "job-test", "name": command[command.index("--name") + 1]},
            "status": {"state": "STARTING"},
        }
        return CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("stacktwin.jobs.nebius.subprocess.run", fake_run)

    job = submit_weekly_pipeline_job("ada@example.com")

    command = captured["command"]
    assert command[:4] == ["/bin/nebius", "ai", "job", "create"]
    assert command[command.index("--image") + 1] == "registry.example/stacktwin-job:test"
    assert command[command.index("--args") + 1] == "--user-id ada@example.com"
    assert command[command.index("--restart-policy") + 1] == "never"
    assert command[command.index("--inject-file") + 1].endswith(":/run/secrets/stacktwin.env")
    assert "--preemptible" in command
    assert captured["kwargs"] == {"check": True, "capture_output": True, "text": True}
    assert job.job_id == "job-test"
    assert job.state == "STARTING"


def test_pipeline_route_returns_accepted_job(monkeypatch):
    monkeypatch.setenv("STACKTWIN_APP_MODE", "cloud")
    monkeypatch.setattr(
        digest,
        "submit_weekly_pipeline_job",
        lambda user_id: SubmittedJob("job-test", "stacktwin-weekly-test", "STARTING"),
    )

    response = digest.run_pipeline(user_id="ada@example.com")
    payload = json.loads(response.body)

    assert response.status_code == 202
    assert payload == {
        "status": "submitted",
        "user_id": "ada@example.com",
        "job_id": "job-test",
        "job_name": "stacktwin-weekly-test",
        "job_state": "STARTING",
    }


def test_submit_weekly_content_prefetch_job_builds_prefetch_command(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("STACKTWIN_APP_MODE=cloud\n")
    monkeypatch.setenv("STACKTWIN_JOB_IMAGE", "registry.example/stacktwin-job:test")
    monkeypatch.setenv("STACKTWIN_JOB_SUBNET_ID", "subnet-test")
    monkeypatch.setenv("STACKTWIN_JOB_ENV_FILE", str(env_file))
    monkeypatch.setenv("NEBIUS_CLI", "/bin/nebius")

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return CompletedProcess(
            command,
            0,
            stdout=json.dumps({"metadata": {"id": "job-test", "name": "prefetch"}}),
            stderr="",
        )

    monkeypatch.setattr("stacktwin.jobs.nebius.subprocess.run", fake_run)

    submit_weekly_content_prefetch_job("lease-owner")

    command = captured["command"]
    assert command[command.index("--args") + 1] == (
        "--prefetch-weekly-content --prefetch-owner lease-owner"
    )
    assert command[command.index("--name") + 1].startswith("stacktwin-prefetch-")
