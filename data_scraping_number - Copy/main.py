import csv
import os
import re

# ===================== CONFIG =====================
INPUT_FOLDER = "input_data"

INVALID_FOLDER = "invalid_by_phone_numbers"
VALID_FOLDER = "valid_by_phone_numbers"

INVALID_FILE = os.path.join(INVALID_FOLDER, "invalid_numbers.csv")
TOLLFREE_FILE = os.path.join(INVALID_FOLDER, "tollfree_numbers.csv")
DUPLICATE_FILE = os.path.join(INVALID_FOLDER, "duplicate_numbers.csv")
VALID_MASTER_FILE = os.path.join(VALID_FOLDER, "valid_master.csv")

# Column positions (NO HEADER CSV)
SERIAL_IDX = 0
PHONE_IDX = 1
NAME_IDX = 2
# ==================================================


def get_source_csv(folder):
    for file in os.listdir(folder):
        if file.lower().endswith(".csv"):
            return os.path.join(folder, file)
    raise FileNotFoundError("❌ input_data folder me koi CSV file nahi mili")


def clean_value(val):
    if val is None:
        return ""
    if isinstance(val, list):
        val = " ".join(map(str, val))
    return str(val).strip()


def data_score(row):
    score = 0
    for v in row:
        if clean_value(v) not in ("", "\\N", "NULL", "null"):
            score += 1
    return score


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="latin-1") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def main():
    # Create folders
    os.makedirs(INVALID_FOLDER, exist_ok=True)
    os.makedirs(VALID_FOLDER, exist_ok=True)

    source_csv = get_source_csv(INPUT_FOLDER)

    # Read CSV (NO HEADER, DIRTY DATA SAFE)
    with open(source_csv, newline="", encoding="latin-1") as f:
        reader = csv.reader(f)
        rows = list(reader)

    phone_map = {}
    invalid_rows = []
    duplicate_rows = []
    tollfree_rows = []

    for row in rows:
        # Ensure minimum columns
        if len(row) <= PHONE_IDX:
            invalid_rows.append(row)
            continue

        phone_raw = clean_value(row[PHONE_IDX])
        phone_digits = re.sub(r"\D", "", phone_raw)

        # Toll free numbers
        if phone_digits.startswith("800") or phone_digits.startswith("1800"):
            tollfree_rows.append(row)
            continue

        # Invalid numbers (non-digit / <10)
        if not phone_digits.isdigit() or len(phone_digits) < 10:
            invalid_rows.append(row)
            continue

        # 11-digit numbers
        if len(phone_digits) == 11:
            invalid_rows.append(row.copy())
            phone_digits = phone_digits[1:]
            row[PHONE_IDX] = phone_digits

        # Still not valid
        if len(phone_digits) != 10:
            invalid_rows.append(row)
            continue

        # Duplicate handling
        if phone_digits not in phone_map:
            phone_map[phone_digits] = row
        else:
            existing = phone_map[phone_digits]
            if data_score(row) > data_score(existing):
                duplicate_rows.append(existing)
                phone_map[phone_digits] = row
            else:
                duplicate_rows.append(row)

    valid_rows = list(phone_map.values())

    # Write output files
    write_csv(VALID_MASTER_FILE, valid_rows)
    write_csv(DUPLICATE_FILE, duplicate_rows)
    write_csv(INVALID_FILE, invalid_rows)
    write_csv(TOLLFREE_FILE, tollfree_rows)

    print("✅ Processing Completed Successfully")
    print(f"✔ Valid Records      : {len(valid_rows)}")
    print(f"✔ Duplicate Records  : {len(duplicate_rows)}")
    print(f"✔ Invalid Numbers    : {len(invalid_rows)}")
    print(f"✔ Toll Free Numbers  : {len(tollfree_rows)}")


if __name__ == "__main__":
    main()
