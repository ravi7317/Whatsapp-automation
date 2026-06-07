import logging

logger = logging.getLogger("whatsapp-sync")

def parse_whatsapp_payload(payload: dict) -> list[dict]:
    """
    Parses incoming payloads from either Meta WhatsApp Business API or direct mock requests.
    Returns a list of dicts with:
      - name: str
      - phone: str
      - message: str
      - message_id: str | None (Meta message ID used for retry deduplication)
    """
    parsed_messages = []

    # 1. Check if this is a direct mock payload
    # Expected keys: "name", "phone", "message"
    if all(k in payload for k in ("name", "phone", "message")):
        parsed_messages.append({
            "name": str(payload["name"]),
            "phone": str(payload["phone"]),
            "message": str(payload["message"]),
            "message_id": None  # No message ID for simple mock payloads
        })
        return parsed_messages

    # 2. Check if this is an official Meta WhatsApp Webhook payload
    # Look for "object" == "whatsapp_business_account" or standard Meta nested keys
    if payload.get("object") == "whatsapp_business_account" or "entry" in payload:
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                # Check if this is indeed a messages change
                if "messages" not in value:
                    continue
                
                # Build a mapping of contact wa_id -> profile name
                contacts_map = {}
                for contact in value.get("contacts", []):
                    wa_id = contact.get("wa_id")
                    profile = contact.get("profile", {})
                    name = profile.get("name")
                    if wa_id and name:
                        contacts_map[wa_id] = name

                # Process all messages in this change
                messages = value.get("messages", [])
                for msg in messages:
                    sender_phone = msg.get("from")
                    message_id = msg.get("id")
                    msg_type = msg.get("type", "text")
                    
                    # Resolve sender name from contacts profile, fallback to phone number
                    sender_name = contacts_map.get(sender_phone, sender_phone)
                    
                    # Handle message text and non-text formats
                    if msg_type == "text":
                        text_obj = msg.get("text", {})
                        message_content = text_obj.get("body", "")
                    else:
                        # Non-text formats (image, document, audio, video, sticker, etc.)
                        message_content = f"[{msg_type}]"
                    
                    if sender_phone and message_content:
                        parsed_messages.append({
                            "name": sender_name,
                            "phone": sender_phone,
                            "message": message_content,
                            "message_id": message_id
                        })
                    else:
                        logger.warning("Skipped parsing a message due to missing sender or content: %s", msg)
                        
        return parsed_messages

    # 3. Payload format not recognized
    return []
