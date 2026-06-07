import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from app.config import settings

logger = logging.getLogger("whatsapp-sync")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client() -> gspread.Client:
    """
    Authenticates with Google Sheets API using credentials from environment variable or local file.
    """
    # 1. Check if raw JSON credential is provided in environment variable
    if settings.GOOGLE_CREDENTIALS:
        try:
            logger.info("Authenticating Google client using GOOGLE_CREDENTIALS environment variable...")
            creds_dict = json.loads(settings.GOOGLE_CREDENTIALS)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            logger.error("Failed to authenticate using GOOGLE_CREDENTIALS environment variable: %s", e)
            raise e

    # 2. Fall back to reading the service account file
    try:
        logger.info("Authenticating Google client using service account file at %s...", settings.GOOGLE_SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_file(settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(
            "Failed to authenticate using Google service account file. "
            "Please make sure credentials/service_account.json exists or GOOGLE_CREDENTIALS is set. Error: %s", 
            e
        )
        raise e

def append_message_to_sheet(name: str, phone: str, message: str) -> str:
    """
    Appends the message details to the Google Sheet.
    Returns:
      - "success" if the message was successfully appended.
      - "skipped" if it was a duplicate and not written.
    Raises exception on connection or permission issues.
    """
    gc = get_gspread_client()

    # Open sheet by key or name
    if settings.SPREADSHEET_ID:
        logger.info("Opening spreadsheet by ID: %s", settings.SPREADSHEET_ID)
        sheet = gc.open_by_key(settings.SPREADSHEET_ID)
    elif settings.SPREADSHEET_NAME:
        logger.info("Opening spreadsheet by Name: %s", settings.SPREADSHEET_NAME)
        sheet = gc.open(settings.SPREADSHEET_NAME)
    else:
        raise ValueError("Neither SPREADSHEET_ID nor SPREADSHEET_NAME is configured in settings.")

    # Select the first worksheet
    worksheet = sheet.get_worksheet(0)
    
    # Read existing values for headers check and content deduplication
    existing_values = worksheet.get_all_values()
    
    # 1. Auto-Header Initialization
    if not existing_values or len(existing_values) == 0:
        headers = ["Timestamp", "Name", "Phone", "Message"]
        logger.info("Worksheet is empty. Writing headers: %s", headers)
        worksheet.append_row(headers)
        existing_values = [headers]

    # 2. Content Deduplication
    # Columns map: 0: Timestamp, 1: Name, 2: Phone, 3: Message
    # Standardize string checking to prevent whitespace duplicates
    clean_phone = str(phone).strip()
    clean_msg = str(message).strip()
    
    for row in existing_values[1:]:
        if len(row) >= 4:
            row_phone = str(row[2]).strip()
            row_msg = str(row[3]).strip()
            if row_phone == clean_phone and row_msg == clean_msg:
                logger.info("Duplicate record detected in sheet: Phone='%s', Message='%s'. Skipping write.", clean_phone, clean_msg)
                return "skipped"

    # 3. Append Row
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_to_append = [timestamp_str, name, phone, message]
    
    logger.info("Appending new row to sheet: %s", row_to_append)
    worksheet.append_row(row_to_append)
    logger.info("Successfully wrote lead to Google Sheets.")
    return "success"
