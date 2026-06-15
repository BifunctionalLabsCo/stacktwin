import os
from stacktwin.storage.base import StorageBackend
from stacktwin.storage.json_storage import JSONStorage


def get_storage() -> StorageBackend:
    """
    Returns the configured storage backend.
    Controlled by STORAGE_BACKEND environment variable.

    Options:
        json        — file-based JSON storage (default)
        postgresql  — PostgreSQL (not yet implemented)

    Usage:
        storage = get_storage()
        storage.save_profile(user_id, profile)
    """
    backend = os.getenv("STORAGE_BACKEND", "json").lower()

    if backend == "json":
        return JSONStorage(
            profiles_dir=os.getenv("PROFILES_DIR", "profiles"),
            outputs_dir=os.getenv("OUTPUTS_DIR", "outputs")
        )

    if backend == "postgresql":
        # TODO: implement PostgreSQLStorage
        # from stacktwin.storage.postgresql_storage import PostgreSQLStorage
        # return PostgreSQLStorage(url=os.getenv("DATABASE_URL"))
        raise NotImplementedError(
            "PostgreSQL storage not yet implemented. "
            "Set STORAGE_BACKEND=json or implement PostgreSQLStorage."
        )

    raise ValueError(f"Unknown storage backend: {backend}. Use 'json' or 'postgresql'.")