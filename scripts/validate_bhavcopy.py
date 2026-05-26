from pathlib import Path
import shutil
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR/"raw"
QUARANTINE_DIR = BASE_DIR/"quarantine"

MIN_FILE_SIZE_BYTES = 50_000
MAX_FILE_SIZE_BYTES = 500_000

EXPECTED_HEADERS = [
    "SYMBOL",
    "OPEN_PRICE",
    "HIGH_PRICE",
    "CLOSE_PRICE",
    "LOW_PRICE",
    "SERIES"
]

def validate_file_size(file_path):
    file_size = file_path.stat().st_size
    
    if file_size < MIN_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size too small: {file_size} bytes"
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size too big: {file_size} bytes"
        )

def validate_header(file_path):
    with open(file_path, "r", encoding = "utf-8") as file:
        first_line = file.readline()
        first_line_lower = first_line.lower()
        
    if "<html" in first_line_lower or "<!doctype" in first_line_lower:
        raise ValueError("HTML content detected")

    missing_headers= []
    
    for header in EXPECTED_HEADERS:
        if header not in first_line:
            missing_headers.append(header)
    
    if missing_headers:
        raise ValueError(
            f"Missing expected headers: {missing_headers}"
        )
            
def extract_date_from_file_name(file_path):
    filename = file_path.stem
    date_portion = filename[2:11]
    
    return pd.to_datetime(
        date_portion,
        format = "%d%b%Y"
    ).date()
    
def validate_date_consistency(file_path):
    expected_date = extract_date_from_file_name(file_path)
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    
    actual_date = pd.to_datetime(
        df["DATE1"].iloc[0].strip(),
        format="%d-%b-%Y"
    ).date()
    
    if actual_date != expected_date:
        raise ValueError(
            f"Date mismatch. "
            f"Filename date: {expected_date}, "
            f"Internal date: {actual_date}"
        )
    
def quarantine_file(file_path, reason):
    QUARANTINE_DIR.mkdir(exist_ok=True)
    destination = QUARANTINE_DIR/file_path.name
    shutil.move(str(file_path), str(destination))
    print(f"QUARANTINED: {file_path.name}")
    print(f"Reason: {reason}")
    
def process_file(file_path):
    try:
        validate_file_size(file_path)
        validate_header(file_path)
        validate_date_consistency(file_path)
        
        print(f"Valid: {file_path.name}")
    except Exception as e:
        quarantine_file(file_path, str(e))
        
def main():
    files = RAW_DIR.glob("*.csv")
    for file_path in files:
        process_file(file_path)
        
if __name__ == "__main__":
    main()