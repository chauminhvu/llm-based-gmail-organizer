import os.path
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.message import EmailMessage

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def create_label(service, label_name):
    """Creates a new label with the given name."""
    try:
        label = {"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        created_label = service.users().labels().create(userId="me", body=label).execute()
        print(f"Created label: {label_name} (ID: {created_label['id']})")
        return created_label["id"]
    except Exception as e:
        if "Label name exists" in str(e):
            return get_label_id(service, label_name)
        print(f"Error creating label {label_name}: {e}")
        return None

def get_label_id(service, label_name):
    """Retrieves the ID of a label by its name."""
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]
        return None
    except Exception as e:
        print(f"Error getting label ID for {label_name}: {e}")
        return None

def apply_label(service, message_id, label_id):
    """Applies a label to a message."""
    try:
        body = {"addLabelIds": [label_id]}
        service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        print(f"Applied label {label_id} to message {message_id}")
    except Exception as e:
        print(f"Error applying label to message {message_id}: {e}")

def authenticate():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def get_body_from_payload(payload):
    """Recursively extracts body from email payload."""
    if "parts" in payload:
        # Priority 1: text/plain
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode()
        
        # Priority 2: text/html (fallback)
        for part in payload["parts"]:
            if part["mimeType"] == "text/html":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode()
        
        # Priority 3: Recurse into multipart/*
        for part in payload["parts"]:
            if part["mimeType"].startswith("multipart/"):
                body = get_body_from_payload(part)
                if body:
                    return body
                    
    # Fallback for non-multipart or if parts failed
    data = payload["body"].get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode()
        
    return ""

def fetch_emails(service, query="is:unread", max_results=10, exclude_ids=None):
    """Fetches emails matching the query, excluding specified IDs."""
    if exclude_ids is None:
        exclude_ids = set()
        
    messages = []
    page_token = None
    
    print(f"Searching for {max_results} new emails (skipping {len(exclude_ids)} verified)...")
    
    # Fetch until we have enough non-excluded messages or run out
    while len(messages) < max_results:
        # Fetch a batch of IDs (lightweight)
        # Request more than needed to account for exclusions
        batch_size = max(50, max_results * 2)
        results = service.users().messages().list(
            userId="me", 
            q=query, 
            maxResults=batch_size,
            pageToken=page_token
        ).execute()
        
        batch = results.get("messages", [])
        if not batch:
            break
            
        for msg in batch:
            if msg["id"] not in exclude_ids:
                messages.append(msg)
                if len(messages) >= max_results:
                    break
        
        page_token = results.get("nextPageToken")
        if not page_token:
            break
            
    email_data = []
    
    if not messages:
        print("No new messages found.")
        return []

    print(f"Found {len(messages)} new messages to process.")
    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()
        
        # Parse headers
        headers = msg["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
        recipient = next((h["value"] for h in headers if h["name"] == "To"), "Unknown Recipient")
        
        # Get snippet
        snippet = msg.get("snippet", "")

        # Get body using recursive helper
        body = get_body_from_payload(msg["payload"])

        email_data.append({
            "id": message["id"],
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "snippet": snippet,
            "body": body
        })
        
    return email_data

if __name__ == "__main__":
    service = authenticate()
    emails = fetch_emails(service, max_results=5)
    for email in emails:
        print(f"Subject: {email['subject']}")
        print(f"Snippet: {email['snippet']}\n")
