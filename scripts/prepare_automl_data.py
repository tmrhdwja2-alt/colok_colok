"""Validate and copy the organizer dataset for Vertex AI AutoML import."""

import argparse
import csv
from pathlib import Path


EXPECTED_ANTIBIOTICS = {"meropenem", "ciprofloxacin", "gentamicin"}
EXPECTED_LABELS = {"likely to fail", "likely to work", "uncertain"}


def prepare(input_path: Path, output_path: Path) -> None:
    with input_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        if columns[:2] != ["antibiotic", "final_call"]:
            raise ValueError("Expected antibiotic and final_call as the first two columns.")
        if len(columns) != 401 or columns[-1] != "data_split":
            raise ValueError(f"Expected 401 columns, found {len(columns)}.")
        rows = list(reader)

    antibiotics = {row["antibiotic"].strip().lower() for row in rows}
    labels = {row["final_call"].strip().lower() for row in rows}
    if antibiotics != EXPECTED_ANTIBIOTICS:
        raise ValueError(f"Unexpected antibiotic values: {sorted(antibiotics)}")
    if labels != EXPECTED_LABELS:
        raise ValueError(f"Unexpected label values: {sorted(labels)}")
    split_values = {row["data_split"].strip().upper() for row in rows}
    if split_values != {"TRAIN", "VALIDATE", "TEST"}:
        raise ValueError(f"Unexpected data_split values: {sorted(split_values)}")
    feature_columns = columns[2:-1]
    for row_number, row in enumerate(rows, 2):
        invalid = [column for column in feature_columns if row[column] not in {"0", "1", "0.0", "1.0"}]
        if invalid:
            raise ValueError(f"Non-binary feature at row {row_number}: {invalid[0]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_columns = columns[:-1]
    with output_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows({column: row[column] for column in output_columns} for row in rows)
    print(f"Validated {len(rows):,} rows; wrote {len(output_columns):,} model columns: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.input, args.output)


if __name__ == "__main__":
    main()
