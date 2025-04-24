import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Assuming your settings are in config.settings
# Adjust the import path if your structure is different
from ..config.settings import TELEGRAM_BOT_TOKEN  # Changed to relative import
from .handlers import general, situation_handler # Import general and situation handlers

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Register Handlers --- 

    # General command handlers (e.g., /start, /help)
    application.add_handler(CommandHandler("start", general.start))
    application.add_handler(CommandHandler("help", general.help_command))

    # Support message handlers (e.g., handling user text for support)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, situation_handler.handle_situation))

    # Add more handlers here for different commands or message types
    
    logger.info("Bot starting...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
