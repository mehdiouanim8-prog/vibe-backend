import os
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_LIVENESS_BYTES = 75 * 1024 * 1024

_ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


def storage_root() -> Path:
    configured = os.getenv("ELEMENT_STORAGE_ROOT")

    if configured:
        root = Path(configured)
    else:
        mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

        if mount:
            root = Path(mount) / "element-private"
        else:
            root = Path.cwd() / "private_storage"

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    return root.resolve()


def new_storage_key(
    user_id: int,
    attempt_number: int,
    kind: str,
    extension: str,
) -> str:
    return (
        f"kyc/"
        f"{user_id}/"
        f"{attempt_number}/"
        f"{kind}-"
        f"{secrets.token_hex(16)}"
        f"{extension}"
    )


def resolve_key(key: str) -> Path:
    root = storage_root()

    candidate = (
        root / key
    ).resolve()

    if root not in candidate.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid storage reference.",
        )

    return candidate


def _validate_file_signature(
    header: bytes,
    content_type: str,
) -> None:

    # JPEG
    if content_type == "image/jpeg":
        if not header.startswith(
            b"\xff\xd8\xff"
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid JPEG file.",
            )
        return

    # PNG
    if content_type == "image/png":
        if header[:8] != (
            b"\x89PNG\r\n\x1a\n"
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid PNG file.",
            )
        return

    # WEBP
    if content_type == "image/webp":
        if not (
            header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid WebP file.",
            )
        return

    # MP4 / MOV
    if content_type in {
        "video/mp4",
        "video/quicktime",
    }:
        if len(header) < 12:
            raise HTTPException(
                status_code=400,
                detail="Invalid video file.",
            )

        # ISO Base Media File Format.
        # Usually contains "ftyp" at bytes 4-7.
        if header[4:8] != b"ftyp":
            raise HTTPException(
                status_code=400,
                detail="Invalid MP4/MOV file.",
            )
        return

    # WebM / Matroska
    if content_type == "video/webm":
        if header[:4] != b"\x1a\x45\xdf\xa3":
            raise HTTPException(
                status_code=400,
                detail="Invalid WebM file.",
            )
        return

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type.",
    )


async def save_upload(
    upload: UploadFile,
    *,
    user_id: int,
    attempt_number: int,
    kind: str,
    max_bytes: int,
    allowed_types: dict[str, str],
) -> tuple[str, int]:

    content_type = (
        upload.content_type or ""
    ).lower()

    extension = allowed_types.get(
        content_type
    )

    if not extension:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type.",
        )

    key = new_storage_key(
        user_id,
        attempt_number,
        kind,
        extension,
    )

    destination = resolve_key(
        key
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total = 0
    signature_checked = False
    first_chunk = b""

    try:
        with destination.open("wb") as output:

            while True:
                chunk = await upload.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                if not signature_checked:
                    first_chunk = chunk[:64]

                    _validate_file_signature(
                        first_chunk,
                        content_type,
                    )

                    signature_checked = True

                total += len(chunk)

                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "File is too large. "
                            f"Maximum size is "
                            f"{max_bytes // (1024 * 1024)} MB."
                        ),
                    )

                output.write(chunk)

    except HTTPException:
        destination.unlink(
            missing_ok=True
        )
        raise

    except Exception as exc:
        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=500,
            detail="Could not securely store the file.",
        ) from exc

    finally:
        await upload.close()

    if total == 0:
        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if not signature_checked:
        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=400,
            detail="Could not validate the uploaded file.",
        )

    return key, total