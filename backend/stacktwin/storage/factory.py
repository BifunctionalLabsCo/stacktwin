import os

from stacktwin.llm import app_mode
from stacktwin.storage.base import StorageBackend
from stacktwin.storage.json_storage import JSONStorage


def get_storage() -> StorageBackend:
    """
    Returns storage for the active application mode.

    Local mode uses file-based JSON storage. Cloud mode uses Nebius Object
    Storage, including all transient weekly pipeline artifacts.

    Usage:
        storage = get_storage()
        storage.save_profile(user_id, profile)
    """
    if app_mode() == "local":
        return JSONStorage(
            profiles_dir=os.getenv("PROFILES_DIR", "profiles"),
            outputs_dir=os.getenv("OUTPUTS_DIR", "outputs"),
        )

    return get_cloud_storage()


def get_cloud_storage() -> StorageBackend:
    """Return the Nebius S3 backend, regardless of the active application mode."""
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
