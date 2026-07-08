from pathlib import Path
import argparse
import pandas as pd
import boto3
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent.parent # scripts/ -> project root
VALIDATED_DIR = BASE_DIR / "validated"

BUCKET_NAME = "project1-market-data-reconciliation-abeer-20260527"
AWS_PROFILE = "project1-s3" # limited IAM profile, not default/admin credentials

DEFAULT_MAX_FILES_TO_UPLOAD = 50

def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("Limit must be a positive integer")
    return value

def parse_args():
    parser = argparse.ArgumentParser(
        description = "Upload validated NSE Bhavcopy files to date-partitioned S3 paths."
    )
    parser.add_argument(
        "--limit",
        type = positive_int,
        default = DEFAULT_MAX_FILES_TO_UPLOAD,
        help = f"Maximum number of validated files to consider for upload. Default: {DEFAULT_MAX_FILES_TO_UPLOAD}",
    )
    
    return parser.parse_args()
    
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
        return "Skipped"

    s3_client.upload_file(
        str(file_path),
        BUCKET_NAME,
        s3_key
    )

    print(f"Uploaded: {file_path.name}")
    print(f"S3 path: s3://{BUCKET_NAME}/{s3_key}")
    
    return "Uploaded"

def main():
    args = parse_args()
    upload_limit = args.limit
    
    session = boto3.Session(profile_name=AWS_PROFILE)
    s3_client = session.client("s3")

    validated_files = sorted(VALIDATED_DIR.glob("*.csv"))
    files_to_upload = validated_files[:upload_limit]
    
    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    
    print(f"Found {len(validated_files)} validated files.")
    print(f"Upload limit: {upload_limit}")
    print(f"Selected {len(files_to_upload)} files for upload.")
    
    for file_path in files_to_upload:
        try:
            result = upload_file_to_s3(s3_client, file_path)
            
            if result == "Uploaded":
                uploaded_count += 1
            elif result == "Skipped":
                skipped_count += 1
        
        except Exception as error:
            failed_count += 1
            print(f"FAILED: {file_path.name}")
            print(f"Reason: {error}")
        
    print("Upload summary")
    print(f"Uploaded: {uploaded_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")

if __name__ == "__main__":
    main()