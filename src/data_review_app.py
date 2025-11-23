import streamlit as st
import json
import pandas as pd
import os

VERIFIED_EMAILS_FILE = "data/verified_emails.json"
REVIEWED_FILE = "data/verified_emails_reviewed.json"
ORGANIZER_FILE = "data/pending_organization.json"
PROMPT_FILE = "prompts/categorize_email_prompt.md"

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
            # Clean categories on load (remove markdown formatting like **)
            for entry in data:
                if "training_data" in entry and "output" in entry["training_data"]:
                    cat = entry["training_data"]["output"]
                    if cat:
                        entry["training_data"]["output"] = cat.strip("*").strip()
            return data
    return []

def save_data(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

def load_categories():
    """Extracts categories from the prompt file."""
    categories = []
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.strip().startswith("- "):
                    # Extract category name (before the colon)
                    cat = line.strip()[2:].split(":")[0].strip()
                    # Clean up markdown formatting
                    cat = cat.strip("*").strip()
                    categories.append(cat)
    return categories

st.set_page_config(page_title="Gmail Data Review", layout="wide")

st.title("Gmail Data Review")

# Sidebar for file selection
st.sidebar.header("Settings")
dataset_option = st.sidebar.radio(
    "Select Dataset",
    ("Verified Emails", "Mailbox Organization (Pending)")
)

if dataset_option == "Verified Emails":
    # Prefer reviewed file for verified emails
    current_file = REVIEWED_FILE if os.path.exists(REVIEWED_FILE) else VERIFIED_EMAILS_FILE
    st.sidebar.info(f"Editing: {current_file}")
else:
    current_file = ORGANIZER_FILE
    st.sidebar.info(f"Editing: {current_file}")

# Load Data
data = load_data(current_file)
categories = load_categories()

if not data:
    st.warning("No data found.")
else:
    # Convert to DataFrame for easier handling in Streamlit, but we'll edit the original list
    # We need to flatten the structure slightly for the table view
    
    # Session state to track changes if needed, but direct edit is simpler for now
    
    st.write(f"Total Entries: {len(data)}")
    
    # Create a list of dicts for the dataframe
    table_data = []
    for i, entry in enumerate(data):
        metadata = entry.get("metadata", {})
        training = entry.get("training_data", {})
        
        # Fallback for old format if any
        if not metadata:
            metadata = {
                "subject": entry.get("subject"),
                "sender": entry.get("sender", "Unknown"),
                "model_prediction": entry.get("llm_prediction"),
                "thumbs_up": entry.get("thumbs_up")
            }
            training = {
                "output": entry.get("user_label")
            }

        table_data.append({
            "Index": i,
            "Subject": metadata.get("subject"),
            "Sender": metadata.get("sender"),
            "Prediction": metadata.get("model_prediction"),
            "Correct Label": training.get("output"),
            "Thumbs Up": metadata.get("thumbs_up")
        })
    
    df = pd.DataFrame(table_data)
    
    # Display interactive table
    # We use data_editor to allow quick edits, but syncing back to JSON requires care
    # For now, let's do a row-by-row review mode which is safer and more detailed
    
    tab1, tab2 = st.tabs(["Review Mode", "Table View"])
    
    with tab1:
        # Pagination
        if "current_index" not in st.session_state:
            st.session_state.current_index = 0
            
        idx = st.session_state.current_index
        
        if 0 <= idx < len(data):
            entry = data[idx]
            
            # Normalize data if needed (handle old format)
            if "metadata" not in entry:
                entry["metadata"] = {
                    "subject": entry.get("subject"),
                    "sender": entry.get("sender", "Unknown"),
                    "recipient": entry.get("recipient", "Unknown"),
                    "snippet": entry.get("snippet"),
                    "model_prediction": entry.get("llm_prediction"),
                    "thumbs_up": entry.get("thumbs_up")
                }
            if "training_data" not in entry:
                entry["training_data"] = {
                    "input": f"Subject: {entry.get('subject')}\nSnippet: {entry.get('snippet')}", # Fallback input
                    "output": entry.get("user_label")
                }
                
            metadata = entry["metadata"]
            training = entry["training_data"]
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"Email {idx + 1}/{len(data)}")
                st.write(f"**Subject:** {metadata.get('subject')}")
                st.write(f"**Sender:** {metadata.get('sender')}")
                st.write(f"**Recipient:** {metadata.get('recipient')}")
                
                with st.expander("View Body Content"):
                    # Try to show the body from input if available, or snippet
                    input_text = training.get("input", "")
                    if "Body:" in input_text:
                        body_text = input_text.split("Body:", 1)[1].strip()
                        
                        # Check if it's HTML content
                        if body_text.strip().startswith("<"):
                            # Render HTML in an iframe for safety and proper rendering
                            st.components.v1.html(
                                f'<div style="max-height: 400px; overflow-y: auto;">{body_text}</div>',
                                height=400,
                                scrolling=True
                            )
                        else:
                            # Plain text email
                            st.text(body_text)
                    else:
                        st.text(metadata.get("snippet"))

            with col2:
                st.info(f"Model Prediction: **{metadata.get('model_prediction')}**")
                
                current_label = training.get("output")
                
                # Thumbs Up/Down logic
                is_correct = st.radio(
                    "Is this correct?",
                    ["Yes", "No"],
                    index=0 if metadata.get("thumbs_up") else 1,
                    key=f"radio_{idx}"
                )
                
                new_label = current_label
                
                if is_correct == "Yes":
                    new_label = metadata.get("model_prediction")
                    metadata["thumbs_up"] = True
                else:
                    metadata["thumbs_up"] = False
                    # Dropdown for correction
                    new_label = st.selectbox(
                        "Select Correct Category",
                        categories,
                        index=categories.index(current_label) if current_label in categories else 0,
                        key=f"select_{idx}"
                    )
                
                # Save changes button
                if st.button("Save & Next", key=f"btn_{idx}"):
                    # Update data
                    training["output"] = new_label
                    entry["training_data"] = training
                    entry["metadata"] = metadata
                    data[idx] = entry
                    save_data(data, current_file)
                    st.success("Saved!")
                    
                    # Move to next
                    if st.session_state.current_index < len(data) - 1:
                        st.session_state.current_index += 1
                    
                    # Always rerun to reflect changes
                    st.rerun()
            
            # Navigation buttons
            c1, c2, c3 = st.columns([1, 1, 8])
            with c1:
                if st.button("Previous"):
                    if st.session_state.current_index > 0:
                        st.session_state.current_index -= 1
                        st.rerun()
            with c2:
                if st.button("Next"):
                    if st.session_state.current_index < len(data) - 1:
                        st.session_state.current_index += 1
                        st.rerun()
                        
        else:
            st.error("Index out of bounds.")

    with tab2:
        st.write("Edit the data directly in the table below. Don't forget to click 'Save Changes'!")
        
        # Configure column config for better editing experience
        column_config = {
            "Index": st.column_config.NumberColumn(disabled=True),
            "Subject": st.column_config.TextColumn(disabled=True),
            "Sender": st.column_config.TextColumn(disabled=True),
            "Prediction": st.column_config.TextColumn(disabled=True),
            "Correct Label": st.column_config.SelectboxColumn(
                "Correct Label",
                options=categories,
                required=True
            ),
            "Thumbs Up": st.column_config.CheckboxColumn(
                "Thumbs Up",
                default=False
            )
        }
        
        edited_df = st.data_editor(
            df,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            key="data_editor"
        )
        
        if st.button("Save Table Changes"):
            # Update the original data list from the edited dataframe
            for index, row in edited_df.iterrows():
                original_idx = row["Index"]
                
                # Update metadata
                data[original_idx]["metadata"]["thumbs_up"] = row["Thumbs Up"]
                
                # Update label
                data[original_idx]["training_data"]["output"] = row["Correct Label"]
                
            save_data(data, current_file)
            st.success("All changes saved to file!")
            st.rerun()
