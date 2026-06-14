from abc import ABC, abstractmethod
from stacktwin.profile.schema import DeveloperProfile, WeeklyDigest


class StorageBackend(ABC):
    """
    Abstract storage contract.
    Implement this to add a new storage backend.
    Currently: JSONStorage
    Planned:   PostgreSQLStorage
    """

    @abstractmethod
    def save_profile(self, user_id: str, profile: DeveloperProfile) -> None:
        """Save or update a developer profile."""
        pass

    @abstractmethod
    def load_profile(self, user_id: str) -> DeveloperProfile | None:
        """Load a developer profile. Returns None if not found."""
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