import os
import logging
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Set up logging for configuration warnings
logger = logging.getLogger("whatsapp-sync")

class Settings(BaseSettings):
    VERIFY_TOKEN: str = "default_verify_token"
    SPREADSHEET_ID: Optional[str] = None
    SPREADSHEET_NAME: Optional[str] = "WhatsappLeads"
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "credentials/service_account.json"
    GOOGLE_CREDENTIALS: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_BUSINESS_ACCOUNT_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None

    # Load from environment variables first, then fallback to .env file if it exists
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
try:
    settings = Settings()
except Exception as e:
    logger.warning("Could not load settings using pydantic-settings, falling back to os.environ: %s", e)
    class FallbackSettings:
        VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "default_verify_token")
        SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
        SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "WhatsappLeads")
        GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
        GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
        WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
        WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    settings = FallbackSettings()


# Perform validation checks
if settings.VERIFY_TOKEN == "default_verify_token":
    logger.warning("WARNING: VERIFY_TOKEN is using the default value. Please set it in your environment or .env file.")

if not settings.SPREADSHEET_ID and not settings.SPREADSHEET_NAME:
    logger.warning("WARNING: Neither SPREADSHEET_ID nor SPREADSHEET_NAME is configured. Google Sheet sync will fail.")
