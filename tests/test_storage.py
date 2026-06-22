import io
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
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

    assert storage.load_profile_source_hash("live-test@example.com") == "live-hash"
    assert storage.digest_exists("live-test@example.com", "2026-06-15")

    response = storage.client.list_objects_v2(Bucket=storage.bucket, Prefix=f"{prefix}/")
    objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
    if objects:
        storage.client.delete_objects(Bucket=storage.bucket, Delete={"Objects": objects})
