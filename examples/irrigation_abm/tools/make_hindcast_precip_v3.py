"""Build the 1998-2018 precipitation input for the irrigation v3 hindcast."""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.irrigation_abm.hindcast_env import HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR  # noqa: E402

SOURCE_CSV = (
    REPO_ROOT
    / "ref"
    / "CRSS_DB"
    / "CRSS_DB"
    / "HistoricalData"
    / "PrismWinterPrecip_NOAA_Winter_1905-2018.csv"
)
OUTPUT_CSV = Path(__file__).resolve().parents[1] / "data" / "hindcast_precip_v3.csv"
SOURCE_SHA256 = "3859730d4ce90e786566fb469c05e7fc74d9a63a5c0d0d2c18d15d98fd24d973"
FIRST_SOURCE_YEAR = HINDCAST_FIRST_YEAR - 2
LAST_SOURCE_YEAR = HINDCAST_LAST_YEAR
GROUP_SOURCE = {
    "WY": "WY_JACKSON",
    "UT1": "UT_FLAMINGGORGE",
    "UT2": "UT_FLAMINGGORGE",
    "UT3": "UT_FLAMINGGORGE",
    "NM": "NM_DURANGO",
    "CO1": "CO_ASPEN",
    "CO2": "CO_ASPEN",
    "CO3": "CO_ASPEN",
    "AZ": "NM_DURANGO",
}


def _checked_source_rows() -> list[list[str]]:
    data = SOURCE_CSV.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(
            f"{SOURCE_CSV} has sha256 {actual}, expected {SOURCE_SHA256}; "
            "refusing to build from unverified data."
        )
    return list(csv.reader(data.decode("utf-8-sig").splitlines()))


def build(output: Path = OUTPUT_CSV) -> Path:
    rows = _checked_source_rows()
    header = rows[0]
    source_index = {name.strip(): index for index, name in enumerate(header[:9])}
    expected = {"Hist", *set(GROUP_SOURCE.values())}
    missing = sorted(expected.difference(source_index))
    if missing:
        raise ValueError(f"{SOURCE_CSV} is missing source columns {missing}")

    by_year: dict[int, list[str]] = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        year = int(row[source_index["Hist"]])
        if FIRST_SOURCE_YEAR <= year <= LAST_SOURCE_YEAR:
            by_year[year] = row
    expected_years = set(range(FIRST_SOURCE_YEAR, LAST_SOURCE_YEAR + 1))
    if set(by_year) != expected_years:
        raise ValueError(
            f"{SOURCE_CSV} years differ from {FIRST_SOURCE_YEAR}-{LAST_SOURCE_YEAR}: "
            f"missing={sorted(expected_years.difference(by_year))}, "
            f"extra={sorted(set(by_year).difference(expected_years))}"
        )

    groups = list(GROUP_SOURCE)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["", *groups])
        for year in range(FIRST_SOURCE_YEAR, LAST_SOURCE_YEAR + 1):
            source_row = by_year[year]
            values = [
                source_row[source_index[GROUP_SOURCE[group]]].strip()
                for group in groups
            ]
            if any(not value for value in values):
                raise ValueError(f"{SOURCE_CSV} has a blank mapped value in {year}")
            writer.writerow([year, *values])
    return output


if __name__ == "__main__":
    path = build()
    print(f"wrote {path} ({hashlib.sha256(path.read_bytes()).hexdigest()})")
