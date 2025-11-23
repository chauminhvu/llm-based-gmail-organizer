import json
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.append(os.getcwd())

from src.gmail_client import authenticate, fetch_emails
from src.llm_client import configure_llm, categorize_email

VERIFIED_EMAILS_FILE = "data/verified_emails.json"

def load_dataset():
    if os.path.exists(VERIFIED_EMAILS_FILE):
        with open(VERIFIED_EMAILS_FILE, "r") as f:
            return json.load(f)
    return []

def save_dataset(data):
    with open(VERIFIED_EMAILS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def main():
    print("--- Gmail Organizer Dataset Builder ---")
    
    # Setup
    try:
        configure_llm()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set GEMINI_API_KEY in a .env file.")
        return

    service = authenticate()
    
    # Fetch emails
    print("Fetching emails...")
    # Changed query to 'is:inbox' to get recent emails, not just unread ones
    emails = fetch_emails(service, query="is:inbox", max_results=10) 
    
    dataset = load_dataset()
    
    # Handle both old (flat) and new (nested) formats for duplicate checking
    existing_ids = set()
    for item in dataset:
        if "metadata" in item:
            existing_ids.add(item["metadata"]["email_id"])
        else:
            existing_ids.add(item.get("email_id") or item.get("id"))
    
    new_entries = 0
    
    for email in emails:
        if email["id"] in existing_ids:
            continue
            
        print(f"\n{'='*50}")
        print(f"From: {email['sender']}")
        print(f"To: {email['recipient']}")
        print(f"Subject: {email['subject']}")
        print(f"Body (first 500 chars): {email['body'][:500]}...")
        print(f"{'='*50}")
        
        # Get LLM Label
        predicted_category = categorize_email(email["subject"], email["snippet"], email["body"])
        print(f"LLM Prediction: {predicted_category}")
        
        # User Review
        while True:
            choice = input("Is this correct? (y/n/s to skip): ").lower()
            if choice == 'y':
                correct_category = predicted_category
                break
            elif choice == 'n':
                correct_category = input("Enter correct category: ").strip()
                break
            elif choice == 's':
                correct_category = None
                break
        
        if correct_category:
            # Construct fine-tuning data
            # We use Subject + Body as the input, as this is richer for fine-tuning than just snippet
            ft_input = f"Subject: {email['subject']}\nBody: {email['body']}"
            
            entry = {
                "training_data": {
                    "input": ft_input,
                    "output": correct_category
                },
                "metadata": {
                    "email_id": email["id"],
                    "subject": email["subject"],
                    "sender": email["sender"],
                    "recipient": email["recipient"],
                    "snippet": email["snippet"],
                    "model_prediction": predicted_category,
                    "thumbs_up": predicted_category == correct_category
                }
            }
            dataset.append(entry)
            new_entries += 1
            
    if new_entries > 0:
        save_dataset(dataset)
        print(f"\nSaved {new_entries} new verified entries to {VERIFIED_EMAILS_FILE}")
    else:
        print("\nNo new entries added.")

if __name__ == "__main__":
    main()
