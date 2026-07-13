import os
from datetime import UTC, datetime
from urllib.parse import quote

import orjson

from stacktwin.learning.schema import WeeklyTrack
from stacktwin.pipeline.run import PipelineRun
from stacktwin.profile.schema import DeveloperProfile, WeeklyDigest
from stacktwin.storage.base import StorageBackend

PREFETCH_LEASE_SECONDS = int(os.getenv("STACKTWIN_PREFETCH_LEASE_SECONDS", "1800"))


class NebiusS3Storage(StorageBackend):
    """S3-compatible storage backed by Nebius Object Storage."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        prefix: str = "stacktwin",
        client=None,
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client or self._create_client(
            endpoint_url,
            region,
            access_key_id,
            secret_access_key,
        )

    @staticmethod
    def _create_client(endpoint_url, region, access_key_id, secret_access_key):
        try:
            import boto3
            from botocore.client import Config
        except ImportError as error:
            raise RuntimeError(
                "Nebius storage requires boto3. Install the project dependencies first."
            ) from error

        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )

    def _user_key(self, user_id: str) -> str:
        return quote(user_id, safe="")

    def _key(self, suffix: str) -> str:
        return f"{self.prefix}/{suffix}" if self.prefix else suffix

    def _profile_key(self, user_id: str) -> str:
        return self._key(f"profiles/{self._user_key(user_id)}.json")

    def _digest_key(self, user_id: str, week_start: str) -> str:
        return self._key(f"digests/{self._user_key(user_id)}/{week_start}.json")

    def _track_key(self, user_id: str, week_start: str) -> str:
        return self._key(f"tracks/{self._user_key(user_id)}/{week_start}.json")

    def _run_key(self, user_id: str, run: PipelineRun) -> str:
        # created_at first so lexicographic key sort matches chronological order.
        return self._key(f"runs/{self._user_key(user_id)}/{run.created_at}_{run.run_id}.json")

    def _content_snapshot_key(self, week_start: str) -> str:
        return self._key(f"content/{week_start}.json")

    def _content_lease_key(self, week_start: str) -> str:
        return self._key(f"content/{week_start}/prefetch.json")

    def _put_json(self, key: str, data: dict) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=orjson.dumps(data),
            ContentType="application/json",
        )

    def _get_json(self, key: str) -> dict | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as error:
            if _is_not_found(error):
                return None
            raise
        return orjson.loads(response["Body"].read())

    def _exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as error:
            if _is_not_found(error):
                return False
            raise

    def save_profile(
        self,
        user_id: str,
        profile: DeveloperProfile,
        source_hash: str | None = None,
    ) -> None:
        self._put_json(
            self._profile_key(user_id),
            {
                "profile": profile.model_dump(mode="json"),
                "source_hash": source_hash,
            },
        )

    def load_profile(self, user_id: str) -> DeveloperProfile | None:
        data = self._get_json(self._profile_key(user_id))
        if not data:
            return None
        return DeveloperProfile(**data.get("profile", data))

    def load_profile_source_hash(self, user_id: str) -> str | None:
        data = self._get_json(self._profile_key(user_id))
        if not data or "profile" not in data:
            return None
        return data.get("source_hash")

    def save_digest(self, user_id: str, digest: WeeklyDigest) -> str:
        key = self._digest_key(user_id, digest.week_start)
        self._put_json(key, digest.model_dump(mode="json"))
        return f"s3://{self.bucket}/{key}"

    def load_latest_digest(self, user_id: str) -> WeeklyDigest | None:
        keys = self._digest_keys(user_id)
        if not keys:
            return None
        data = self._get_json(keys[-1])
        return WeeklyDigest(**data) if data else None

    def load_digest_history(self, user_id: str) -> list[dict]:
        history = []
        for key in reversed(self._digest_keys(user_id)):
            data = self._get_json(key)
            if data:
                history.append(
                    {
                        "week_start": data.get("week_start"),
                        "generated_at": data.get("generated_at"),
                        "items": len(data.get("items", [])),
                        "total_processed": data.get("total_items_processed", 0),
                    }
                )
        return history

    def load_digest_by_week(self, user_id: str, week_start: str) -> WeeklyDigest | None:
        data = self._get_json(self._digest_key(user_id, week_start))
        return WeeklyDigest(**data) if data else None

    def digest_exists(self, user_id: str, week_start: str) -> bool:
        return self._exists(self._digest_key(user_id, week_start))

    def save_track(self, user_id: str, track: WeeklyTrack) -> str:
        key = self._track_key(user_id, track.week_start)
        self._put_json(key, track.model_dump(mode="json"))
        return f"s3://{self.bucket}/{key}"

    def load_latest_track(self, user_id: str) -> WeeklyTrack | None:
        keys = self._track_keys(user_id)
        if not keys:
            return None
        data = self._get_json(keys[-1])
        return WeeklyTrack(**data) if data else None

    def load_track_history(self, user_id: str) -> list[dict]:
        history = []
        for key in reversed(self._track_keys(user_id)):
            data = self._get_json(key)
            if not data:
                continue
            modules = data.get("modules", [])
            history.append(
                {
                    "track_id": data.get("id"),
                    "week_start": data.get("week_start"),
                    "generated_at": data.get("generated_at"),
                    "modules": len(modules),
                    "planned_minutes": sum(
                        module.get("estimated_minutes", 0) for module in modules
                    ),
                }
            )
        return history

    def load_track_by_week(self, user_id: str, week_start: str) -> WeeklyTrack | None:
        data = self._get_json(self._track_key(user_id, week_start))
        return WeeklyTrack(**data) if data else None

    def track_exists(self, user_id: str, week_start: str) -> bool:
        return self._exists(self._track_key(user_id, week_start))

    def save_run(self, run: PipelineRun) -> None:
        # Run records are immutable per attempt at a given created_at, but a
        # run is mutated in place across stage transitions, so look up its
        # existing key by run_id before writing rather than assuming a fixed key.
        existing_key = self._find_run_key(run.user_id, run.run_id)
        key = existing_key or self._run_key(run.user_id, run)
        self._put_json(key, run.model_dump(mode="json"))

    def load_latest_run(self, user_id: str) -> PipelineRun | None:
        keys = self._run_keys(user_id)
        if not keys:
            return None
        data = self._get_json(keys[-1])
        return PipelineRun(**data) if data else None

    def load_run_history(self, user_id: str, limit: int = 20) -> list[PipelineRun]:
        runs = []
        for key in reversed(self._run_keys(user_id)):
            if len(runs) >= limit:
                break
            data = self._get_json(key)
            if data:
                runs.append(PipelineRun(**data))
        return runs

    def _scored_article_key(self, user_id: str, week_start: str, url: str) -> str:
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self._key(f"scored/{self._user_key(user_id)}/{week_start}/{url_hash}.json")

    def _scored_article_prefix(self, user_id: str, week_start: str) -> str:
        return self._key(f"scored/{self._user_key(user_id)}/{week_start}/")

    def save_scored_article(self, user_id: str, week_start: str, url: str, data: dict) -> None:
        key = self._scored_article_key(user_id, week_start, url)
        self._put_json(key, data)

    def load_scored_articles_for_week(self, user_id: str, week_start: str) -> list[dict]:
        prefix = self._scored_article_prefix(user_id, week_start)
        keys = []
        continuation_token = None
        while True:
            request = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            keys.extend(
                item["Key"]
                for item in response.get("Contents", [])
                if item["Key"].endswith(".json")
            )
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        results = []
        for key in sorted(keys):
            data = self._get_json(key)
            if data:
                results.append(data)
        return results

    def clear_scored_checkpoint(self, user_id: str, week_start: str) -> None:
        prefix = self._scored_article_prefix(user_id, week_start)
        keys_to_delete = []
        continuation_token = None
        while True:
            request = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            keys_to_delete.extend(
                item["Key"] for item in response.get("Contents", [])
            )
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        if keys_to_delete:
            # S3 delete_objects is limited to 1000 keys per call — chunk accordingly.
            for i in range(0, len(keys_to_delete), 1000):
                chunk = keys_to_delete[i : i + 1000]
                self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": k} for k in chunk]},
                )
            print(
                f"[storage] cleared {len(keys_to_delete)} scored checkpoint objects for "
                f"{user_id}/{week_start}"
            )

    def save_content_snapshot(
        self, week_start: str, articles: list[dict], tag_index: dict[str, list[str]] | None
    ) -> str:
        key = self._content_snapshot_key(week_start)
        self._put_json(
            key,
            {"week_start": week_start, "articles": articles, "tag_index": tag_index},
        )
        return f"s3://{self.bucket}/{key}"

    def load_content_snapshot(self, week_start: str) -> dict | None:
        return self._get_json(self._content_snapshot_key(week_start))

    def acquire_content_prefetch_lease(self, week_start: str, owner_id: str) -> bool:
        key = self._content_lease_key(week_start)
        payload = self._new_content_lease(owner_id)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=orjson.dumps(payload),
                ContentType="application/json",
                IfNoneMatch="*",
            )
            return True
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code not in {"PreconditionFailed", "412"}:
                raise

        response = self.client.get_object(Bucket=self.bucket, Key=key)
        lease = orjson.loads(response["Body"].read())
        if not self._can_reclaim_content_lease(lease):
            return False
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=orjson.dumps(payload),
                ContentType="application/json",
                IfMatch=response["ETag"],
            )
            return True
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"PreconditionFailed", "412"}:
                return False
            raise

    def load_content_prefetch_lease(self, week_start: str) -> dict | None:
        return self._get_json(self._content_lease_key(week_start))

    def complete_content_prefetch_lease(self, week_start: str, owner_id: str) -> None:
        self._write_content_lease(week_start, owner_id, "ready")

    def fail_content_prefetch_lease(self, week_start: str, owner_id: str, reason: str) -> None:
        self._write_content_lease(week_start, owner_id, "failed", reason)

    def _write_content_lease(
        self, week_start: str, owner_id: str, status: str, reason: str | None = None
    ) -> None:
        lease = self.load_content_prefetch_lease(week_start)
        if not lease or lease.get("owner_id") != owner_id:
            return
        payload = {
            "owner_id": owner_id,
            "status": status,
            "started_at": lease.get("started_at", datetime.now(UTC).isoformat()),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if reason:
            payload["reason"] = reason[:300]
        self._put_json(self._content_lease_key(week_start), payload)

    @staticmethod
    def _new_content_lease(owner_id: str) -> dict[str, str]:
        now = datetime.now(UTC).isoformat()
        return {"owner_id": owner_id, "status": "running", "started_at": now, "updated_at": now}

    @staticmethod
    def _can_reclaim_content_lease(lease: dict | None) -> bool:
        if not lease or lease.get("status") == "failed":
            return True
        if lease.get("status") != "running":
            return False
        timestamp = lease.get("updated_at") or lease.get("started_at")
        if not isinstance(timestamp, str):
            return True
        try:
            updated_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return True
        return (datetime.now(UTC) - updated_at).total_seconds() >= PREFETCH_LEASE_SECONDS

    def _find_run_key(self, user_id: str, run_id: str) -> str | None:
        for key in self._run_keys(user_id):
            if key.endswith(f"_{run_id}.json"):
                return key
        return None

    def _run_keys(self, user_id: str) -> list[str]:
        return self._object_keys("runs", user_id)

    def _digest_keys(self, user_id: str) -> list[str]:
        return self._object_keys("digests", user_id)

    def _track_keys(self, user_id: str) -> list[str]:
        return self._object_keys("tracks", user_id)

    def _object_keys(self, collection: str, user_id: str) -> list[str]:
        prefix = self._key(f"{collection}/{self._user_key(user_id)}/")
        keys = []
        continuation_token = None

        while True:
            request = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            keys.extend(
                item["Key"]
                for item in response.get("Contents", [])
                if item["Key"].endswith(".json")
            )
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

        return sorted(keys)


def _is_not_found(error: Exception) -> bool:
    response = getattr(error, "response", {})
    return response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}
