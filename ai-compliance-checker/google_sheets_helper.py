import os
import gspread
from dotenv import load_dotenv

# ✅ Load .env
load_dotenv()

def connect_to_sheet():
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    tab_name = os.getenv("GOOGLE_SHEET_TAB")
    creds_file = os.getenv("GOOGLE_SERVICE_CREDS")

    print("DEBUG: Loaded GOOGLE_SHEET_ID =", sheet_id)

    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID missing in .env")

    if not tab_name:
        raise ValueError("GOOGLE_SHEET_TAB missing in .env")

    if not creds_file or not os.path.exists(creds_file):
        raise FileNotFoundError("service_account.json NOT FOUND. Check GOOGLE_SERVICE_CREDS path.")

    # ✅ Authenticate
    client = gspread.service_account(filename=creds_file)

    # ✅ Open sheet
    sheet = client.open_by_key(sheet_id).worksheet(tab_name)
    return sheet


def write_missing_clauses(sheet, file_name, missing_list):
    """Write results to Google Sheet"""

    # ✅ SAFETY: Ensure missing_list is always a list
    if not isinstance(missing_list, list):
        missing_list = [str(missing_list)]

    row = [file_name, ", ".join(missing_list) if missing_list else "No missing clauses"]
    sheet.append_row(row)