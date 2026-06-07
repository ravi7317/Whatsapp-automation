import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, Request, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.utils import parse_whatsapp_payload
from app.sheets import append_message_to_sheet

# Set up logging format and levels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("whatsapp-sync")

# Initialize FastAPI App
app = FastAPI(
    title="WhatsApp to Google Sheets Sync API",
    description="Automatically logs incoming WhatsApp messages to Google Sheets.",
    version="1.0.0"
)

# Webhook Retry Deduplication Cache (in-memory)
class WebhookRetryCache:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = set()
        self.history = []

    def is_duplicate(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self.cache:
            return True
        
        # Add to cache
        self.cache.add(message_id)
        self.history.append(message_id)
        
        # Keep cache size bounded
        if len(self.history) > self.max_size:
            oldest = self.history.pop(0)
            self.cache.discard(oldest)
            
        return False

retry_cache = WebhookRetryCache()

@app.get("/health")
async def health():
    """
    Health Check endpoint for deployment platforms like Render/Railway.
    """
    return {"status": "healthy"}

@app.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """
    Meta Webhook Verification endpoint.
    GET /webhook is called by Meta to verify endpoint ownership.
    """
    logger.info("Incoming webhook verification request: mode=%s, token=%s", mode, token)
    
    if mode == "subscribe" and token == settings.VERIFY_TOKEN:
        logger.info("Webhook verification SUCCESSFUL. Echoing challenge.")
        return PlainTextResponse(content=challenge, status_code=status.HTTP_200_OK)
    
    logger.warning("Webhook verification FAILED. Mode: %s, token match: %s", mode, token == settings.VERIFY_TOKEN)
    return PlainTextResponse(content="Forbidden", status_code=status.HTTP_403_FORBIDDEN)

@app.post("/webhook")
async def receive_webhook(payload: dict):
    """
    Webhook Message Receiver.
    Accepts Meta WhatsApp Business Cloud API message payload or direct mock JSON payload.
    """
    # 1. Retrieve and log the raw payload for full observability
    try:
        logger.info("Incoming webhook payload: %s", json.dumps(payload))
    except Exception as e:
        logger.error("Failed to log payload: %s", e)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Invalid payload body"}
        )


    # 2. Parse the payload
    parsed_messages = parse_whatsapp_payload(payload)
    if not parsed_messages:
        logger.warning("Webhook payload structure could not be parsed or contained no messages.")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Unsupported or invalid payload format"}
        )

    results = []
    has_errors = False
    
    # 3. Process each parsed message
    for msg in parsed_messages:
        name = msg["name"]
        phone = msg["phone"]
        message_body = msg["message"]
        message_id = msg["message_id"]

        logger.info("Processing message from '%s' (%s): '%s' (ID: %s)", name, phone, message_body, message_id)

        # Check in-memory webhook retry cache first
        if message_id and retry_cache.is_duplicate(message_id):
            logger.info("Skipped message (ID: %s) because it is a duplicate webhook retry.", message_id)
            results.append({
                "name": name,
                "phone": phone,
                "status": "skipped",
                "reason": "Duplicate webhook retry"
            })
            continue

        # Write to Google Sheets
        try:
            write_status = append_message_to_sheet(name=name, phone=phone, message=message_body)
            if write_status == "skipped":
                results.append({
                    "name": name,
                    "phone": phone,
                    "status": "skipped",
                    "reason": "Duplicate message content in sheet"
                })
            else:
                results.append({
                    "name": name,
                    "phone": phone,
                    "status": "success",
                    "reason": "Successfully saved to sheet"
                })
        except Exception as e:
            logger.error("Failed to append message to Google Sheets: %s", e)
            results.append({
                "name": name,
                "phone": phone,
                "status": "error",
                "reason": str(e)
            })
            has_errors = True

    # 4. Determine response codes and content
    if has_errors:
        # If any writing error occurred, return 500 so client/Meta knows it failed
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to sync some messages", "details": results}
        )
    
    # If all skipped or saved, return 200 OK
    all_skipped = all(r["status"] == "skipped" for r in results)
    response_msg = "All duplicate messages skipped" if all_skipped else "Messages synchronized successfully"
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "success", "message": response_msg, "details": results}
    )
