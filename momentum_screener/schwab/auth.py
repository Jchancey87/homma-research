import os
import schwab.auth
from schwab.client import Client

# Path to store the OAuth token
TOKEN_PATH = os.path.expanduser(os.getenv('SCHWAB_TOKEN_PATH', '~/.config/schwab/token.json'))

def get_client():
    """
    Returns an authenticated schwab.client.Client.
    Uses cached token if available, otherwise initiates OAuth flow.
    """
    api_key = os.getenv('SCHWAB_API_KEY')
    api_secret = os.getenv('SCHWAB_API_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL', 'https://127.0.0.1')

    if not api_key or not api_secret:
        raise ValueError("SCHWAB_API_KEY and SCHWAB_API_SECRET must be set in environment")

    # Ensure token directory exists
    token_dir = os.path.dirname(TOKEN_PATH)
    if token_dir:
        os.makedirs(token_dir, exist_ok=True)

    try:
        # Attempt to create client from existing token
        client = schwab.auth.client_from_token_file(TOKEN_PATH, api_key, api_secret)
        return client
    except FileNotFoundError:
        # This will require interactive input if run from terminal
        # In a headless environment, this might fail unless setup_oauth was run first.
        return schwab.auth.easy_client(api_key, api_secret, callback_url, TOKEN_PATH)

def setup_oauth():
    """
    CLI helper to run the one-time OAuth setup.
    """
    api_key = os.getenv('SCHWAB_API_KEY')
    api_secret = os.getenv('SCHWAB_API_SECRET')
    callback_url = os.getenv('SCHWAB_CALLBACK_URL', 'https://127.0.0.1')
    
    if not api_key or not api_secret:
        print("Error: SCHWAB_API_KEY and SCHWAB_API_SECRET must be set.")
        return

    token_dir = os.path.dirname(TOKEN_PATH)
    if token_dir:
        os.makedirs(token_dir, exist_ok=True)
        
    print(f"Starting OAuth setup. Token will be saved to {TOKEN_PATH}")
    schwab.auth.easy_client(api_key, api_secret, callback_url, TOKEN_PATH)
