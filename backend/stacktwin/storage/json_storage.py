import json
import os
from datetime import UTC, datetime

from stacktwin.learning.schema import WeeklyTrack
from stacktwin.pipeline.run import PipelineRun
from stacktwin.profile.schema import DeveloperProfile, WeeklyDigest
from stacktwin.storage.base import StorageBackend

# Runs kept per user in the JSON backend. Older runs are dropped on write
# so a single user's run history file cannot grow without bound.
MAX_STORED_RUNS_PER_USER = 100


class JSONStorage(StorageBackend):
    """
    File-based storage using JSON files.
    Simple, no dependencies, works for MVP and hackathon demo.

    File structure:
        profiles/
            soumya@gmail.com_profile.json
            john@company.com_profile.json
        outputs/
            soumya@gmail.com_digest_2026-06-14.json
            john@company.com_digest_2026-06-14.json
    """

    def __init__(self, profiles_dir: str = "profiles", outputs_dir: str = "outputs"):
        self.profiles_dir = profiles_dir
        self.outputs_dir = outputs_dir
        os.makedirs(profiles_dir, exist_ok=True)
        os.makedirs(outputs_dir, exist_ok=True)

    def _safe_user_id(self, user_id: str) -> str:
        """
        Sanitise user_id for use in filenames.
        Replaces characters that are invalid in filenames.
        """
        return user_id.replace("/", "_").replace("\\", "_").replace(":", "_")

    def _profile_path(self, user_id: str) -> str:
        return os.path.join(self.profiles_dir, f"{self._safe_user_id(user_id)}_profile.json")

    def _digest_path(self, user_id: str, week_start: str) -> str:
        filename = f"{self._safe_user_id(user_id)}_digest_{week_start}.json"
        return os.path.join(self.outputs_dir, filename)

    def _track_path(self, user_id: str, week_start: str) -> str:
        filename = f"{self._safe_user_id(user_id)}_track_{week_start}.json"
        return os.path.join(self.outputs_dir, filename)

    def _runs_path(self, user_id: str) -> str:
        filename = f"{self._safe_user_id(user_id)}_runs.json"
        return os.path.join(self.outputs_dir, filename)

    def _content_snapshot_path(self, week_start: str) -> str:
        return os.path.join(self.outputs_dir, f"content_{week_start}.json")

    def save_profile(
        self,
        user_id: str,
        profile: DeveloperProfile,
        source_hash: str | None = None,
    ) -> None:
        path = self._profile_path(user_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "profile": profile.model_dump(mode="json"),
                    "source_hash": source_hash,
                },
                f,
                indent=2,
            )
        print(f"[storage] profile saved: {path}")

    def load_profile(self, user_id: str) -> DeveloperProfile | None:
        path = self._profile_path(user_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        profile_data = data.get("profile", data)
        return DeveloperProfile(**profile_data)

    def load_profile_source_hash(self, user_id: str) -> str | None:
        path = self._profile_path(user_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("source_hash") if "profile" in data else None

    def save_digest(self, user_id: str, digest: WeeklyDigest) -> str:
        path = self._digest_path(user_id, digest.week_start)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(digest.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"[storage] digest saved: {path}")
        return path

    def load_latest_digest(self, user_id: str) -> WeeklyDigest | None:
        safe_id = self._safe_user_id(user_id)
        files = sorted(
            [
                f
                for f in os.listdir(self.outputs_dir)
                if f.startswith(f"{safe_id}_digest_") and f.endswith(".json")
            ],
            reverse=True,
        )

        if not files:
            return None

        with open(os.path.join(self.outputs_dir, files[0]), encoding="utf-8") as f:
            data = json.load(f)
        return WeeklyDigest(**data)

    def load_digest_history(self, user_id: str) -> list[dict]:
        safe_id = self._safe_user_id(user_id)
        files = sorted(
            [
                f
                for f in os.listdir(self.outputs_dir)
                if f.startswith(f"{safe_id}_digest_") and f.endswith(".json")
            ],
            reverse=True,
        )

        history = []
        for filename in files:
            with open(os.path.join(self.outputs_dir, filename), encoding="utf-8") as f:
                data = json.load(f)
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
        path = self._digest_path(user_id, week_start)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return WeeklyDigest(**data)

    def digest_exists(self, user_id: str, week_start: str) -> bool:
        return os.path.exists(self._digest_path(user_id, week_start))

    def save_track(self, user_id: str, track: WeeklyTrack) -> str:
        path = self._track_path(user_id, track.week_start)
        with open(path, "w", encoding="utf-8") as track_file:
            json.dump(track.model_dump(mode="json"), track_file, indent=2, ensure_ascii=False)
        print(f"[storage] track saved: {path}")
        return path

    def load_latest_track(self, user_id: str) -> WeeklyTrack | None:
        files = self._track_files(user_id)
        if not files:
            return None
        with open(os.path.join(self.outputs_dir, files[0]), encoding="utf-8") as track_file:
            return WeeklyTrack(**json.load(track_file))

    def load_track_history(self, user_id: str) -> list[dict]:
        history = []
        for filename in self._track_files(user_id):
            with open(os.path.join(self.outputs_dir, filename), encoding="utf-8") as track_file:
                data = json.load(track_file)
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
        path = self._track_path(user_id, week_start)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as track_file:
            return WeeklyTrack(**json.load(track_file))

    def track_exists(self, user_id: str, week_start: str) -> bool:
        return os.path.exists(self._track_path(user_id, week_start))

    def save_run(self, run: PipelineRun) -> None:
        path = self._runs_path(run.user_id)
        runs = self._load_runs(run.user_id)
        runs = [r for r in runs if r.run_id != run.run_id]
        runs.append(run)
        runs.sort(key=lambda r: r.created_at, reverse=True)
        runs = runs[:MAX_STORED_RUNS_PER_USER]
        with open(path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode="json") for r in runs], f, indent=2, ensure_ascii=False)

    def load_latest_run(self, user_id: str) -> PipelineRun | None:
        runs = self._load_runs(user_id)
        return runs[0] if runs else None

    def load_run_history(self, user_id: str, limit: int = 20) -> list[PipelineRun]:
        return self._load_runs(user_id)[:limit]

    def _load_runs(self, user_id: str) -> list[PipelineRun]:
        path = self._runs_path(user_id)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        runs = [PipelineRun(**item) for item in data]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs

    def _scored_dir(self, user_id: str, week_start: str) -> str:
        return os.path.join(
            self.outputs_dir, "scored", self._safe_user_id(user_id), week_start
        )

    def save_scored_article(self, user_id: str, week_start: str, url: str, data: dict) -> None:
        import hashlib
        scored_dir = self._scored_dir(user_id, week_start)
        os.makedirs(scored_dir, exist_ok=True)
        url_hash = hashlib.md5(url.encode()).hexdigest()
        path = os.path.join(scored_dir, f"{url_hash}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_scored_articles_for_week(self, user_id: str, week_start: str) -> list[dict]:
        scored_dir = self._scored_dir(user_id, week_start)
        if not os.path.exists(scored_dir):
            return []
        results = []
        for filename in sorted(os.listdir(scored_dir)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(scored_dir, filename)
            try:
                with open(path, encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception as exc:
                print(f"[storage] skipping corrupt checkpoint file {filename}: {exc}")
        return results

    def clear_scored_checkpoint(self, user_id: str, week_start: str) -> None:
        import shutil
        scored_dir = self._scored_dir(user_id, week_start)
        if os.path.exists(scored_dir):
            shutil.rmtree(scored_dir)
            print(f"[storage] cleared scored checkpoint: {scored_dir}")
            # Remove parent dirs (user, then scored root) if now empty
            parents = [os.path.dirname(scored_dir), os.path.dirname(os.path.dirname(scored_dir))]
            for parent in parents:
                try:
                    os.rmdir(parent)
                except OSError:
                    break  # not empty or doesn't exist — stop

    def save_content_snapshot(
        self, week_start: str, articles: list[dict], tag_index: dict[str, list[str]] | None
    ) -> str:
        path = self._content_snapshot_path(week_start)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "week_start": week_start,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "articles": articles,
                    "tag_index": tag_index,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        return path

    def load_content_snapshot(self, week_start: str) -> dict | None:
        path = self._content_snapshot_path(week_start)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _track_files(self, user_id: str) -> list[str]:
        prefix = f"{self._safe_user_id(user_id)}_track_"
        return sorted(
            [
                filename
                for filename in os.listdir(self.outputs_dir)
                if filename.startswith(prefix) and filename.endswith(".json")
            ],
            reverse=True,
        )
