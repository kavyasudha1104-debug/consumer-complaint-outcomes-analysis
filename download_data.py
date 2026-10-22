"""Download or extract the CFPB Consumer Complaint Database.

Official source: https://www.consumerfinance.gov/data-research/consumer-complaints/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW_DIR  # noqa: E402

URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
EXPECTED_CSV = "complaints.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 24), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(zip_path: Path | None) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if zip_path is None:
        zip_path = RAW_DIR / "complaints_csv.zip"
        print(f"Downloading {URL} ...")
        urllib.request.urlretrieve(URL, zip_path)
        source = URL
    else:
        zip_path = zip_path.expanduser().resolve()
        if not zip_path.is_file():
            raise SystemExit(f"ZIP file not found: {zip_path}")
        source = f"local file: {zip_path}"

    try:
        with zipfile.ZipFile(zip_path) as archive:
            csv_files = [
                name
                for name in archive.namelist()
                if Path(name).name.lower() == EXPECTED_CSV
                and not name.endswith("/")
            ]

            if len(csv_files) != 1:
                raise SystemExit(
                    f"Expected one complaints.csv in the ZIP; "
                    f"found {len(csv_files)}."
                )

            output_csv = RAW_DIR / EXPECTED_CSV
            with archive.open(csv_files[0]) as src, output_csv.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 24)

    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Invalid ZIP file: {zip_path}") from exc

    with output_csv.open("r", encoding="utf-8-sig", newline="") as file:
        header = file.readline().strip()

    record = {
        "source": source,
        "official_url": URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "zip_sha256": sha256(zip_path),
        "csv_bytes": output_csv.stat().st_size,
        "csv_sha256": sha256(output_csv),
        "header": header,
    }

    record_path = RAW_DIR / "retrieval_record.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zip",
        type=Path,
        default=None,
        help="Use an existing CFPB ZIP instead of downloading it.",
    )
    args = parser.parse_args()
    main(args.zip)