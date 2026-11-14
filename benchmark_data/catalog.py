"""BLS Diary file naming and organization, independent of cloud clients."""
from dataclasses import dataclass
from pathlib import PurePosixPath
import re

FILE_TYPES = {
    "fmld": "Consumer-unit characteristics, weights and weekly summary expenditures",
    "memd": "Individual member characteristics and income",
    "expd": "Detailed weekly expenditure records",
    "dtbd": "Detailed annual income",
    "dtid": "Income imputation iterations",
}
PATTERN = re.compile(r"(fmld|memd|expd|dtbd|dtid)(\d{2})([1-4])\.csv", re.I)

@dataclass(frozen=True)
class DiaryFile:
    key: str
    year: int
    quarter: int
    kind: str

    @property
    def filename(self):
        return PurePosixPath(self.key).name

    @property
    def table_name(self):
        return f"{self.kind}_{self.year}_q{self.quarter}"

    @property
    def relative_directory(self):
        return f"{self.year}/q{self.quarter}/{self.kind}"


def identify(key, year):
    if year not in (2024, 2025):
        raise ValueError("Supported releases are 2024 and 2025.")
    match = PATTERN.fullmatch(PurePosixPath(key).name)
    if not match:
        raise ValueError(f"Unrecognized diary CSV filename: {key}")
    kind, suffix, quarter = match.groups()
    if int(suffix) != year % 100:
        raise ValueError(f"Filename year does not match requested release: {key}")
    return DiaryFile(key, year, int(quarter), kind.lower())


def validate_inventory(files, allow_partial=False):
    found = [(f.kind, f.quarter) for f in files]
    if len(found) != len(set(found)):
        raise ValueError("Duplicate file type/quarter in S3 prefix; choose a single release version.")
    if not files:
        raise ValueError("No diary CSV files found in the requested S3 prefix.")
    missing = sorted(set((kind,q) for kind in FILE_TYPES for q in range(1,5)) - set(found))
    if missing and not allow_partial:
        raise ValueError(f"Incomplete release, missing {missing}. Use --allow-partial only intentionally.")
    return missing
