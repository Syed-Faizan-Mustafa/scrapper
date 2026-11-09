import os
import csv
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# =========================
# CONFIG
# =========================
INPUT_DIR = "input_data"
VALID_DIR = "valid_by_phone_numbers"
INVALID_DIR = "invalid_by_phone_numbers"
CHUNK_SIZE = 10000

PHONE_INDEX = 1   # 2nd column
DOB_INDEX = 9     # 10th column

REPORT_FILE = "final_report.pdf"

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

def is_valid_phone(phone):
    if len(phone) != 10:
        return False
    if phone.startswith("800"):
        return False
    return True

def normalize_dob(dob):
    dob = dob.strip()
    if not dob:
        return "", False

    # Already valid
    try:
        return datetime.strptime(dob, "%Y-%m-%d").strftime("%Y-%m-%d"), True
    except:
        pass

    # Convertible numeric formats only
    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(dob, fmt).strftime("%Y-%m-%d"), True
        except:
            pass

    # Text / ambiguous → invalid
    return "", False

def write_rows(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="latin1") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

# =========================
# MAIN LOGIC
# =========================
def main():
    ensure_dirs()

    seen_phones = set()

    valid_chunk = []
    invalid_phone_rows = []
    duplicate_rows = []
    invalid_dob_rows = []

    valid_count = 0
    invalid_phone_count = 0
    duplicate_count = 0
    invalid_dob_count = 0
    total_count = 0

    chunk_index = 1

    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith(".csv"):
            continue

        file_path = os.path.join(INPUT_DIR, filename)

        with open(file_path, newline="", encoding="latin1", errors="ignore") as f:
            reader = csv.reader(f)

            for row in reader:
                total_count += 1

                # Ensure enough columns exist
                if len(row) <= max(PHONE_INDEX, DOB_INDEX):
                    invalid_phone_rows.append(row)
                    invalid_phone_count += 1
                    continue

                # ================= PHONE =================
                phone = clean_phone(row[PHONE_INDEX])
                row[PHONE_INDEX] = phone

                if not is_valid_phone(phone):
                    invalid_phone_rows.append(row)
                    invalid_phone_count += 1
                    continue

                if phone in seen_phones:
                    duplicate_rows.append(row)
                    duplicate_count += 1
                    continue

                seen_phones.add(phone)

                # ================= DOB =================
                dob, dob_valid = normalize_dob(row[DOB_INDEX])
                row[DOB_INDEX] = dob

                if not dob_valid:
                    invalid_dob_rows.append(row)
                    invalid_dob_count += 1
                    continue

                # ================= VALID =================
                valid_chunk.append(row)
                valid_count += 1

                if len(valid_chunk) == CHUNK_SIZE:
                    write_rows(
                        os.path.join(
                            VALID_DIR,
                            f"valid_clients_chunk_{chunk_index}.csv"
                        ),
                        valid_chunk
                    )
                    valid_chunk.clear()
                    chunk_index += 1

    # Remaining valid rows
    if valid_chunk:
        write_rows(
            os.path.join(
                VALID_DIR,
                f"valid_clients_chunk_{chunk_index}.csv"
            ),
            valid_chunk
        )

    # =========================
    # WRITE INVALID FILES
    # =========================
    write_rows(
        os.path.join(INVALID_DIR, "invalid_phone_numbers.csv"),
        invalid_phone_rows
    )

    write_rows(
        os.path.join(INVALID_DIR, "duplicate_phone_numbers.csv"),
        duplicate_rows
    )

    write_rows(
        os.path.join(INVALID_DIR, "invalid_or_missing_dob.csv"),
        invalid_dob_rows
    )

    # =========================
    # PDF REPORT
    # =========================
    c = canvas.Canvas(REPORT_FILE, pagesize=A4)
    y = 800

    c.setFont("Helvetica", 12)
    c.drawString(50, y, "CSV Data Validation Report")
    y -= 40

    c.drawString(50, y, f"Total clients processed: {total_count}")
    y -= 20
    c.drawString(50, y, f"Valid clients: {valid_count}")
    y -= 20

    total_invalid = invalid_phone_count + duplicate_count + invalid_dob_count
    c.drawString(50, y, f"Invalid clients: {total_invalid}")
    y -= 30

    c.drawString(50, y, "Invalid Breakdown:")
    y -= 20
    c.drawString(70, y, f"Invalid phone numbers: {invalid_phone_count}")
    y -= 20
    c.drawString(70, y, f"Duplicate phone numbers: {duplicate_count}")
    y -= 20
    c.drawString(70, y, f"Invalid or missing DOB: {invalid_dob_count}")

    c.save()

    print("✅ DONE")
    print("Total:", total_count)
    print("Valid:", valid_count)
    print("Invalid phone:", invalid_phone_count)
    print("Duplicates:", duplicate_count)
    print("Invalid DOB:", invalid_dob_count)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
