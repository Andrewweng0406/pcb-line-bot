import os
import boto3
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileStorage:
    def __init__(self):
        self.use_s3 = settings.AWS_ENABLED and settings.AWS_S3_BUCKET
        self.local_upload_dir = Path(settings.UPLOAD_DIR)
        self.local_upload_dir.mkdir(parents=True, exist_ok=True)

        if self.use_s3:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                logger.info(f"S3 storage initialized for bucket {settings.AWS_S3_BUCKET}")
            except Exception as e:
                logger.warning(f"S3 initialization failed: {e}, falling back to local storage")
                self.use_s3 = False
        else:
            self.s3_client = None

    def save_upload(self, file_path: str, file_bytes: bytes) -> str:
        try:
            if self.use_s3:
                s3_key = f"uploads/{Path(file_path).name}"
                self.s3_client.put_object(
                    Bucket=settings.AWS_S3_BUCKET,
                    Key=s3_key,
                    Body=file_bytes
                )
                url = f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"
                logger.info(f"File saved to S3: {url}")
                return url
            else:
                local_path = self.local_upload_dir / Path(file_path).name
                with open(local_path, "wb") as f:
                    f.write(file_bytes)
                logger.info(f"File saved locally: {local_path}")
                return str(local_path)
        except Exception as e:
            logger.error(f"Error saving upload: {e}")
            raise

    def get_upload(self, file_key: str) -> bytes:
        try:
            if self.use_s3 and file_key.startswith("s3://"):
                bucket = settings.AWS_S3_BUCKET
                key = file_key.replace(f"s3://{bucket}/", "")
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                return response["Body"].read()
            else:
                with open(file_key, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Error getting upload: {e}")
            raise

    def save_export(self, filename: str, file_bytes: bytes) -> str:
        try:
            if self.use_s3:
                s3_key = f"exports/{filename}"
                self.s3_client.put_object(
                    Bucket=settings.AWS_S3_BUCKET,
                    Key=s3_key,
                    Body=file_bytes
                )
                url = f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
                logger.info(f"Export saved to S3: {s3_key}")
                return url
            else:
                export_dir = Path("exports")
                export_dir.mkdir(exist_ok=True)
                local_path = export_dir / filename
                with open(local_path, "wb") as f:
                    f.write(file_bytes)
                logger.info(f"Export saved locally: {local_path}")
                return f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
        except Exception as e:
            logger.error(f"Error saving export: {e}")
            raise

    def cleanup(self, file_path: str):
        try:
            if not self.use_s3 and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up local file: {file_path}")
        except Exception as e:
            logger.warning(f"Error cleaning up file: {e}")


file_storage = FileStorage()
