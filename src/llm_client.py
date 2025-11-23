import os
from dotenv import load_dotenv

load_dotenv()

# Global client instance
_client = None
_llm_type = None
_model_context_length = None

def configure_llm():
    """Configures the LLM client based on environment variables."""
    global _client, _llm_type, _model_context_length
    
    # Check which LLM to use
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        # Local LLM via LM Studio native SDK
        try:
            import lmstudio as lms
            
            _client = lms.llm()
            _llm_type = "local"
            
            # Get context length from the loaded model
            _model_context_length = _client.get_context_length()
            model_name = "LM Studio Model"  # LM Studio SDK doesn't expose model name easily
            
            print(f"Using LM Studio with context length: {_model_context_length} tokens")
            
        except ImportError:
            # Fallback to OpenAI-compatible API if lmstudio package not installed
            print("LM Studio SDK not found, using OpenAI-compatible API...")
            from openai import OpenAI
            
            base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1")
            api_key = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")
            
            _client = OpenAI(base_url=base_url, api_key=api_key)
            _llm_type = "local_openai"
            
            # Auto-detect model if not specified
            model_name = os.getenv("LOCAL_LLM_MODEL")
            if not model_name:
                try:
                    models = _client.models.list()
                    if models.data:
                        model_name = models.data[0].id
                        print(f"Auto-detected model: {model_name}")
                    else:
                        raise ValueError("No models found in LM Studio. Please load a model first.")
                except Exception as e:
                    raise ValueError(f"Failed to detect model from LM Studio: {e}")
            
            # Try to get context length from model info
            # First check if manually configured
            manual_context = os.getenv("LOCAL_LLM_CONTEXT_LENGTH")
            if manual_context:
                _model_context_length = int(manual_context)
                print(f"Using configured context length: {_model_context_length} tokens")
            else:
                try:
                    model_info = _client.models.retrieve(model_name)
                    if hasattr(model_info, 'context_length'):
                        _model_context_length = model_info.context_length
                        print(f"Model context length: {_model_context_length} tokens")
                    else:
                        _model_context_length = 4096
                        print(f"Could not retrieve context length, using default: {_model_context_length}")
                        print("Tip: Set LOCAL_LLM_CONTEXT_LENGTH in .env to match your model's context")
                except Exception as e:
                    _model_context_length = 4096
                    print(f"Could not retrieve context length, using default: {_model_context_length}")
                    print("Tip: Set LOCAL_LLM_CONTEXT_LENGTH in .env to match your model's context")
            
            # Store model name for later use
            os.environ["LOCAL_LLM_MODEL"] = model_name
            print(f"Using local LLM at {base_url} with model: {model_name}")
    else:
        # Google Gemini
        from google import genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        _client = genai.Client(api_key=api_key)
        _llm_type = "gemini"
        print("Using Google Gemini")

def categorize_email(subject, snippet, body):
    """Categorizes an email using the configured LLM."""
    if _client is None:
        configure_llm()
    
    try:
        prompt_path = os.path.join(os.getcwd(), "prompts", "categorize_email_prompt.md")
        with open(prompt_path, "r") as f:
            prompt_template = f.read()
        
        # Format the full prompt first
        full_prompt = prompt_template.format(subject=subject, snippet=snippet, body=body)
        
        if _llm_type == "local":
            # LM Studio native SDK - use proper tokenization
            import lmstudio as lms
            
            # Create a chat object
            chat = lms.Chat.from_history({
                "messages": [
                    {"role": "system", "content": "You are an email categorization assistant."},
                    {"role": "user", "content": full_prompt}
                ]
            })
            
            # Check if it fits in context
            formatted = _client.apply_prompt_template(chat)
            token_count = len(_client.tokenize(formatted))
            context_length = _client.get_context_length()
            
            # If too long, truncate the body and retry
            if token_count >= context_length:
                # Calculate how much to truncate
                chars_per_token = len(body) / max(token_count - 500, 1)  # Rough estimate
                max_body_chars = int((context_length - 500) * chars_per_token * 0.4)  # Use 50% for body
                
                truncated_body = body[:max_body_chars] + "\n[... truncated for length ...]"
                full_prompt = prompt_template.format(subject=subject, snippet=snippet, body=truncated_body)
                
                chat = lms.Chat.from_history({
                    "messages": [
                        {"role": "system", "content": "You are an email categorization assistant."},
                        {"role": "user", "content": full_prompt}
                    ]
                })
                
                print(f"Truncated email body from {len(body)} to {max_body_chars} chars to fit context")
            
            # Generate response
            response = _client.respond(chat, config={"temperature": 0.3})
            category = response.content.strip()
            return category
            
        elif _llm_type == "local_openai":
            # OpenAI-compatible API fallback
            # Truncate body based on estimated context
            max_tokens_for_body = int(_model_context_length * 0.5)
            max_body_length = max_tokens_for_body * 4  # Rough estimate: 1 token ≈ 4 chars
            
            truncated_body = body[:max_body_length]
            if len(body) > max_body_length:
                truncated_body += "\n[... truncated for length ...]"
            
            prompt = prompt_template.format(subject=subject, snippet=snippet, body=truncated_body)
            model_name = os.getenv("LOCAL_LLM_MODEL")
            
            response = _client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an email categorization assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )
            category = response.choices[0].message.content.strip()
            
            # Clean up markdown formatting
            category = category.strip("*").strip()
            
            return category
        else:
            # Gemini API call
            response = _client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            category = response.text.strip()
            
            # Clean up markdown formatting
            category = category.strip("*").strip()
            
            return category
            
    except Exception as e:
        error_msg = str(e)
        
        # Handle context length errors specifically
        if "context length" in error_msg.lower() or "tokens" in error_msg.lower():
            print(f"Warning: Email too long for model context. Subject: {subject[:50]}...")
            print("Tip: Increase context length in LM Studio or use a model with larger context window")
            return "Uncategorized"
        
        print(f"Error calling LLM: {e}")
        return "Uncategorized"
