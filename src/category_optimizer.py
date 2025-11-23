import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from src.gmail_client import authenticate, fetch_emails
from src.llm_client import configure_llm

def suggest_categories_with_llm(emails):
    """Uses Gemini to suggest email categories (always uses Gemini for best results)."""
    from google import genai
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Always use Gemini for category optimization (we want the best model for this)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Category optimization requires Gemini.")
    
    client = genai.Client(api_key=api_key)
    print("Using Gemini for category optimization...")

    # Prepare a summary of emails
    email_list_text = ""
    for i, email in enumerate(emails):
        email_list_text += f"{i+1}. Subject: {email['subject']} | Sender: {email['sender']} | Snippet: {email['snippet']}\n"
    
    prompt = f"""
    I have a list of {len(emails)} emails from a user's inbox. 
    Analyze them and suggest a set of 5-8 distinct, mutually exclusive categories that would best organize this specific inbox.

    The current categories are: Work, Personal, Promotions, Social, Updates, Spam.

    If the current categories are good, say so. If they can be improved, please suggest the new list.

    **Important:** Group entire topics together rather than splitting by status.
    (e.g., 'Order Confirmation', 'Shipping Update', and 'Review Request' should all go into one 'Shopping' category).

    Provide the output in this format:

    ### Analysis
    (Brief analysis of the email types found)

    ### Suggested Categories
    - Category 1: Description
    - Category 2: Description
    ...

    Here are the emails:
    {email_list_text}
    """

    print("Analyzing emails with Gemini...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def generate_prompt_content(analysis):
    """Generates the actual system prompt content based on the analysis."""
    from google import genai
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Always use Gemini for prompt generation
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found")
    
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert prompt engineer. 
    Based on the following analysis and suggested categories for an email inbox, create the final system prompt that will be used to categorize emails.
    
    The output must be ONLY the content of the prompt file, with no markdown code blocks or extra text.
    
    The prompt should:
    - Instruct the LLM to categorize emails into the suggested categories
    - Include clear descriptions of each category
    - Use a format like: "You are an email categorization assistant. Categorize the following email into one of these categories: ..."
    
    Email Subject: {{subject}}
    Email Snippet: {{snippet}}
    Email Body: {{body}}
    
    Return ONLY the category name.
    
    ---
    Input Analysis:
    {analysis}
    """
    
    print("Generating optimized prompt...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    # Clean up potential markdown code blocks if the model adds them
    content = response.text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
    if content.endswith("```"):
        content = content.rsplit("\n", 1)[0]
    return content.strip()

def main():
    print("--- Email Category Optimizer ---")
    configure_llm()
    service = authenticate()
    
    print("Fetching last 200 emails...")
    emails = fetch_emails(service, query="is:inbox", max_results=200)
    
    if not emails:
        print("No emails found.")
        return

    suggestion = suggest_categories_with_llm(emails)
    print("\n" + "="*50 + "\n")
    print(suggestion)
    print("\n" + "="*50 + "\n")
    
    # Generate and save the new prompt
    new_prompt = generate_prompt_content(suggestion)
    
    prompt_path = os.path.join(os.getcwd(), "prompts", "categorize_email_prompt.md")
    with open(prompt_path, "w") as f:
        f.write(new_prompt)
        
    print(f"Optimized prompt saved to {prompt_path}")

if __name__ == "__main__":
    main()
