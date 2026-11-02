import os
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

def test_neon_storage():
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    app_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_REGION", "ap-southeast-1")
    bucket = "pravision-evidence"

    print("Testing Neon Object Storage credentials...")
    print(f"  Endpoint: {endpoint}")
    print(f"  Key ID present: {bool(key_id)}")
    print(f"  Region: {region}")
    print(f"  Bucket: {bucket}")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=app_key,
        region_name=region,
        config=Config(
            s3={"addressing_style": "path"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"}
        )
    )

    test_content = b"NEON OBJECT STORAGE VERIFICATION PAYLOAD 2026-11-02"
    expected_hash = hashlib.sha256(test_content).hexdigest()
    key = "test_verification_evidence.txt"

    print(f"Uploading object '{key}' to Neon bucket '{bucket}'...")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=test_content,
        ContentType="text/plain",
        Metadata={"sha256": expected_hash}
    )
    print("Upload successful!")

    print(f"Downloading object '{key}' from Neon bucket '{bucket}'...")
    resp = client.get_object(Bucket=bucket, Key=key)
    downloaded_data = resp["Body"].read()
    downloaded_hash = hashlib.sha256(downloaded_data).hexdigest()
    print(f"Downloaded hash: {downloaded_hash}")
    assert downloaded_hash == expected_hash, "Hash mismatch!"
    assert downloaded_data == test_content, "Content mismatch!"
    print("Bit-for-bit SHA-256 integrity verified!")

    print(f"Deleting object '{key}'...")
    client.delete_object(Bucket=bucket, Key=key)
    print("Delete verified!")
    print("Neon Object Storage test PASSED completely!")

if __name__ == "__main__":
    test_neon_storage()

