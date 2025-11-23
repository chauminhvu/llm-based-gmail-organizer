import os
import sys
import time

# Add the current directory to sys.path to allow imports from src
sys.path.append(os.getcwd())

from src.gmail_client import authenticate, fetch_emails, create_label, apply_label, get_label_id
from src.llm_client import configure_llm, categorize_email

def launch_review_and_apply(service, pending_data, pending_file):
    """Launch Streamlit for review and apply labels after confirmation."""
    # Prompt user to review
    print("=" * 80)
    print("REVIEW PHASE")
    print("=" * 80)
    print("\nI will now launch the Streamlit app for you to review and correct the categories.")
    print("In the Streamlit app:")
    print("  1. Make sure 'Mailbox Organization (Pending)' is selected in the sidebar")
    print("  2. Review each email and correct categories as needed")
    print("  3. Close the browser tab when done")
    print("  4. Press Ctrl+C in the Streamlit terminal to stop the server")
    
    launch = input("\nLaunch Streamlit now? (y/n, default y): ").lower()
    if launch != 'n':
        import subprocess
        print("\nLaunching Streamlit...")
        print("=" * 80)
        print("\nREMINDER: When you're done reviewing:")
        print("   1. Close the browser tab")
        print("   2. Press Ctrl+C here to stop the server\n")
        print("=" * 80)
        try:
            # Launch Streamlit in foreground so user can interact
            subprocess.run(["streamlit", "run", "src/data_review_app.py"], check=True)
        except subprocess.CalledProcessError:
            print("\nStreamlit was closed.")
        except KeyboardInterrupt:
            print("\nStreamlit was stopped.")
        except FileNotFoundError:
            print("\nError: Streamlit not found. Please install it with: pip install streamlit")
            return
        
        print("=" * 80)
    
    # Confirm before applying
    print("\n" + "=" * 80)
    print("SAVE TO VERIFIED EMAILS")
    print("=" * 80)
    print("\nBefore applying labels, let's save your corrections to the verified emails database.")
    print("This builds your ground truth dataset for future fine-tuning.")
    
    save_confirmed = input("\nSave corrected data to verified_emails.json? (y/n, default y): ").lower()
    
    if save_confirmed == 'n':
        print(f"Operation cancelled. Your corrections remain in {pending_file}")
        return
    
    # Save to verified emails
    import json
    verified_file = "data/verified_emails.json"
    
    # Reload corrected data from pending file
    if not os.path.exists(pending_file):
        print(f"Error: {pending_file} not found. Aborting.")
        return
        
    with open(pending_file, "r") as f:
        corrected_data = json.load(f)
    
    # Load existing verified emails
    if os.path.exists(verified_file):
        with open(verified_file, "r") as f:
            verified_data = json.load(f)
    else:
        verified_data = []
    
    # Get existing email IDs to check for duplicates
    existing_ids = set()
    for entry in verified_data:
        if "metadata" in entry and "email_id" in entry["metadata"]:
            existing_ids.add(entry["metadata"]["email_id"])
    
    # Add non-duplicate entries
    added_count = 0
    for entry in corrected_data:
        email_id = entry["metadata"]["email_id"]
        if email_id not in existing_ids:
            verified_data.append(entry)
            existing_ids.add(email_id)
            added_count += 1
    
    # Save updated verified emails
    with open(verified_file, "w") as f:
        json.dump(verified_data, f, indent=4)
    
    print(f"\nSaved to verified emails: {added_count} new, {len(corrected_data) - added_count} duplicates skipped")
    print(f"Total verified emails: {len(verified_data)}")
    
    # Now apply to Gmail
    print("\n" + "=" * 60)
    print("APPLY PHASE")
    print("=" * 60)
    confirm = input("\nApply the labels to Gmail now? (y/n): ").lower()
    if confirm != 'y':
        print(f"Labels not applied. Your verified data is saved in {verified_file}")
        return
    
    # Reload the corrected data
    if not os.path.exists(pending_file):
        print(f"Error: {pending_file} not found. Aborting.")
        return
        
    import json
    with open(pending_file, "r") as f:
        corrected_data = json.load(f)
    
    print("\nApplying labels based on your corrections...")
    
    # Cache label IDs to avoid repeated API calls
    label_cache = {}

    for entry in corrected_data:
        email_id = entry["metadata"]["email_id"]
        category = entry["training_data"]["output"]
        subject = entry["metadata"]["subject"]
        
        if category == "Uncategorized":
            continue

        # Get or Create Label ID
        if category not in label_cache:
            label_id = get_label_id(service, category)
            if not label_id:
                print(f"  -> Creating new label: {category}")
                label_id = create_label(service, category)
            label_cache[category] = label_id
        
        label_id = label_cache.get(category)
        
        # Apply Label
        if label_id:
            apply_label(service, email_id, label_id)
            print(f"  -> Applied '{category}' to: {subject[:40]}...")
        else:
            print(f"  -> Error: Could not create label for {category}")
            
    print("\nOrganization complete!")
    print(f"\nYou can delete {pending_file} if you're satisfied with the results.")

def main():
    print("--- Gmail Organizer ---")
    
    # Setup
    try:
        configure_llm()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set GEMINI_API_KEY in a .env file.")
        return

    # Authenticate (will prompt for login if token.json is missing/invalid)
    service = authenticate()
    
    # Check if there's existing pending work
    pending_file = "data/pending_organization.json"
    if os.path.exists(pending_file):
        print("\n" + "=" * 80)
        print("EXISTING WORK FOUND")
        print("=" * 80)
        print(f"\nFound existing file: {pending_file}")
        print("This file may contain your previous corrections.")
        resume = input("\nDo you want to:\n  1. Resume (skip to review/apply)\n  2. Start fresh (re-analyze emails)\nChoice (1/2, default 1): ")
        
        if resume != "2":
            print("\nResuming from existing data...")
            # Skip to review phase
            import json
            with open(pending_file, "r") as f:
                pending_data = json.load(f)
            
            # Clean categories on load (remove markdown formatting like **)
            for entry in pending_data:
                if "training_data" in entry and "output" in entry["training_data"]:
                    cat = entry["training_data"]["output"]
                    if cat:
                        entry["training_data"]["output"] = cat.strip("*").strip()
            
            # Show what's in the file
            print("\n" + "="*80)
            print(f"{'SUBJECT':<50} | {'CATEGORY'}")
            print("-" * 80)
            for entry in pending_data:
                subject = entry["metadata"]["subject"][:50] + "..." if len(entry["metadata"]["subject"]) > 50 else entry["metadata"]["subject"]
                category = entry["training_data"]["output"]
                print(f"{subject:<50} | {category}")
            print("="*80 + "\n")
            
            # Jump to review phase
            launch_review_and_apply(service, pending_data, pending_file)
            return
        else:
            print("\nStarting fresh analysis...")
    
    # Ask user for number of emails
    try:
        num_emails = int(input("How many emails to analyze? (default 10): ") or 10)
    except ValueError:
        num_emails = 10

    # Ask user for query type
    print("Choose emails to process:")
    print("1. Unread only (is:unread is:inbox)")
    print("2. All Inbox (is:inbox)")
    choice = input("Enter choice (1/2, default 1): ")
    
    query = "is:unread is:inbox"
    if choice == "2":
        query = "is:inbox"
    
    # Load verified IDs to exclude
    verified_ids = set()
    verified_file = "data/verified_emails.json"
    if os.path.exists(verified_file):
        try:
            import json
            with open(verified_file, "r") as f:
                verified_data = json.load(f)
                for entry in verified_data:
                    if "metadata" in entry and "email_id" in entry["metadata"]:
                        verified_ids.add(entry["metadata"]["email_id"])
            print(f"Loaded {len(verified_ids)} verified emails to skip.")
        except Exception as e:
            print(f"Warning: Could not load verified emails: {e}")

    # Fetch emails
    print(f"Fetching {num_emails} emails with query '{query}'...")
    emails = fetch_emails(service, query=query, max_results=num_emails, exclude_ids=verified_ids)
    
    if not emails:
        print("No emails found.")
        return

    print(f"Found {len(emails)} emails to organize.\n")
    
    # Analyze emails and save to pending file
    pending_data = []
    print("Analyzing emails...")
    for email in emails:
        print(f"Processing: {email['subject'][:80]}...")
        category = categorize_email(email["subject"], email["snippet"], email["body"])
        
        # Save in dataset format
        pending_data.append({
            "training_data": {
                "input": f"Subject: {email['subject']}\nBody: {email['body']}",
                "output": category
            },
            "metadata": {
                "email_id": email["id"],
                "subject": email["subject"],
                "sender": email["sender"],
                "recipient": email["recipient"],
                "snippet": email["snippet"],
                "model_prediction": category,
                "thumbs_up": False
            }
        })
        # Rate limiting
        time.sleep(0.5)

    # Save to pending file
    import json
    with open(pending_file, "w") as f:
        json.dump(pending_data, f, indent=4)
    
    print(f"\nSaved {len(pending_data)} emails to {pending_file}")
    
    # Show Preview
    print("\n" + "="*60)
    print(f"{'SUBJECT':<50} | {'CATEGORY'}")
    print("-" * 80)
    for entry in pending_data:
        subject = entry["metadata"]["subject"][:50] + "..." if len(entry["metadata"]["subject"]) > 50 else entry["metadata"]["subject"]
        category = entry["training_data"]["output"]
        print(f"{subject:<50} | {category}")
    print("="*80 + "\n")
    
    # Launch review and apply
    launch_review_and_apply(service, pending_data, pending_file)

if __name__ == "__main__":
    main()
