"""Cellar: S3-compatible object storage, used through boto3.

The bucket is private. Images are never public: the browser gets a short-lived
presigned URL, signed locally with the add-on's key (no network call).
"""

import os
import time

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import Settings


class Cellar:
    def __init__(self, settings: Settings):
        self.bucket = settings.bucket
        self.endpoint = settings.cellar_endpoint
        self.ttl = settings.presign_ttl
        self.s3 = boto3.client(
            "s3",
            # Cellar ignores the region but boto3 wants one: the Cellar doc says "default".
            # (The local moto emulator needs AWS_DEFAULT_REGION=us-east-1.)
            region_name=os.environ.get("AWS_DEFAULT_REGION", "default"),
            endpoint_url=settings.cellar_endpoint,
            aws_access_key_id=settings.cellar_key_id,
            aws_secret_access_key=settings.cellar_key_secret,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                # As advised by the Cellar doc for recent boto3 versions
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                connect_timeout=5,
                read_timeout=20,
                retries={"max_attempts": 2},
            ),
        )
        self._stats_cache: tuple[float, dict] | None = None

    def ensure_bucket(self) -> bool:
        """Create the private bucket if it is missing. Returns True if created."""
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            return False
        except ClientError as err:
            if err.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
        self.s3.create_bucket(Bucket=self.bucket)  # private by default
        return True

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def put(self, key: str, body: bytes, content_type: str) -> float:
        """Upload an object, return the duration in ms."""
        t0 = time.perf_counter()
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        self._stats_cache = None
        return round((time.perf_counter() - t0) * 1000, 1)

    def head(self, key: str) -> dict:
        meta = self.s3.head_object(Bucket=self.bucket, Key=key)
        return {
            "size": meta["ContentLength"],
            "content_type": meta.get("ContentType", ""),
            "etag": meta.get("ETag", "").strip('"'),
            "last_modified": meta.get("LastModified"),
        }

    def presign(self, key: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.ttl
        )

    def unsigned_url(self, key: str) -> str:
        """The same object without a signature: Cellar answers 403."""
        return f"{self.endpoint}/{self.bucket}/{key}"

    def stats(self) -> dict:
        """Objects and bytes stored in the bucket (cached 20 s)."""
        if self._stats_cache and time.monotonic() - self._stats_cache[0] < 20:
            return self._stats_cache[1]
        objects = total = 0
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            for obj in page.get("Contents", []):
                objects += 1
                total += obj["Size"]
        result = {"objects": objects, "bytes": total}
        self._stats_cache = (time.monotonic(), result)
        return result
