from pathlib import Path
import tempfile
import shutil
import os

from openpyxl import load_workbook, Workbook


# ============================================================
# CONFIGURATION
# ============================================================

MASTER_FILE = Path(
    "Softwave 100K IPC DIDs - 2026 Sep 10 Updated.xlsx"
)

OUTPUT_DIR = Path("xlsx_chunks")

# Maximum allowed XLSX file size
MAX_SIZE_KB = 100
MAX_SIZE_BYTES = MAX_SIZE_KB * 1024


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_file_size(path: Path) -> int:
    """Return file size in bytes."""
    return path.stat().st_size


def get_file_size_kb(path: Path) -> float:
    """Return file size in KB."""
    return get_file_size(path) / 1024


def save_workbook(workbook, path: Path):
    """
    Save workbook to the specified path.
    """
    workbook.save(path)


def create_chunk_workbook(headers, rows, sheet_title):
    """
    Create a new workbook containing headers and rows.
    """

    workbook = Workbook()

    worksheet = workbook.active
    worksheet.title = sheet_title[:31]

    # Write headers
    worksheet.append(headers)

    # Write data rows
    for row in rows:
        worksheet.append(row)

    return workbook


def verify_file_size(path: Path) -> bool:
    """
    Verify that the generated XLSX file is
    within the configured size limit.
    """

    size = get_file_size(path)

    return size <= MAX_SIZE_BYTES


# ============================================================
# VALIDATE MASTER FILE
# ============================================================

if not MASTER_FILE.exists():
    raise FileNotFoundError(
        f"Master file was not found:\n{MASTER_FILE.resolve()}"
    )


if MASTER_FILE.suffix.lower() != ".xlsx":
    raise ValueError(
        "The master file must be an .xlsx Excel file."
    )


print("=" * 70)
print("XLSX 100 KB CHUNKING SCRIPT")
print("=" * 70)

print(f"Master file : {MASTER_FILE}")
print(f"Output dir  : {OUTPUT_DIR}")
print(f"Max size    : {MAX_SIZE_KB} KB")
print()


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD MASTER WORKBOOK
# ============================================================

print("Loading master workbook...")

master_workbook = load_workbook(
    MASTER_FILE,
    read_only=True,
    data_only=False
)

print(
    f"Sheets found: {len(master_workbook.sheetnames)}"
)

print(
    f"Sheet names: {', '.join(master_workbook.sheetnames)}"
)

print()


# ============================================================
# TEMPORARY DIRECTORY
# ============================================================

temporary_dir = Path(
    tempfile.mkdtemp(
        prefix="xlsx_chunking_"
    )
)


# ============================================================
# GLOBAL COUNTERS
# ============================================================

global_chunk_number = 1
total_rows_processed = 0
total_chunks_created = 0


# ============================================================
# PROCESS EACH SHEET
# ============================================================

try:

    for sheet_name in master_workbook.sheetnames:

        worksheet = master_workbook[sheet_name]

        print("-" * 70)
        print(f"Processing sheet: {sheet_name}")
        print("-" * 70)

        # ----------------------------------------------------
        # READ HEADER
        # ----------------------------------------------------

        rows_iterator = worksheet.iter_rows(
            values_only=True
        )

        try:
            headers = next(rows_iterator)
        except StopIteration:
            print("Sheet is empty. Skipping.")
            print()
            continue

        headers = list(headers)

        # ----------------------------------------------------
        # CURRENT CHUNK
        # ----------------------------------------------------

        current_rows = []

        sheet_row_number = 0

        for row in rows_iterator:

            row = list(row)

            sheet_row_number += 1
            total_rows_processed += 1

            # Add the row temporarily
            test_rows = current_rows + [row]

            # ------------------------------------------------
            # CREATE TEMPORARY XLSX
            # ------------------------------------------------

            temp_file = (
                temporary_dir /
                f"test_{global_chunk_number:08d}.xlsx"
            )

            test_workbook = create_chunk_workbook(
                headers=headers,
                rows=test_rows,
                sheet_title=sheet_name
            )

            save_workbook(
                test_workbook,
                temp_file
            )

            test_workbook.close()

            actual_size = get_file_size(
                temp_file
            )

            # ------------------------------------------------
            # ROW FITS
            # ------------------------------------------------

            if actual_size <= MAX_SIZE_BYTES:

                current_rows.append(row)

                temp_file.unlink(
                    missing_ok=True
                )

            # ------------------------------------------------
            # ROW DOES NOT FIT
            # ------------------------------------------------

            else:

                # If there are already rows in the chunk,
                # save the existing chunk first.
                if current_rows:

                    output_file = (
                        OUTPUT_DIR /
                        f"chunk_{global_chunk_number:06d}.xlsx"
                    )

                    final_workbook = (
                        create_chunk_workbook(
                            headers=headers,
                            rows=current_rows,
                            sheet_title=sheet_name
                        )
                    )

                    save_workbook(
                        final_workbook,
                        output_file
                    )

                    final_workbook.close()

                    # Verify actual size
                    final_size = get_file_size(
                        output_file
                    )

                    if final_size > MAX_SIZE_BYTES:
                        raise RuntimeError(
                            f"INTERNAL ERROR: "
                            f"{output_file.name} is "
                            f"{final_size / 1024:.2f} KB, "
                            f"which exceeds the "
                            f"{MAX_SIZE_KB} KB limit."
                        )

                    print(
                        f"Created: {output_file.name} | "
                        f"Rows: {len(current_rows)} | "
                        f"Size: {final_size / 1024:.2f} KB"
                    )

                    total_chunks_created += 1
                    global_chunk_number += 1

                    current_rows = []

                # --------------------------------------------
                # CHECK WHETHER SINGLE ROW FITS
                # --------------------------------------------

                single_row_temp = (
                    temporary_dir /
                    f"single_{global_chunk_number:08d}.xlsx"
                )

                single_row_workbook = (
                    create_chunk_workbook(
                        headers=headers,
                        rows=[row],
                        sheet_title=sheet_name
                    )
                )

                save_workbook(
                    single_row_workbook,
                    single_row_temp
                )

                single_row_workbook.close()

                single_row_size = get_file_size(
                    single_row_temp
                )

                single_row_temp.unlink(
                    missing_ok=True
                )

                if single_row_size > MAX_SIZE_BYTES:

                    raise RuntimeError(
                        "\n"
                        "A SINGLE ROW CANNOT FIT INTO "
                        f"A {MAX_SIZE_KB} KB XLSX FILE.\n\n"
                        f"Sheet       : {sheet_name}\n"
                        f"Row number  : {sheet_row_number + 1}\n"
                        f"Row size    : "
                        f"{single_row_size / 1024:.2f} KB\n"
                        f"Maximum     : "
                        f"{MAX_SIZE_KB} KB\n\n"
                        "This row must be handled separately "
                        "because Excel workbook overhead plus "
                        "the row's data exceeds the limit."
                    )

                # Start new chunk with this row
                current_rows.append(row)

        # ----------------------------------------------------
        # SAVE LAST CHUNK OF CURRENT SHEET
        # ----------------------------------------------------

        if current_rows:

            output_file = (
                OUTPUT_DIR /
                f"chunk_{global_chunk_number:06d}.xlsx"
            )

            final_workbook = (
                create_chunk_workbook(
                    headers=headers,
                    rows=current_rows,
                    sheet_title=sheet_name
                )
            )

            save_workbook(
                final_workbook,
                output_file
            )

            final_workbook.close()

            final_size = get_file_size(
                output_file
            )

            if final_size > MAX_SIZE_BYTES:
                raise RuntimeError(
                    f"FINAL CHUNK EXCEEDED LIMIT: "
                    f"{output_file.name} = "
                    f"{final_size / 1024:.2f} KB"
                )

            print(
                f"Created: {output_file.name} | "
                f"Rows: {len(current_rows)} | "
                f"Size: {final_size / 1024:.2f} KB"
            )

            total_chunks_created += 1
            global_chunk_number += 1

        print()


finally:

    # ========================================================
    # CLEANUP
    # ========================================================

    master_workbook.close()

    if temporary_dir.exists():
        shutil.rmtree(
            temporary_dir,
            ignore_errors=True
        )


# ============================================================
# FINAL VERIFICATION
# ============================================================

print("=" * 70)
print("FINAL VERIFICATION")
print("=" * 70)

output_files = sorted(
    OUTPUT_DIR.glob("chunk_*.xlsx")
)

oversized_files = []

total_output_size = 0

for file in output_files:

    size = get_file_size(file)

    total_output_size += size

    if size > MAX_SIZE_BYTES:

        oversized_files.append(
            (
                file.name,
                size
            )
        )


# ============================================================
# RESULTS
# ============================================================

print(
    f"Master rows processed : {total_rows_processed}"
)

print(
    f"Chunks created        : {len(output_files)}"
)

print(
    f"Output directory      : "
    f"{OUTPUT_DIR.resolve()}"
)

print(
    f"Total output size     : "
    f"{total_output_size / (1024 * 1024):.2f} MB"
)

print()


# ============================================================
# SAFETY CHECK
# ============================================================

if oversized_files:

    print("ERROR: Some files exceed 100 KB!")

    for filename, size in oversized_files:

        print(
            f"  {filename}: "
            f"{size / 1024:.2f} KB"
        )

    raise RuntimeError(
        "The 100 KB size requirement was violated."
    )


print("SUCCESS!")
print(
    f"Every generated XLSX file is "
    f"<= {MAX_SIZE_KB} KB."
)

print("=" * 70)
