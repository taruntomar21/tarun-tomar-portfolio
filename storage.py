
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

import boto3
from botocore.config import Config
from PIL import Image, ImageOps
from pypdf import PdfReader
from flask import current_app, g, has_request_context

from extensions import db
from models import Asset
from services import ValidationError


Image.MAX_IMAGE_PIXELS = 20_000_000

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
RESUME_EXTENSIONS = {".pdf"}


def s3():
    c = current_app.config
    return boto3.client(
        "s3",
        region_name=c["S3_REGION"],
        endpoint_url=c["S3_ENDPOINT_URL"],
        aws_access_key_id=c["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=c["S3_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )


def reference_static_asset(relative_path, purpose="image"):
    """Reference an existing, repository-managed file inside Flask's static folder."""
    if not isinstance(relative_path, str):
        raise ValidationError("Enter a valid static file path.")

    relative_path = relative_path.strip().replace("\\", "/")

    if not relative_path or "\x00" in relative_path:
        raise ValidationError("Enter a static file path.")

    path = Path(relative_path)

    if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
        raise ValidationError("Use a relative path inside the static folder.")

    if path.suffix.lower() not in (
        RESUME_EXTENSIONS if purpose == "resume" else IMAGE_EXTENSIONS
    ):
        if purpose == "resume":
            raise ValidationError("Resume files must be PDF files.")
        raise ValidationError("Use JPG, PNG, or WebP image files.")

    static_root = Path(current_app.static_folder).resolve()
    file_path = (static_root / path).resolve()

    if not file_path.is_relative_to(static_root) or not file_path.is_file():
        raise ValidationError(
            "Static file not found. Check the path and ensure the file exists "
            "inside the static folder."
        )

    if file_path.is_symlink():
        raise ValidationError("Symbolic links are not supported for static assets.")

    if purpose == "resume":
        try:
            with file_path.open("rb") as file:
                header = file.read(5)
            if header != b"%PDF-":
                raise ValueError()

            pdf = PdfReader(str(file_path), strict=True)
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError()

            root = pdf.trailer["/Root"]
            if (
                any(key in root for key in ("/OpenAction", "/AA"))
                or "/JavaScript" in str(root.get("/Names", ""))
            ):
                raise ValueError()

            for page in pdf.pages:
                if "/AA" in page:
                    raise ValueError()
        except Exception:
            raise ValidationError(
                "PDF must be readable, unencrypted, and free of active document actions."
            )

        mime = "application/pdf"
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(file_path) as image:
                    image.verify()
                with Image.open(file_path) as image:
                    image.load()
        except Exception:
            raise ValidationError("Image is invalid or exceeds the safe pixel limit.")

        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }[file_path.suffix.lower()]

    key = f"static:{path.as_posix()}"
    asset = db.session.scalar(db.select(Asset).where(Asset.key == key))

    if asset:
        asset.filename = file_path.name
        asset.mimetype = mime
        asset.size = file_path.stat().st_size
        asset.purpose = purpose
    else:
        asset = Asset(
            key=key,
            filename=file_path.name,
            mimetype=mime,
            size=file_path.stat().st_size,
            purpose=purpose,
        )
        db.session.add(asset)

    db.session.flush()
    return asset


def save_upload(upload, purpose="image"):
    if not upload or not upload.filename:
        return None

    # Render's local filesystem is temporary. Use repository-managed static
    # files there unless a persistent storage service is deliberately configured.
    backend = current_app.config.get("STORAGE_BACKEND", "local")
    if current_app.config.get("APP_ENV") == "production" and backend != "s3":
        raise ValidationError(
            "Direct uploads are disabled on this deployment. Add the file to "
            "the repository's static folder and enter its relative static path."
        )

    raw = upload.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise ValidationError("Each upload must be 10 MB or smaller.")

    if purpose == "resume":
        if not upload.filename.lower().endswith(".pdf") or not raw.startswith(b"%PDF-"):
            raise ValidationError("Upload a valid PDF resume.")

        try:
            pdf = PdfReader(BytesIO(raw), strict=True)
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError()

            root = pdf.trailer["/Root"]
            if (
                any(key in root for key in ("/OpenAction", "/AA"))
                or "/JavaScript" in str(root.get("/Names", ""))
            ):
                raise ValueError()

            for page in pdf.pages:
                if "/AA" in page:
                    raise ValueError()
        except Exception:
            raise ValidationError(
                "PDF must be readable, unencrypted, and free of active document actions."
            )

        extension = "pdf"
        mime = "application/pdf"
    else:
        if Path(upload.filename).suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValidationError("Use JPG, PNG, or WebP images.")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = Image.open(BytesIO(raw))
                image.verify()

                image = ImageOps.exif_transpose(
                    Image.open(BytesIO(raw))
                ).convert("RGB")
                image.thumbnail((1800, 1800))

                output = BytesIO()
                image.save(output, "WEBP", quality=85)
                raw = output.getvalue()
        except Exception:
            raise ValidationError("Image is invalid or exceeds the safe pixel limit.")

        extension = "webp"
        mime = "image/webp"

    key = f"portfolio/{uuid4().hex}.{extension}"

    if backend == "s3":
        s3().put_object(
            Bucket=current_app.config["S3_BUCKET"],
            Key=key,
            Body=raw,
            ContentType=mime,
        )
    elif backend == "local":
        path = Path(current_app.config["UPLOAD_ROOT"]) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    else:
        raise ValidationError("File uploads are disabled for the configured storage backend.")

    if has_request_context():
        if not hasattr(g, "uploaded_keys"):
            g.uploaded_keys = []
        g.uploaded_keys.append(key)

    asset = Asset(
        key=key,
        filename=f"{purpose}.{extension}",
        mimetype=mime,
        size=len(raw),
        purpose=purpose,
    )
    db.session.add(asset)
    db.session.flush()
    return asset


def delete_key(key):
    # Repository files must never be deleted by database cleanup.
    if key.startswith("static:"):
        return

    if current_app.config["STORAGE_BACKEND"] == "s3":
        s3().delete_object(
            Bucket=current_app.config["S3_BUCKET"],
            Key=key,
        )
    else:
        (Path(current_app.config["UPLOAD_ROOT"]) / key).unlink(missing_ok=True)


def remove_blob(asset):
    delete_key(asset.key)
