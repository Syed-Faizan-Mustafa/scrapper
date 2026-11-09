print(">>> SCRIPT STARTED <<<")
import os
import csv

# =========================
# CONFIG
# =========================
INPUT_DIR = "input_data"

VALID_DIR = "valid_by_phone_numbers"
INVALID_DIR = "invalid_by_phone_numbers"

PHONE_INDEX = 1  # 2nd column

VALID_FILE = "valid_master.csv"
DUPLICATE_FILE = "duplicate_numbers.csv"
TOLLFREE_FILE = "tollfree_numbers.csv"
INVALID_FILE = "invalid_numbers.csv"

# =========================
# HELPERS
# =========================
def ensure_dirs():
    os.makedirs(VALID_DIR, exist_ok=True)
    os.makedirs(INVALID_DIR, exist_ok=True)

def clean_phone(phone):
    phone = "".join(ch for ch in phone if ch.isdigit())
    if len(phone) == 11 and phone.startswith("1"):
        phone = phone[1:]
    return phone

def is_tollfree(phone):
    return phone.startswith("800") or phone.startswith("1800")

def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="latin1") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

# =========================
# MAIN
# =========================
def main():
    ensure_dirs()

    seen_phones = set()

    valid_rows = []
    duplicate_rows = []
    tollfree_rows = []
    invalid_rows = []

    total = 0

    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith(".csv"):
            continue

        file_path = os.path.join(INPUT_DIR, filename)

        with open(file_path, newline="", encoding="latin1", errors="ignore") as f:
            reader = csv.reader(f)

            for row in reader:
                total += 1

                if len(row) <= PHONE_INDEX:
                    invalid_rows.append(row)
                    continue

                phone = clean_phone(row[PHONE_INDEX])
                row[PHONE_INDEX] = phone

                # Invalid length
                if len(phone) != 10:
                    invalid_rows.append(row)
                    continue

                # Toll free
                if is_tollfree(phone):
                    tollfree_rows.append(row)
                    continue

                # Duplicate
                if phone in seen_phones:
                    duplicate_rows.append(row)
                    continue

                # Valid
                seen_phones.add(phone)
                valid_rows.append(row)

    # =========================
    # WRITE OUTPUT FILES
    # =========================
    write_csv(os.path.join(VALID_DIR, VALID_FILE), valid_rows)
    write_csv(os.path.join(INVALID_DIR, DUPLICATE_FILE), duplicate_rows)
    write_csv(os.path.join(INVALID_DIR, TOLLFREE_FILE), tollfree_rows)
    write_csv(os.path.join(INVALID_DIR, INVALID_FILE), invalid_rows)

    # =========================
    # SUMMARY
    # =========================
    print("✅ PHONE CLEANUP COMPLETE")
    print("Total records:", total)
    print("Valid:", len(valid_rows))
    print("Duplicates:", len(duplicate_rows))
    print("Toll-free:", len(tollfree_rows))
    print("Invalid:", len(invalid_rows))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
