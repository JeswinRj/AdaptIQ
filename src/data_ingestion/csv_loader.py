"""CSV-backed response source (default mode; stands in for the Google Sheet)."""
from pathlib import Path

import pandas as pd

from .base import ResponseSource


class CsvResponseSource(ResponseSource):
    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} not found. Run "
                "`python scripts/generate_synthetic_data.py` first.")
        df = pd.read_csv(self.path)
        return self.validate(df)
