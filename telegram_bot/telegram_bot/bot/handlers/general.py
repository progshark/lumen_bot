async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    # user = update.effective_user # We are not using the user variable in the new message
    await update.message.reply_text(
        "привет, сеня! я здесь, чтобы поддержать тебя. расскажи, что произошло сегодня и как я могу тебе помочь?"
    )

# You can add other general handlers like /help here
# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     ... 