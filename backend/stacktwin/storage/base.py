from abc import ABC, abstractmethod

from stacktwin.learning.schema import WeeklyTrack
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
