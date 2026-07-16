"""Google Sheets response source via gspread + OAuth2 (report §6.2).

STATUS: implemented and ready, but UNTESTED against live credentials —
no real Google service account was available during development.

To enable (see README "Switching to real Google Sheets mode"):
  1. Create a Google Cloud service account with Sheets + Drive API access.
  2. Download its JSON key and share the sheet with the service account email.
  3. Set in .env:
       DATA_SOURCE=gsheet
       GOOGLE_CREDENTIALS_FILE=/path/to/service_account.json
       GSHEET_NAME=<spreadsheet title>
       GSHEET_WORKSHEET=<worksheet/tab name>
  4. The sheet's header row must contain the columns listed in
     ResponseSource.REQUIRED_COLUMNS (a column-mapping dict can be passed
     if the Form writes full question texts as headers).
"""
import pandas as pd

from .base import ResponseSource

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GSheetResponseSource(ResponseSource):
    def __init__(self, credentials_file: str, sheet_name: str,
                 worksheet: str = "Form Responses 1", column_map: dict = None):
        if not credentials_file:
            raise ValueError(
                "DATA_SOURCE=gsheet requires GOOGLE_CREDENTIALS_FILE to be set.")
        self.credentials_file = credentials_file
        self.sheet_name = sheet_name
        self.worksheet = worksheet
        # optional {sheet header -> canonical column} mapping, e.g. the full
        # Google Form question text -> "A1"
        self.column_map = column_map or {}

    def _client(self):
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            self.credentials_file, scopes=SCOPES)
        return gspread.authorize(creds)

    def load(self) -> pd.DataFrame:
        client = self._client()
        ws = client.open(self.sheet_name).worksheet(self.worksheet)
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        if self.column_map:
            df = df.rename(columns=self.column_map)
        return self.validate(df)
