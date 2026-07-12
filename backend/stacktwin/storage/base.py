from abc import ABC, abstractmethod

from stacktwin.learning.schema import WeeklyTrack
from stacktwin.pipeline.run import PipelineRun
from stacktwin.profile.schema import DeveloperProfile, WeeklyDigest


class StorageBackend(ABC):
    """
    Abstract storage contract.
    Implement this to add a new storage backend.
    Implementations must preserve the same profile and digest behavior
    across local and production backends.
    """

    @abstractmethod
    def save_profile(
        self,
        user_id: str,
        profile: DeveloperProfile,
        source_hash: str | None = None,
    ) -> None:
        """Save or update a developer profile."""
        pass

    @abstractmethod
    def load_profile(self, user_id: str) -> DeveloperProfile | None:
        """Load a developer profile. Returns None if not found."""
        pass

    @abstractmethod
    def load_profile_source_hash(self, user_id: str) -> str | None:
        """Load the hash of the source document used for the stored profile."""
        pass

    @abstractmethod
    def save_digest(self, user_id: str, digest: WeeklyDigest) -> str:
        """Save a weekly digest. Returns the storage path/key."""
        pass

    @abstractmethod
    def load_latest_digest(self, user_id: str) -> WeeklyDigest | None:
        """Load the most recent digest for a user. Returns None if not found."""
        pass

    @abstractmethod
    def load_digest_history(self, user_id: str) -> list[dict]:
        """Load summary of all past digests for a user."""
        pass

    @abstractmethod
    def load_digest_by_week(self, user_id: str, week_start: str) -> WeeklyDigest | None:
        """Load a specific week's digest. Returns None if not found."""
        pass

    @abstractmethod
    def digest_exists(self, user_id: str, week_start: str) -> bool:
        """Return whether a completed digest already exists for the user and week."""
        pass

    @abstractmethod
    def save_track(self, user_id: str, track: WeeklyTrack) -> str:
        """Save a generated weekly classroom track and return its storage location."""
        pass

    @abstractmethod
    def load_latest_track(self, user_id: str) -> WeeklyTrack | None:
        """Load the most recent generated classroom track."""
        pass

    @abstractmethod
    def load_track_history(self, user_id: str) -> list[dict]:
        """Load summaries for the user's generated tracks."""
        pass

    @abstractmethod
    def load_track_by_week(self, user_id: str, week_start: str) -> WeeklyTrack | None:
        """Load a generated classroom track for a specific week."""
        pass

    @abstractmethod
    def track_exists(self, user_id: str, week_start: str) -> bool:
        """Return whether a classroom track exists for the user and week."""
        pass

    @abstractmethod
    def save_run(self, run: PipelineRun) -> None:
        """Create or update a durable pipeline run record."""
        pass

    @abstractmethod
    def load_latest_run(self, user_id: str) -> PipelineRun | None:
        """Load the most recently created/updated run for a user. None if none exist."""
        pass

    @abstractmethod
    def load_run_history(self, user_id: str, limit: int = 20) -> list[PipelineRun]:
        """Load the most recent runs for a user, newest first, bounded by limit."""
        pass

    @abstractmethod
    def save_scored_article(self, user_id: str, week_start: str, url: str, data: dict) -> None:
        """
        Persist a single scored article for resumable pipeline runs.
        `data` must contain 'article' and 'score' dicts.
        Implementations that do not support per-article checkpointing may no-op.
        """
        pass

    @abstractmethod
    def load_scored_articles_for_week(self, user_id: str, week_start: str) -> list[dict]:
        """
        Load all scored articles already persisted for (user_id, week_start).
        Returns a list of dicts, each with 'article' and 'score' keys.
        Returns an empty list when no checkpoint exists.
        """
        pass

    @abstractmethod
    def clear_scored_checkpoint(self, user_id: str, week_start: str) -> None:
        """
        Delete all per-article checkpoint files for (user_id, week_start).
        Called after the digest is successfully persisted — checkpoints are only
        needed for crash recovery and are dead weight once the run succeeds.
        """
        pass

    @abstractmethod
    def save_content_snapshot(
        self, week_start: str, articles: list[dict], tag_index: dict[str, list[str]] | None
    ) -> str:
        """Persist the shared weekly source pool and its optional normalized tag index."""
        pass

    @abstractmethod
    def load_content_snapshot(self, week_start: str) -> dict | None:
        """Load the shared weekly source pool, or None when it has not been prefetched."""
        pass
