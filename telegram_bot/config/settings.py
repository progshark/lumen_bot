import os
from dotenv import load_dotenv

# Explicitly define the path to the .env file relative to this script
# __file__ is the path to settings.py
# os.path.dirname(__file__) is the directory containing settings.py (config/)
# os.path.abspath(os.path.join(...)) goes up two levels to the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
dotenv_path = os.path.join(project_root, ".env")

# Load environment variables from .env file
load_dotenv(dotenv_path=dotenv_path)

# Telegram Bot Token (Required)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

# Your Chat ID for notifications (Required for alerts)
FINNY_CHAT_ID = os.getenv("FINNY_CHAT_ID")
if not FINNY_CHAT_ID:
    # Warn instead of raising an error, so bot can still run without notifications
    print("Warning: FINNY_CHAT_ID not found in environment variables. Suicide alert notifications will be disabled.")
    FINNY_CHAT_ID = None # Set to None if not found
else:
    # Ensure it's an integer if found
    try:
        FINNY_CHAT_ID = int(FINNY_CHAT_ID)
    except ValueError:
        print("Warning: FINNY_CHAT_ID is not a valid integer. Suicide alert notifications will be disabled.")
        FINNY_CHAT_ID = None

# Response Delay (Optional, defaults to 1.5 seconds)
try:
    RESPONSE_DELAY = float(os.getenv("RESPONSE_DELAY", "1.5"))
except ValueError:
    print("Warning: RESPONSE_DELAY env variable is not a valid float. Using default 1.5 seconds.")
    RESPONSE_DELAY = 1.5

# Example of another setting (Optional)
# LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
