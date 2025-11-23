# Gmail Organizer & Dataset Builder

This project helps you organize your Gmail inbox and build a verified dataset for classifying emails using LLMs (Google Gemini or local models).

**How it works:**
1.  **Analyze Inbox**: Fetches a batch of emails (default ~200) to understand your inbox patterns.
2.  **Optimize Categories**: Uses Gemini to suggest tailored categories based on your actual emails and generates a custom system prompt.
3.  **Organize & Label**: Fetches new emails and classifies them into the suggested categories using the custom prompt.
4.  **Human Review**: Launches a local web UI (Streamlit) for you to review and correct the LLM's predictions.
5.  **Apply to Gmail**: Once verified, it applies the correct labels to your emails in Gmail and saves the data for future fine-tuning.

## Prerequisites

- Python 3.10 or higher
- A Google Cloud Project with the **Gmail API** enabled
- A **Gemini API Key** from Google AI Studio (optional if using local LLM)
- **LM Studio** (optional for local LLM)

## Installation

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

## Setup

### 1. Gmail API Credentials
To fetch emails, you need to set up OAuth credentials:

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project or select an existing one.
3.  Navigate to **APIs & Services > Library** and search for **Gmail API**. Click **Enable**.
4.  Go to **APIs & Services > OAuth consent screen**.
    *   Select **External** (unless you have a Workspace organization).
    *   Fill in the required fields (App name, User support email, etc.).
    *   **Important**: Under **Test users**, add your own Gmail address. This allows you to use the app in testing mode without verification.
5.  Go to **APIs & Services > Credentials**.
    *   Click **Create Credentials** > **OAuth client ID**.
    *   Application type: **Desktop app**.
    *   Name: "Gmail Organizer" (or similar).
    *   Click **Create**.
6.  Download the JSON file, rename it to `credentials.json`, and place it in the root directory of this project.

### 2. Gemini API Key
If you plan to use Google's Gemini models (recommended for best performance):

1.  Go to [Google AI Studio](https://aistudio.google.com/).
2.  Click **Get API key**.
3.  Click **Create API key** (you can use an existing project or create a new one).
4.  Copy the key string. You will need this for the `.env` file.

### 3. Environment Variables
Create a `.env` file in the root directory.

**For Google Gemini:**
```env
GEMINI_API_KEY=your_api_key_here
```

**For Local LLM (LM Studio):**
```env
USE_LOCAL_LLM=true
# Optional: Manually set context length if auto-detection fails
# LOCAL_LLM_CONTEXT_LENGTH=8192
```

### 4. Local LLM Configuration (Optional)
If using LM Studio:
1.  Install [LM Studio](https://lmstudio.ai/).
2.  Load a model (e.g., Llama 3, Mistral).
3.  Start the local server (default: `http://localhost:1234`).
4.  The system will automatically detect the loaded model and its context length using the native SDK.

### 5. Token Generation (`token.json`)
On the first run, a browser window will prompt you to log in. This creates `token.json`, which stores your session credentials.
- **Function**: Enables future runs without re-authentication.
- **Security**: **Keep this private.** Do not share or commit to Git.

## Usage

### Step 1: Optimize Categories (Optional)
Analyze your recent emails to generate a tailored system prompt with suggested categories based on your actual inbox content.

```bash
uv run python src/category_optimizer.py
```
This will update `prompts/categorize_email_prompt.md` with categories optimized for your emails.

### Step 2: Organize & Label Emails
Fetch emails from your inbox and generate initial labels using the LLM.

```bash
uv run python src/organizer.py
```
*   Fetches new emails (skipping already verified ones).
*   Categorizes them using the configured LLM.
*   Saves pending categorizations to `data/pending_organization.json`.
*   Automatically launches the review app.

### Step 3: Review & Verify Data
The web interface allows you to review, correct, and verify the LLM's categorizations.

```bash
uv run streamlit run src/data_review_app.py
```
*   **Review Mode**: View emails with properly rendered HTML bodies.
*   **Correct**: Fix categories using the dropdown menu.
*   **Save**: Verified emails are saved to `data/verified_emails.json`, building your ground truth dataset.

### Alternative: CLI Dataset Builder
If you prefer a command-line interface for building the dataset without the organizer workflow:

```bash
uv run python src/dataset_builder.py
```

## Project Structure

```text
.
├── data/
│   ├── verified_emails.json      # The ground truth dataset (human-verified)
│   └── pending_organization.json # Temporary storage for unverified predictions
├── credentials.json              # OAuth client ID file from Google Cloud
├── prompts/
│   └── categorize_email_prompt.md # System prompt for the LLM
├── pyproject.toml                # Python dependencies and configuration
├── src/
│   ├── organizer.py              # Main script to fetch and label emails
│   ├── category_optimizer.py     # Analyzes inbox to suggest categories
│   ├── data_review_app.py        # Streamlit web app for data review
│   ├── dataset_builder.py        # CLI tool for building datasets
│   ├── gmail_client.py           # Gmail API authentication and fetching
│   └── llm_client.py             # LLM interaction (Gemini & Local)
└── token.json                    # Auto-generated OAuth token (do not edit)
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
