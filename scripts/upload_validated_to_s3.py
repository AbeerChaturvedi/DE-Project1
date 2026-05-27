from pathlib import Path
import pandas as pd
import boto3
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent.parent
VALIDATED_DIR = BASE_DIR / "validated"

BUCKET_NAME = "project1-market-data-reconciliation-abeer-20260527"
AWS_PROFILE = "project1-s3"


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

    sample_file = sorted(VALIDATED_DIR.glob("*.csv"))[0]

    upload_file_to_s3(s3_client, sample_file)


if __name__ == "__main__":
    main()