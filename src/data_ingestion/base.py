"""Common interface for response data sources (report §6.1-6.2)."""
from abc import ABC, abstractmethod

import pandas as pd


class ResponseSource(ABC):
    """A source of raw questionnaire responses.

    Every loader returns a DataFrame with one row per student and columns:
    student_id, name, subject, plus the question columns A1..A3, B1..B4,
    C1..C4, D1..D3, E1, E2 (see docs/questionnaire_and_scoring.md).
    """

    REQUIRED_COLUMNS = [
        "student_id", "name", "subject",
        "A1", "A2", "A3",
        "B1", "B2", "B3", "B4",
        "C1", "C2", "C3", "C4",
        "D1", "D2", "D3",
        "E1", "E2",
    ]

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Fetch all responses."""

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Data source is missing required columns: {missing}")
        return df
