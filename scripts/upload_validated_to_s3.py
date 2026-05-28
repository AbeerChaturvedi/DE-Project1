from pathlib import Path
import pandas as pd
import boto3
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent.parent #resolve gives full script path → scripts/ → project root
VALIDATED_DIR = BASE_DIR / "validated"

BUCKET_NAME = "project1-market-data-reconciliation-abeer-20260527"
AWS_PROFILE = "project1-s3" #tells to use limited IAM profile instead of default/admin credentials
MAX_FILES_TO_UPLOAD = 5

def extract_date_from_file_name(file_path):
    filename = file_path.stem
    date_portion = filename[2:11]

    return pd.to_datetime(
        date_portion,
        format="%d%b%Y"
    ).date()


def build_s3_key(file_path):
    file_date = extract_date_from_file_name(file_path)

    return (
        f"validated/nse_bhavcopy/"
        f"year={file_date.year}/"
        f"month={file_date.month:02d}/"
        f"day={file_date.day:02d}/"
        f"{file_path.name}"
    )


def object_exists(s3_client, bucket_name, s3_key):
    try:
        s3_client.head_object(
            Bucket=bucket_name,
            Key=s3_key
        )
        return True

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "404":
            return False

        raise


def upload_file_to_s3(s3_client, file_path):
    s3_key = build_s3_key(file_path)

    if object_exists(s3_client, BUCKET_NAME, s3_key):
        print(f"Already exists, skipping: s3://{BUCKET_NAME}/{s3_key}")
        return

    s3_client.upload_file(
        str(file_path),
        BUCKET_NAME,
        s3_key
    )

    print(f"Uploaded: {file_path.name}")
    print(f"S3 path: s3://{BUCKET_NAME}/{s3_key}")


def main():
    session = boto3.Session(profile_name=AWS_PROFILE)
    s3_client = session.client("s3")

    validated_files = sorted(VALIDATED_DIR.glob("*.csv"))
    
    files_to_upload = validated_files[:MAX_FILES_TO_UPLOAD]
    
    print(f"Found {len(validated_files)} validated files. ")
    print(f"Uploading first {len(files_to_upload)} files.")
    
    for file_path in files_to_upload:
        upload_file_to_s3(s3_client, file_path)


if __name__ == "__main__":
    main()