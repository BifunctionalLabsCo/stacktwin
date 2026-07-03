import io
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from stacktwin.learning.builder import build_weekly_track
from stacktwin.pipeline.run import PipelineRun, SourceRunStatus
from stacktwin.profile.schema import (
    ArticleScore,
    DeveloperProfile,
    DigestItem,
    WeeklyDigest,
)
from stacktwin.storage.json_storage import JSONStorage
from stacktwin.storage.nebius_s3_storage import NebiusS3Storage


class FakeS3Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.delete_calls: list[list[str]] = []

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        try:
            body = self.objects[(Bucket, Key)]
        except KeyError as error:
            raise _not_found("GetObject") from error
        return {"Body": io.BytesIO(body)}

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _not_found("HeadObject")
        return {}

    def list_objects_v2(self, Bucket, Prefix, **kwargs):
        keys = sorted(
            key for bucket, key in self.objects if bucket == Bucket and key.startswith(Prefix)
        )
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def delete_objects(self, Bucket, Delete, **kwargs):
        keys = [item["Key"] for item in Delete.get("Objects", [])]
        self.delete_calls.append(keys)
        for key in keys:
            self.objects.pop((Bucket, key), None)
        return {"Deleted": [{"Key": key} for key in keys]}


class FakeClientError(Exception):
    def __init__(self, operation: str):
        self.response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        super().__init__(f"{operation}: Not found")


def _not_found(operation: str) -> FakeClientError:
    return FakeClientError(operation)


def _profile(name: str = "Ada") -> DeveloperProfile:
    return DeveloperProfile(
        name=name,
        current_role="Backend Engineer",
        current_stack=["Python", "FastAPI"],
        learning=["RAG"],
    )


def _digest(week_start: str = "2026-06-15") -> WeeklyDigest:
    score = ArticleScore(
        relevance=0.9,
        novelty=0.7,
        practicality=0.8,
        difficulty=0.5,
        urgency=0.4,
        stack_match=0.9,
        learning_value=0.9,
        time_cost_minutes=8,
        overall=0.86,
        why_this_matters="Matches the learner's backend goals.",
        recommended_action="read_now",
    )
    item = DigestItem(
        title="A useful systems article",
        url="https://example.com/article",
        source="devto",
        summary="A concise summary.",
        score=score,
        estimated_reading_minutes=8,
        tags=["python"],
    )
    return WeeklyDigest(
        week_start=week_start,
        profile_name="Ada",
        items=[item],
        total_items_processed=12,
        generated_at="2026-06-15T10:00:00+00:00",
    )


def _track(week_start: str = "2026-06-15"):
    return build_weekly_track(_digest(week_start), _profile())


def _run(
    run_id: str = "run-1",
    user_id: str = "ada@example.com",
    target_week: str = "2026-06-15",
    created_at: str = "2026-06-15T08:00:00+00:00",
    status: str = "running",
) -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        user_id=user_id,
        target_week=target_week,
        trigger_type="manual",
        status=status,
        current_stage="queued",
        attempt_number=1,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.fixture(params=["json", "nebius"])
def storage(request, tmp_path):
    if request.param == "json":
        return JSONStorage(
            profiles_dir=str(tmp_path / "profiles"),
            outputs_dir=str(tmp_path / "outputs"),
        )
    return NebiusS3Storage(
        bucket="test-bucket",
        endpoint_url="https://storage.example.com",
        region="test-region",
        access_key_id="test-key",
        secret_access_key="test-secret",
        prefix="contract-tests",
        client=FakeS3Client(),
    )


def test_profile_hash_contract(storage):
    assert storage.load_profile("ada@example.com") is None
    assert storage.load_profile_source_hash("ada@example.com") is None

    storage.save_profile("ada@example.com", _profile(), source_hash="sha256:abc")

    assert storage.load_profile("ada@example.com").name == "Ada"
    assert storage.load_profile_source_hash("ada@example.com") == "sha256:abc"


def test_digest_contract(storage):
    digest = _digest()

    assert not storage.digest_exists("ada@example.com", digest.week_start)
    path = storage.save_digest("ada@example.com", digest)

    assert path
    assert storage.digest_exists("ada@example.com", digest.week_start)
    assert storage.load_digest_by_week("ada@example.com", digest.week_start) == digest
    assert storage.load_latest_digest("ada@example.com") == digest
    assert storage.load_digest_history("ada@example.com") == [
        {
            "week_start": digest.week_start,
            "generated_at": digest.generated_at,
            "items": 1,
            "total_processed": 12,
        }
    ]


def test_weekly_track_contract(storage):
    track = _track()

    assert not storage.track_exists("ada@example.com", track.week_start)
    path = storage.save_track("ada@example.com", track)

    assert path
    assert storage.track_exists("ada@example.com", track.week_start)
    assert storage.load_track_by_week("ada@example.com", track.week_start) == track
    assert storage.load_latest_track("ada@example.com") == track
    assert storage.load_track_history("ada@example.com") == [
        {
            "track_id": track.id,
            "week_start": track.week_start,
            "generated_at": track.generated_at,
            "modules": 1,
            "planned_minutes": track.modules[0].estimated_minutes,
        }
    ]


def test_run_contract_create_and_load_latest(storage):
    assert storage.load_latest_run("ada@example.com") is None
    assert storage.load_run_history("ada@example.com") == []

    run = _run()
    storage.save_run(run)

    loaded = storage.load_latest_run("ada@example.com")
    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.status == "running"


def test_run_contract_stage_transition_updates_in_place(storage):
    run = _run()
    storage.save_run(run)

    run.current_stage = "ingesting"
    run.sources = [SourceRunStatus(source="devto", status="ok", fetched_count=5, duration_ms=120)]
    storage.save_run(run)

    loaded = storage.load_latest_run("ada@example.com")
    assert loaded.current_stage == "ingesting"
    assert loaded.sources == [
        SourceRunStatus(source="devto", status="ok", fetched_count=5, duration_ms=120)
    ]

    history = storage.load_run_history("ada@example.com")
    assert len(history) == 1
    assert history[0].run_id == run.run_id


def test_run_contract_history_is_bounded_and_newest_first(storage):
    older = _run(run_id="run-older", created_at="2026-06-08T08:00:00+00:00")
    newer = _run(run_id="run-newer", created_at="2026-06-15T08:00:00+00:00")
    storage.save_run(older)
    storage.save_run(newer)

    history = storage.load_run_history("ada@example.com", limit=1)
    assert len(history) == 1
    assert history[0].run_id == "run-newer"

    full_history = storage.load_run_history("ada@example.com")
    assert [run.run_id for run in full_history] == ["run-newer", "run-older"]
    assert storage.load_latest_run("ada@example.com").run_id == "run-newer"


def test_run_contract_isolates_users(storage):
    storage.save_run(_run(run_id="run-ada", user_id="ada@example.com"))
    storage.save_run(_run(run_id="run-bo", user_id="bo@example.com"))

    assert storage.load_latest_run("ada@example.com").run_id == "run-ada"
    assert storage.load_latest_run("bo@example.com").run_id == "run-bo"
    assert [r.run_id for r in storage.load_run_history("ada@example.com")] == ["run-ada"]


def test_json_storage_reads_legacy_profile(tmp_path):
    storage = JSONStorage(
        profiles_dir=str(tmp_path / "profiles"),
        outputs_dir=str(tmp_path / "outputs"),
    )
    path = storage._profile_path("legacy@example.com")
    path_data = _profile("Legacy").model_dump_json()
    with open(path, "w", encoding="utf-8") as profile_file:
        profile_file.write(path_data)

    assert storage.load_profile("legacy@example.com").name == "Legacy"
    assert storage.load_profile_source_hash("legacy@example.com") is None


def test_clear_scored_checkpoint_chunks_s3_deletes():
    client = FakeS3Client()
    storage = NebiusS3Storage(
        bucket="test-bucket",
        endpoint_url="https://storage.example.com",
        region="test-region",
        access_key_id="test-key",
        secret_access_key="test-secret",
        prefix="contract-tests",
        client=client,
    )

    user_id = "ada@example.com"
    week_start = "2026-06-15"
    for index in range(1001):
        storage.save_scored_article(
            user_id,
            week_start,
            url=f"https://example.com/article-{index}",
            data={
                "article": {"url": f"https://example.com/article-{index}"},
                "score": {"overall": 0.9},
            },
        )

    storage.clear_scored_checkpoint(user_id, week_start)

    assert len(client.delete_calls) == 2
    assert len(client.delete_calls[0]) == 1000
    assert len(client.delete_calls[1]) == 1
    assert storage.load_scored_articles_for_week(user_id, week_start) == []


@pytest.mark.skipif(
    os.getenv("RUN_NEBIUS_STORAGE_TESTS", "false").lower() != "true",
    reason="Set RUN_NEBIUS_STORAGE_TESTS=true to exercise the configured Nebius bucket.",
)
def test_live_nebius_storage_contract():
    load_dotenv()
    required = [
        "NEBIUS_S3_BUCKET",
        "NEBIUS_S3_REGION",
        "NEBIUS_S3_ENDPOINT",
        "NEBIUS_S3_ACCESS_KEY_ID",
        "NEBIUS_S3_SECRET_ACCESS_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]
    assert not missing, f"Missing live storage configuration: {', '.join(missing)}"

    prefix = f"{os.getenv('NEBIUS_S3_TEST_PREFIX', 'stacktwin-tests')}/{uuid4().hex}"
    storage = NebiusS3Storage(
        bucket=os.environ["NEBIUS_S3_BUCKET"],
        endpoint_url=os.environ["NEBIUS_S3_ENDPOINT"],
        region=os.environ["NEBIUS_S3_REGION"],
        access_key_id=os.environ["NEBIUS_S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["NEBIUS_S3_SECRET_ACCESS_KEY"],
        prefix=prefix,
    )

    storage.save_profile("live-test@example.com", _profile(), source_hash="live-hash")
    storage.save_digest("live-test@example.com", _digest())
    storage.save_track("live-test@example.com", _track())

    assert storage.load_profile_source_hash("live-test@example.com") == "live-hash"
    assert storage.digest_exists("live-test@example.com", "2026-06-15")
    assert storage.track_exists("live-test@example.com", "2026-06-15")

    response = storage.client.list_objects_v2(Bucket=storage.bucket, Prefix=f"{prefix}/")
    objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
    if objects:
        storage.client.delete_objects(Bucket=storage.bucket, Delete={"Objects": objects})
