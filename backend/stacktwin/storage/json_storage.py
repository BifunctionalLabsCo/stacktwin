import json
import os
from stacktwin.profile.schema import DeveloperProfile, WeeklyDigest
from stacktwin.storage.base import StorageBackend


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
        return os.path.join(self.outputs_dir, f"{self._safe_user_id(user_id)}_digest_{week_start}.json")

    def save_profile(self, user_id: str, profile: DeveloperProfile) -> None:
        path = self._profile_path(user_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2)
        print(f"[storage] profile saved: {path}")

    def load_profile(self, user_id: str) -> DeveloperProfile | None:
        path = self._profile_path(user_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return DeveloperProfile(**data)

    def save_digest(self, user_id: str, digest: WeeklyDigest) -> str:
        path = self._digest_path(user_id, digest.week_start)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(digest.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"[storage] digest saved: {path}")
        return path

    def load_latest_digest(self, user_id: str) -> WeeklyDigest | None:
        safe_id = self._safe_user_id(user_id)
        files = sorted([
            f for f in os.listdir(self.outputs_dir)
            if f.startswith(f"{safe_id}_digest_") and f.endswith(".json")
        ], reverse=True)

        if not files:
            return None

        with open(os.path.join(self.outputs_dir, files[0]), encoding="utf-8") as f:
            data = json.load(f)
        return WeeklyDigest(**data)

    def load_digest_history(self, user_id: str) -> list[dict]:
        safe_id = self._safe_user_id(user_id)
        files = sorted([
            f for f in os.listdir(self.outputs_dir)
            if f.startswith(f"{safe_id}_digest_") and f.endswith(".json")
        ], reverse=True)

        history = []
        for filename in files:
            with open(os.path.join(self.outputs_dir, filename), encoding="utf-8") as f:
                data = json.load(f)
                history.append({
                    "week_start": data.get("week_start"),
                    "generated_at": data.get("generated_at"),
                    "items": len(data.get("items", [])),
                    "total_processed": data.get("total_items_processed", 0)
                })
        return history

    def load_digest_by_week(self, user_id: str, week_start: str) -> WeeklyDigest | None:
        path = self._digest_path(user_id, week_start)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return WeeklyDigest(**data)