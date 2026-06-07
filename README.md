# WhatsApp Message to Google Sheets Sync API

This is a FastAPI-based service that automatically captures incoming WhatsApp messages (from Meta WhatsApp Business Cloud API or mock client payloads) and logs them to a Google Sheet. It includes built-in duplicate detection for both webhook retries and duplicate content.

---

## Features

- **Double-layered Deduplication**:
  1. **Webhook Retry Cache**: In-memory message ID cache to filter duplicate webhook event deliveries from Meta.
  2. **Spreadsheet Row Deduplication**: Checks incoming message content against existing rows to prevent recording duplicate messages from the same user.
- **Auto-Initializing Headers**: Automatically creates the header row `["Timestamp", "Name", "Phone", "Message"]` if the worksheet is empty.
- **Flexible Payload Support**: Seamlessly processes both the official nested Meta WhatsApp webhook payload and direct/mock flat payloads.
- **Graceful Media Support**: Auto-translates non-text message types (e.g. `image`, `audio`, `video`, `sticker`, etc.) into clear annotations like `[image]`, `[audio]`.
- **Health Check Endpoint**: Dedicated `/health` endpoint for monitoring on Render/Railway.
- **Secure Secret Handling**: Supports loading Google credentials securely from either a local `credentials/service_account.json` file (git-ignored) or directly from the `GOOGLE_CREDENTIALS` environment variable as a raw JSON string.

---

## Tech Stack

- **Framework**: Python, FastAPI, Uvicorn
- **Integration**: Google Sheets API (via `gspread` and `google-auth`)
- **Validation**: Pydantic v2
- **Deployment**: Docker, Render, Railway

---

## Project Structure

```text
whatsapp-sheet-sync/
│
├── app/
│   ├── main.py        # Central FastAPI application, routers, logging and caches
│   ├── sheets.py      # Google Sheets client auth, initialization, and writes
│   ├── config.py      # Environment configurations and validation fallbacks
│   └── utils.py       # Flexible parser for Meta and simple payloads
│
├── .env               # Local configuration file (git-ignored)
├── requirements.txt   # Pip dependencies
├── Dockerfile         # Docker recipe for hosting
├── README.md          # Setup & Deployment guide
└── .gitignore         # Git ignore file
```

---

## Local Setup

### 1. Configure Google Sheets API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Drive API** and **Google Sheets API**.
3. Create a **Service Account** under **IAM & Admin > Service Accounts**.
4. Generate a new key for the Service Account in **JSON format** and download it.
5. Place this JSON file in `credentials/service_account.json` (inside the `whatsapp-sheet-sync` project folder).
6. Create a Google Sheet and share it with the service account's `client_email` (found in the JSON) with **Editor** permissions.

### 2. Configure Environment Variables

Create a `.env` file in the root of the project:

```env
# Verification token used by Meta to verify your endpoint
VERIFY_TOKEN=your_secure_verify_token

# Google Spreadsheet Configuration
# Specify either the exact spreadsheet ID (recommended) or the spreadsheet Name:
SPREADSHEET_NAME=WhatsappLeads
# SPREADSHEET_ID=1aBCdEfGhIJKlMnOpQrStUvWxYz_1234567890
```

### 3. Install and Run Locally

1. Set up a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the development server:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Access the API documentation at `http://localhost:8000/docs`.

---

## Verification and Testing

### 1. Health Check
```bash
curl http://localhost:8000/health
```
**Expected Response:** `{"status": "healthy"}`

### 2. Webhook Verification (GET /webhook)
Simulate Meta's verification challenge:
```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test_challenge&hub.verify_token=your_secure_verify_token"
```
**Expected Response:** `test_challenge` (Status code: 200 OK)

### 3. Post Message - Direct / Mock Payload (POST /webhook)
```bash
curl -X POST "http://localhost:8000/webhook" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Rahul\",\"phone\":\"919876543210\",\"message\":\"Need admission details\"}"
```
**First Request Response:** `{"status": "success", "message": "Messages synchronized successfully", "details": [{"name": "Rahul", "phone": "919876543210", "status": "success", "reason": "Successfully saved to sheet"}]}` (Status code: 200 OK)

**Immediate Second Request (Duplicate Check):** `{"status": "success", "message": "All duplicate messages skipped", "details": [{"name": "Rahul", "phone": "919876543210", "status": "skipped", "reason": "Duplicate message content in sheet"}]}`

### 4. Post Message - Meta Webhook Text Payload
```bash
curl -X POST "http://localhost:8000/webhook" \
  -H "Content-Type: application/json" \
  -d "{\"object\":\"whatsapp_business_account\",\"entry\":[{\"id\":\"12345\",\"changes\":[{\"value\":{\"messaging_product\":\"whatsapp\",\"contacts\":[{\"profile\":{\"name\":\"Rahul\"},\"wa_id\":\"919876543210\"}],\"messages\":[{\"from\":\"919876543210\",\"id\":\"wamid.HBgLOTE5ODc2NTQzMjEwFQIAERgSQ0FEMzY3QTk3QzEyMEJCMzkzAA==\",\"timestamp\":\"1623067200\",\"text\":{\"body\":\"Need admission details\"},\"type\":\"text\"}]},\"field\":\"messages\"}]}]}"
```

---

## Run with Docker

1. Build the Docker image:
   ```bash
   docker build -t whatsapp-sheet-sync .
   ```
2. Run the Docker container:
   ```bash
   docker run -p 8000:8000 --env-file .env -v "%cd%/credentials:/app/credentials" whatsapp-sheet-sync
   ```

---

## Deployment Guide (Render/Railway)

### Option A: Render (Easiest)

1. Push your code to GitHub (ensure `.env` and `credentials/service_account.json` are **not** committed).
2. Log in to [Render](https://render.com/) and click **New > Web Service**.
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment**: `Python` or `Docker` (Choose Docker to use the containerized configuration automatically).
   - **Branch**: `main`
5. Click **Advanced** to add **Environment Variables**:
   - `PORT`: Set to the port you want (or leave empty; Render assigns one and Docker handles it).
   - `VERIFY_TOKEN`: Your secret verification token.
   - `SPREADSHEET_NAME` or `SPREADSHEET_ID`: Your Google Sheet identifier.
   - `GOOGLE_CREDENTIALS`: Copy the entire text content of your `service_account.json` file and paste it here.
6. Click **Deploy Web Service**.
7. Once deployed, configure your Meta App webhook URL:
   - **Callback URL**: `https://your-render-url.onrender.com/webhook`
   - **Verify Token**: Same as `VERIFY_TOKEN`.
