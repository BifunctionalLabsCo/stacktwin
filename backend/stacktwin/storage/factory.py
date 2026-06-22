import os

from stacktwin.storage.base import StorageBackend
from stacktwin.storage.json_storage import JSONStorage


def get_storage() -> StorageBackend:
    """
    Returns the configured storage backend.
    Controlled by STORAGE_BACKEND environment variable.

    Options:
        json     - file-based JSON storage (default)
        nebius  - Nebius Object Storage through its S3-compatible API

    Usage:
        storage = get_storage()
        storage.save_profile(user_id, profile)
    """
    backend = os.getenv("STORAGE_BACKEND", "json").lower()

    if backend == "json":
        return JSONStorage(
            profiles_dir=os.getenv("PROFILES_DIR", "profiles"),
            outputs_dir=os.getenv("OUTPUTS_DIR", "outputs"),
        )

    if backend == "nebius":
        from stacktwin.storage.nebius_s3_storage import NebiusS3Storage

        required = {
            "NEBIUS_S3_BUCKET": os.getenv("NEBIUS_S3_BUCKET"),
            "NEBIUS_S3_REGION": os.getenv("NEBIUS_S3_REGION"),
            "NEBIUS_S3_ENDPOINT": os.getenv("NEBIUS_S3_ENDPOINT"),
            "NEBIUS_S3_ACCESS_KEY_ID": os.getenv("NEBIUS_S3_ACCESS_KEY_ID"),
            "NEBIUS_S3_SECRET_ACCESS_KEY": os.getenv("NEBIUS_S3_SECRET_ACCESS_KEY"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise OSError(f"Missing Nebius storage configuration: {', '.join(sorted(missing))}")

        return NebiusS3Storage(
            bucket=required["NEBIUS_S3_BUCKET"],
            region=required["NEBIUS_S3_REGION"],
            endpoint_url=required["NEBIUS_S3_ENDPOINT"],
            access_key_id=required["NEBIUS_S3_ACCESS_KEY_ID"],
            secret_access_key=required["NEBIUS_S3_SECRET_ACCESS_KEY"],
            prefix=os.getenv("NEBIUS_S3_PREFIX", "stacktwin"),
        )

    raise ValueError(f"Unknown storage backend: {backend}. Use 'json' or 'nebius'.")
