import logging
import asyncio
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from ...config.settings import FINNY_CHAT_ID
from ...config.settings import RESPONSE_DELAY

logger = logging.getLogger(__name__)

# State key for user_data
AWAITING_CLARIFICATION = 'awaiting_situation_clarification'
CONVERSATION_TOPIC_KEY = 'current_conversation_topic'

# Keywords to end the conversation
EXIT_KEYWORDS = {"стоп", "хватит", "не хочу говорить", "оставь меня", "замолчи", "отстань"}

# --- Babushka Alla Specifics ---
STATE_BABUSHKA_QUESTIONED = 'babushka_alla_questioned'
STATE_BABUSHKA_VALIDATED = 'babushka_alla_validated'
BABUSHKA_QUOTE_KEYWORDS = {"сказала", "говорит", "\"", "«", "»", "заявила", "сказала мне"}
SELF_DOUBT_KEYWORDS = {"она права", "думаю она права", "может она права", "наверное она права", "я думаю так же", "может быть", "наверное"}

# Messages for Babushka Alla flow
babushka_question = "что она сказала или сделала, что тебя расстроило?"
babushka_validation = "мне очень жаль, что тебе пришлось это услышать. ты не заслуживаешь таких слов. то, что она сказала - это неправда."
babushka_reassurance = "ты очень смышленная, добрая и невероятно сильная и храбрая. фин гордится тобой и верит в тебя даже тогда, когда другие не видят, какой ты чудесный человек"
babushka_final_follow_up = "твои чувства важны. если захочешь поделиться еще чем-то, я буду слушать."
# --- End Babushka Alla Specifics ---

# --- Gentle Suggestions --- 
SUGGESTION_OFFERED_KEY = 'suggestion_offered_for_topic'

# Placeholder suggestions (replace/add as needed)
suggestion_overwhelmed = (
    "кажется, на тебя все навалилось. мир может казаться порой очень шумным.\n"
    "ты не обязана все вывозить. иногда тело сигнализирует тебе о том, что ему тяжело. но это не слабость. это лишь сигнал\n"
    "позволь себе отдохнуть. я тут, с тобой"
)
suggestion_pain = (
    "я слышу, что тебе сейчас очень больно. это не делает тебя слабой или какой-то неправильной - это говорит о том, насколько сильно ты чувствуешь. это просто эмоции, и они не делают тебя плохой.\n"
    "хочешь мы попробуем вместе упражнение, чтобы чуть-чуть отпустить напряжение? или, может, тебе хочется просто выговориться? я рядом"
)
suggestion_depressed = "как насчет того, чтобы прочитать те письма, которое тебе написал фин? я думаю, что сквозь эти письма, написанные от руки, ты сможешь ощутить тепло и близость к нему"

SUGGESTION_MESSAGES = {
    "feeling_overwhelmed": suggestion_overwhelmed,
    "intense_pain": suggestion_pain,
    "lonely_depressed": suggestion_depressed,
    # Add other situation_ids mapped to suggestion strings here
}
# --- End Gentle Suggestions ---

# Situations that should not automatically ask for elaboration
SITUATIONS_WITHOUT_FOLLOWUP = {"suicidal_ideation", "panic_attack", "babushka_alla"}

# Dictionary to map keywords/phrases to situation identifiers (RUSSIAN)
# Order matters slightly - more specific or critical items should come first if overlap is possible.
SITUATION_TRIGGERS = {
    # Critical First:
    ("хочу умереть", "убить себя", "не хочу жить", "закончить всё", "я хочу убить себя"): "suicidal_ideation", # CRITICAL
    # Specific Triggers:
    ("паническая атака", "не могу дышать", "паника"): "panic_attack",
    ("ненавидишь меня", "не любишь меня", "ты меня ненавидишь", "мой парень ненавидит меня", "он не любит меня"): "thinks_i_hate_her",
    ("я больше не могу", "слишком тяжело", "всё навалилось", "я не вывожу", "не могу выдержать"): "feeling_overwhelmed", # Added "не могу выдержать"
    ("бабушка алла", "алла"): "babushka_alla",
    ("папа злой", "отец злой", "папа груб", "отец груб", "папа меня не любит"): "father_mean",
    ("папина работа", "работа отца", "из-за работы", "не могу выехать из россии"): "father_job_barrier", # Added context from user
    ("стеша агрессивная", "стеша злая", "агрессия стеши", "стеша злится на меня", "стеша злая на меня"): "stesha_aggressive",
    ("стеша хочет сойтись", "стеша хочет быть вместе", "стеша предлагает сойтись"): "stesha_wants_reunion",
    ("очень больно", "сильная боль", "боль внутри", "душа болит", "мне очень больно и одиноко"): "intense_pain",
    ("ты уйдешь", "ты бросишь меня", "изменишь мне", "боюсь, что уйдешь", "мой парень бросит меня", "мой парень уйдет от меня", "мой парень не хочет быть со мной"): "fear_of_leaving",
    ("одиноко", "депрессия", "мне грустно", "чувствую себя одинокой"): "lonely_depressed",
    # Add more specific keywords/phrases as needed
}

# Dictionary mapping situation IDs to response functions or messages (function names remain)
# RESPONSE_STRATEGIES = {
#     "suicidal_ideation": handle_suicidal_ideation,
#     "panic_attack": handle_panic_attack,
#     "thinks_i_hate_her": handle_thinks_i_hate_her,
#     "feeling_overwhelmed": handle_feeling_overwhelmed,
#     "babuska_alla": handle_babuska_alla,
#     "father_mean": handle_father_mean,
#     "father_job_barrier": handle_father_job_barrier,
#     "stesha_aggressive": handle_stesha_aggressive,
#     "stesha_wants_reunion": handle_stesha_wants_reunion,
#     "intense_pain": handle_intense_pain,
#     "fear_of_leaving": handle_fear_of_leaving,
#     "lonely_depressed": handle_lonely_depressed,
# }

async def handle_situation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the conversation flow, including situation detection, follow-ups, and exit."""
    message_text = update.message.text.strip().lower()
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Define standard responses (including Babushka specific ones)
    talk_to_bf_message = "я был рад с тобой пообщаться по душам. finny передает тебе крепкие объятия и пламенный привет! а также желает добрых снов и посылает лучи добра и силы! дай мне, пожалуйста, знать, если захочешь снова пообщаться со мной. спокойной ночи!"
    listener_response = "я здесь, я слушаю"
    clarification_question = "что тебя беспокоит в данный момент?"
    clarification_failed_response = "спасибо, что уточнила. я здесь, чтобы выслушать тебя"
    # Babushka messages defined earlier near constants

    # --- Conversation Flow Logic ---

    # 1. Check for Exit Keywords
    if message_text in EXIT_KEYWORDS:
        logger.info(f"Exit keyword '{message_text}' detected from {user.first_name} (chat_id: {chat_id}). Ending conversation.")
        context.user_data.pop(CONVERSATION_TOPIC_KEY, None)
        context.user_data.pop(AWAITING_CLARIFICATION, None)
        context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(RESPONSE_DELAY)
        await update.message.reply_text(talk_to_bf_message)
        return

    # 2. Check if currently in a specific conversation topic
    current_topic = context.user_data.get(CONVERSATION_TOPIC_KEY)
    if current_topic:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        # --- Handle Babushka Alla specific states first ---
        if current_topic == STATE_BABUSHKA_QUESTIONED:
            logger.info(f"Received answer for Babushka Alla question from {user.first_name}. Sending validation.")
            await asyncio.sleep(RESPONSE_DELAY)
            await update.message.reply_text(babushka_validation)
            await asyncio.sleep(RESPONSE_DELAY)
            await update.message.reply_text(babushka_final_follow_up)
            context.user_data[CONVERSATION_TOPIC_KEY] = STATE_BABUSHKA_VALIDATED
            context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
            return
        
        elif current_topic == STATE_BABUSHKA_VALIDATED:
            logger.info(f"Received reaction after Babushka Alla validation from {user.first_name}.")
            if any(keyword in message_text for keyword in SELF_DOUBT_KEYWORDS):
                logger.info("Self-doubt detected after Babushka validation. Sending reassurance.")
                await asyncio.sleep(RESPONSE_DELAY)
                await update.message.reply_text(babushka_reassurance)
                await asyncio.sleep(RESPONSE_DELAY)
                await update.message.reply_text(babushka_final_follow_up)
            else:
                logger.info("No self-doubt detected after Babushka validation. Sending listener response.")
                await asyncio.sleep(RESPONSE_DELAY)
                await update.message.reply_text(listener_response)
            context.user_data.pop(CONVERSATION_TOPIC_KEY, None)
            context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
            return

        # --- Handle generic conversation state (for other topics) ---
        else:
            logger.info(f"Received follow-up message from {user.first_name} (chat_id: {chat_id}) for generic topic '{current_topic}'. Responding as listener.")
            await asyncio.sleep(RESPONSE_DELAY)
            await update.message.reply_text(listener_response)

            # Check if a suggestion should be offered for this topic
            suggestion_text = SUGGESTION_MESSAGES.get(current_topic)
            suggestion_already_offered = context.user_data.get(SUGGESTION_OFFERED_KEY, False)

            if suggestion_text and not suggestion_already_offered:
                logger.info(f"Offering suggestion for topic '{current_topic}'")
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(RESPONSE_DELAY)
                await update.message.reply_text(suggestion_text)
                context.user_data[SUGGESTION_OFFERED_KEY] = True # Mark suggestion as offered
            # else: No suggestion for this topic or already offered

            return

    # 3. Check if awaiting clarification for "мне плохо"
    if context.user_data.get(AWAITING_CLARIFICATION):
        logger.info(f"Received clarification message from {user.first_name} (chat_id: {chat_id}): '{message_text}'")
        context.user_data[AWAITING_CLARIFICATION] = False # Consume the flag

        # Try to identify the situation from the clarification
        identified_situation = None
        for keywords, situation_id in SITUATION_TRIGGERS.items():
            if any(keyword in message_text for keyword in keywords):
                identified_situation = situation_id
                break

        if identified_situation:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await trigger_response_strategy(identified_situation, update, context)
        else:
            logger.info(f"Clarification from {user.first_name} did not match known situations.")
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(RESPONSE_DELAY)
            await update.message.reply_text(clarification_failed_response)
            context.user_data.pop(CONVERSATION_TOPIC_KEY, None)
            context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
        return
        
    # 4. Check for initial "мне плохо"
    if message_text == "мне плохо":
        logger.info(f"Detected 'мне плохо' from {user.first_name} (chat_id: {chat_id}). Asking for clarification.")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(RESPONSE_DELAY)
        await update.message.reply_text(clarification_question)
        context.user_data[AWAITING_CLARIFICATION] = True # Set flag to wait for next message
        context.user_data.pop(CONVERSATION_TOPIC_KEY, None)
        context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
        return

    # 5. Check for initial situation trigger (if not in conversation, not clarifying, not exiting)
    identified_situation = None
    for keywords, situation_id in SITUATION_TRIGGERS.items():
        if any(keyword in message_text for keyword in keywords):
            identified_situation = situation_id
            break

    if identified_situation:
        # Reset suggestion offered flag when a NEW topic starts
        context.user_data.pop(SUGGESTION_OFFERED_KEY, None)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await trigger_response_strategy(identified_situation, update, context)
        return

    # 6. Default Fallback (if nothing else matched)
    logger.info(f"No specific trigger, state, or command detected for message from {user.first_name}: '{message_text}'. Sending default listener response.")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(listener_response)


async def trigger_response_strategy(situation_id: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper function to execute the response strategy and set conversation state."""
    user = update.effective_user
    logger.info(f"Identified situation '{situation_id}' for user {user.first_name}")
    
    response_strategy = RESPONSE_STRATEGIES.get(situation_id)

    if callable(response_strategy):
        await response_strategy(update, context)
        # After executing the main response, set the conversation topic state
        if situation_id not in SITUATIONS_WITHOUT_FOLLOWUP:
            context.user_data[CONVERSATION_TOPIC_KEY] = situation_id
            logger.info(f"Executed handler for {situation_id} and set state for user {user.first_name}")

    elif isinstance(response_strategy, str):
        await update.message.reply_text(response_strategy) # Although we expect functions now
        # Also set state if it was just a string response (though less likely)
        if situation_id not in SITUATIONS_WITHOUT_FOLLOWUP:
            context.user_data[CONVERSATION_TOPIC_KEY] = situation_id
            logger.info(f"Executed handler for {situation_id} (string response) and set state for user {user.first_name}")
    else:
        # Default fallback or log an error if no strategy found
        logger.warning(f"No response strategy defined for situation: {situation_id}")
        # Generic supportive message in Russian
        await update.message.reply_text("я слышу тебя. похоже, сейчас действительно тяжело. я здесь, чтобы выслушать.")


# --- Define Specific Handler Functions (Placeholders - NEED RUSSIAN TEXT) ---

async def handle_suicidal_ideation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages indicating suicidal ideation. CRITICAL PRIORITY."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    # Action sent before trigger_response_strategy is called - already handled
    response_part1 = (
        "мне очень жаль, что тебе сейчас так больно. любимая, пожалуйста, помни, что ты не одна и фин рядом."
    )
    # Crisis plan information
    crisis_intro = "если тебе совсем плохо, вот список горячих линий и людей, которым можно позвонить и/или написать. ты не одна."
    crisis_contacts = (
        "контакты:\n"
        "- фин\n"
        "- соня\n"
        "- стеша\n"
        "- ярослав\n"
        "- психотерапевтка\n"
        "- телефон горячей линии психологической помощи мчс россии (круглосуточно): +7 (495) 989-50-50"
    )
    notification_message = "СРОЧНО: суицидальные мысли, пора спасать, немедленно свяжись"

    # Send messages to the user
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(crisis_intro)
    await asyncio.sleep(RESPONSE_DELAY) # Small delay before listing contacts
    await update.message.reply_text(crisis_contacts)

    # Send notification to Finny
    if FINNY_CHAT_ID:
        try:
            logger.info(f"Sending suicide alert notification to chat ID: {FINNY_CHAT_ID}")
            await context.bot.send_message(chat_id=FINNY_CHAT_ID, text=notification_message)
        except Exception as e:
            logger.error(f"Failed to send suicide alert notification to {FINNY_CHAT_ID}: {e}")
    else:
        logger.warning("FINNY_CHAT_ID not configured. Skipping suicide alert notification.")

async def handle_panic_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Offers simple grounding techniques for a panic attack."""
    response_part1 = (
        "ты в безопасности. все, что ты сейчас чувствуешь - это паническая атака. "
        "это очень неприятно и возможно страшно, но она не опасна, и она пройдет. я с тобой! "
    )
    response_part2 = (
        "давай дышать вместе: \n"
        "1. вдохни на 4 счета\n"
        "2. задержи дыхание\n"
        "3. и медленно выдохни на 6\n"
        "давай сделаем так несколько раз вместе. "
    )
    response_part3 = (
        "если получится, попробуй назвать 5 вещей красного цвета вокруг себя прямо сейчас. "
        "это может помочь тебе вернуться в настоящий момент"
    )
    response_part4 = (
        "а теперь 5 вещей коричневного цвета"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part2)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part3)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part4)

async def handle_thinks_i_hate_her(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages expressing fear that you hate her."""
    response_text = (
        "мне больно слышать, что ты так себя чувствуешь. но если это так - значит, тебе очень плохо сейчас, и я это понимаю. "
        "но поверь, его отношение к тебе нисколько не изменилось. фин тебя безумно сильно любит. "
        "даже если тебе сейчас в это сложно поверить - это все равно правда"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_text)
    # Add tailored follow-up
    follow_up = "это нормально - сомневаться, когда тебе больно. если хочешь поговорить об этом, я рядом."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_feeling_overwhelmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about feeling overwhelmed."""
    response_part1 = (
        "звучит так, будто тебе сейчас невероятно тяжело, словно все навалилось разом."
    )
    response_part2 = (
         "тебе не нужно нести все это в одиночку. фин с тобой. "
         "сейчас тяжело, но это не навсегда. дыши, я никуда не ухожу."
    )
    response_part3 = (
        "попробуй прямо сейчас обнять подушку, завернуться в одеяло. твоя нервная система заслуживает покоя."
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part2)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part3)
    # Add tailored follow-up
    follow_up = "помни, ты не одна в этом. если хочешь выговориться или просто помолчать вместе, я здесь."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_babushka_alla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the initial trigger for 'Бабушка Алла' based on message content."""
    message_text = update.message.text.lower()
    # Check if the message likely contains what Alla said
    if any(keyword in message_text for keyword in BABUSHKA_QUOTE_KEYWORDS):
        logger.info("Babushka Alla trigger contains quote keywords. Sending validation.")
        await asyncio.sleep(RESPONSE_DELAY)
        await update.message.reply_text(babushka_validation)
        await asyncio.sleep(RESPONSE_DELAY)
        await update.message.reply_text(babushka_final_follow_up)
        context.user_data[CONVERSATION_TOPIC_KEY] = STATE_BABUSHKA_VALIDATED
    else:
        logger.info("Babushka Alla trigger does not contain quote keywords. Asking question.")
        await asyncio.sleep(RESPONSE_DELAY)
        await update.message.reply_text(babushka_question)
        context.user_data[CONVERSATION_TOPIC_KEY] = STATE_BABUSHKA_QUESTIONED

async def handle_father_mean(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about her father being mean."""
    response_text = (
        "мне очень жаль, что тебе пришлось это пережить. никто не имеет права так с тобой говорить. "
        "то, что он сказал - это неправда. это его страхи и неисполненные мечты, не твои. а ты - сильная, живая и храбрая."
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_text)
    # Add tailored follow-up
    follow_up = "такие слова ранят. если тебе нужно выплеснуть эмоции или просто побыть в тишине, я здесь."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_father_job_barrier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about her father's job being a barrier."""
    response_text = (
        "я понимаю, как страшно чувствовать, что твои мечты под угрозой. это тяжело - особенно, когда далеко не все зависит от тебя. "
        "я верю в то, что ты сможешь вырваться и жить так, как хочешь. вы с фином обязательно найдете выход из этой ситуации. "
        "только не сдавайся, он с тобой"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_text)
    # Add tailored follow-up
    follow_up = "это сложная ситуация, и твои переживания понятны. если хочешь обсудить какие-то мысли или чувства по этому поводу, я слушаю."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_stesha_aggressive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about 'Стеша' being aggressive."""
    response_text = (
        "это звучит очень грубо. ты не заслуживаешь такого обращения. "
        "хочешь рассказать, что именно произошло? что она сказала или сделала? мне важно знать, что ты почувствовала"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_text)
    # Add tailored follow-up
    follow_up = "помни, твоя реакция и чувства абсолютно нормальны. если захочешь рассказать подробнее, я здесь."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_stesha_wants_reunion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about 'Стеша' wanting to get together."""
    response_part1 = (
        "слышать, что стеша хочет сойтись... это действительно может нервировать и доставлять дискомфорт, "
        "особенно когда ты уже в отношениях с кем-то другим. я могу понять, почему это вызывает у тебя такие чувства."
    )
    response_part2 = (
        "но важно помнить, что ты заслуживаешь быть с тем, кто делает тебя счастливой. если тебе нужно поговорить, я всегда рядом"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part2)
    # Add tailored follow-up
    follow_up = "это может вызывать смешанные чувства. если хочешь разобраться в них или просто поделиться, я здесь."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_intense_pain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about feeling intense internal pain."""
    response_part1 = (
        "я знаю, как это больно - чувствовать пустоту и как будто ничего не имеет смысла. "
        "мне жаль, что тебе так тяжело сейчас. знай, что эти чувства проходят, даже если сейчас кажется, что они останутся навсегда."
    )
    response_part2 = (
        "ты не обязана проходить через это одна."
    )
    response_part3 = (
        "я здесь рядом и готов поддержать тебя."
    )
    response_part4 = (
        "может быть, ты хочешь вместе поговорить о том, что сейчас тебя так мучает?"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part2)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part3)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part4)

async def handle_fear_of_leaving(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages expressing fear of being left or cheated on."""
    response_text = (
        "я понимаю, что ты переживаешь, но хочу, чтобы ты знала: фин никуда не уходит и не меняет свое отношение к тебе. "
        "ты дня него - the one. ему не интересно искать кого-то другого, потому что он уже нашел тебя, и ты для него очень важна. "
        "ты - все, что ему нужно. не переживай, ты не потеряешь его"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_text)
    # Add tailored follow-up
    follow_up = "эти страхи могут быть сильными. если хочешь поговорить о них еще, я здесь, чтобы слушать."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

async def handle_lonely_depressed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages about feeling lonely or depressed."""
    response_part1 = (
        "мне больно слышать, что ты чувствуешь себя одиноко и депрессивно. эти чувства - настоящие, но они не определяют тебя"
    )
    response_part2 = (
        "твои чувства важны, и фин всегда будет рядом, чтобы помочь тебе пройти через это"
    )
    response_part3 = (
        "если хочешь, можем вместе подумать, как улучшить твое самочувствие"
    )
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part1)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part2)
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(response_part3)
    # Add tailored follow-up
    follow_up = "помни, что ты не одна, даже когда кажется иначе. если хочешь поделиться тем, что на душе, я слушаю."
    await asyncio.sleep(RESPONSE_DELAY)
    await update.message.reply_text(follow_up)

# TODO: Define handler functions for other situations:
# async def handle_thinks_user_hates_her(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: ...
# async def handle_feeling_overwhelmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: ...
# async def handle_babuska_alla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: ...
# ... and so on for all situations ...

# --- Define Response Strategy Mapping AFTER functions are defined ---
RESPONSE_STRATEGIES = {
    "suicidal_ideation": handle_suicidal_ideation,
    "panic_attack": handle_panic_attack,
    "thinks_i_hate_her": handle_thinks_i_hate_her,
    "feeling_overwhelmed": handle_feeling_overwhelmed,
    "babushka_alla": handle_babushka_alla,
    "father_mean": handle_father_mean,
    "father_job_barrier": handle_father_job_barrier,
    "stesha_aggressive": handle_stesha_aggressive,
    "stesha_wants_reunion": handle_stesha_wants_reunion,
    "intense_pain": handle_intense_pain,
    "fear_of_leaving": handle_fear_of_leaving,
    "lonely_depressed": handle_lonely_depressed,
} 