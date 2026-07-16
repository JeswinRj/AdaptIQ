"""Data ingestion factory: pick the response source from config."""
from .base import ResponseSource
from .csv_loader import CsvResponseSource
from .gsheet_loader import GSheetResponseSource


def get_source(cfg) -> ResponseSource:
    if cfg.DATA_SOURCE == "gsheet":
        return GSheetResponseSource(
            credentials_file=cfg.GOOGLE_CREDENTIALS_FILE,
            sheet_name=cfg.GSHEET_NAME,
            worksheet=cfg.GSHEET_WORKSHEET,
        )
    return CsvResponseSource(cfg.CSV_PATH)
