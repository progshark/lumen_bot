from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
import asyncio
# Import RESPONSE_DELAY from central config
from ...config.settings import RESPONSE_DELAY

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    chat_id = update.effective_chat.id
    user = update.effective_user # Keep user info in case needed later
    # Send a simple lowercase Russian welcome message, including help suggestion
    welcome_message = "привет! я твой бот для эмоциональной поддержки. чтобы узнать больше о том, как я работаю, нажми /help."
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(welcome_message)

# You can add other general handlers like /help here
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    chat_id = update.effective_chat.id
    help_text = (
        "я здесь, чтобы выслушать и поддержать тебя, когда тебе плохо. "
        "я постараюсь понять твое состояние и быть рядом. "
        "если захочешь прекратить разговор, скажи 'стоп' или 'хватит'. "
        "помни, я всего лишь бот и не могу заменить профессиональную помощь или твоего парня. "
        "он тоже очень переживает за тебя."
    )
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(help_text)
