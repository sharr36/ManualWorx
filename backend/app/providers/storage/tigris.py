"""Tigris (S3-compatible) storage provider."""

import asyncio
from functools import partial

import boto3

from .base import StorageProvider


class TigrisStorageProvider(StorageProvider):
    """Object storage via Tigris (Fly.io S3-compatible)."""

    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            ),
        )
        return await self.get_url(key)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                self._client.get_object,
                Bucket=self.bucket,
                Key=key,
            ),
        )
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._client.delete_object,
                Bucket=self.bucket,
                Key=key,
            ),
        )

    async def get_url(self, key: str) -> str:
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            partial(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=3600,
            ),
        )
        return url
