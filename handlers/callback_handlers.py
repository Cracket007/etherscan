from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timezone, timedelta
import logging

def get_period_keyboard():
    """Клавиатура выбора токена"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💎 ETH", callback_data="type_eth"),
        InlineKeyboardButton("💵 USDT", callback_data="type_usdt")
    )
    return markup

def get_time_period_keyboard(token_type):
    """Клавиатура выбора периода"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🕒 Последний месяц", callback_data=f"period_{token_type}_month"),
        InlineKeyboardButton("♾ Все время", callback_data=f"period_{token_type}_all")
    )
    markup.row(InlineKeyboardButton("📋 Выбрать период", callback_data=f"period_{token_type}_custom"))
    markup.row(InlineKeyboardButton("◀️ Назад", callback_data="back_to_tokens"))
    return markup

def get_custom_period_keyboard():
    """Клавиатура для пользовательского периода"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("◀️ Назад", callback_data="back_to_periods"))
    return markup

def process_custom_period(bot, message, db):
    """Обработка пользовательского периода"""
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        
        try:
            start_date_str, end_date_str = text.split()
            start_date = datetime.strptime(start_date_str, '%d.%m.%Y')
            end_date = datetime.strptime(end_date_str, '%d.%m.%Y')
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            if end_date > datetime.now():
                bot.reply_to(message, "❌ Конечная дата не может быть в будущем")
                return
                
            if start_date > end_date:
                bot.reply_to(message, "❌ Начальная дата не может быть позже конечной")
                return
                
            wallet = db.get_user_wallet(chat_id)
            token_type = db.get_user_token(chat_id)
            
            if not wallet:
                bot.reply_to(message, "❌ Сначала отправьте адрес кошелька")
                return
                
            status_message = bot.reply_to(
                message,
                f"⏳ Формирую отчет за период {start_date_str} - {end_date_str}..."
            )
            
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            period_str = f"за {start_date_str} - {end_date_str}"
            
            if token_type == 'eth':
                from main import process_eth_request
                process_eth_request(chat_id, wallet, start_timestamp, end_timestamp, period_str, status_message.message_id)
            else:
                from main import process_usdt_request
                process_usdt_request(chat_id, wallet, start_timestamp, end_timestamp, period_str, status_message.message_id)
            
            db.update_user_state(chat_id, None)
            
        except ValueError:
            bot.reply_to(
                message,
                "❌ Неверный формат периода\n"
                "Используйте формат: ДД.ММ.ГГГГ ДД.ММ.ГГГГ\n"
                "Например: 01.01.2023 31.12.2023"
            )
            
    except Exception as e:
        logging.error(f"Error in process_custom_period: {str(e)}")
        bot.reply_to(message, f"❌ Ошибка при обработке периода: {str(e)}")

def handle_callback(bot, call, db):
    try:
        chat_id = call.message.chat.id
        wallet = db.get_user_wallet(chat_id)
        
        if call.data == "back_to_tokens":
            db.update_user_state(chat_id, None)
            markup = get_period_keyboard()
            bot.edit_message_text(
                "💱 Выберите тип токена для анализа:",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
            return
            
        if call.data == "back_to_periods":
            db.update_user_state(chat_id, None)
            token_type = db.get_user_token(chat_id)
            if not token_type:
                token_type = 'eth'
            markup = get_time_period_keyboard(token_type)
            emoji = "🔷" if token_type == 'eth' else "💎"
            
            bot.edit_message_text(
                f"{emoji} Выберите период для анализа {token_type.upper()} транзакций:",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
            return

        if call.data.startswith('type_'):
            token_type = call.data.split('_')[1]
            db.update_user_token(chat_id, token_type)
            markup = get_time_period_keyboard(token_type)
            emoji = "🔷" if token_type == 'eth' else "💎"
            
            bot.edit_message_text(
                f"{emoji} Выберите период для анализа {token_type.upper()} транзакций:",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
            return

        if call.data.startswith('period_'):
            parts = call.data.split('_')
            token_type = parts[1]
            period = parts[2]
            
            if period == 'custom':
                db.update_user_state(chat_id, 'waiting_period')
                markup = get_custom_period_keyboard()
                bot.edit_message_text(
                    "📅 Введите период в формате:\n"
                    "ДД.ММ.ГГГГ ДД.ММ.ГГГГ\n\n"
                    "Например: 01.01.2023 31.12.2023",
                    chat_id,
                    call.message.message_id,
                    reply_markup=markup
                )
                return

            now = datetime.now(timezone.utc)
            end_timestamp = int(now.timestamp())
            
            if period == 'all':
                start_timestamp = None
                period_str = "за все время"
            else:
                start_timestamp = int((now - timedelta(days=30)).timestamp())
                period_str = "за последний месяц"

            try:
                bot.edit_message_text(
                    "⏳ Формирование отчета...",
                    chat_id,
                    call.message.message_id
                )
                
                if token_type == 'eth':
                    from main import process_eth_request
                    process_eth_request(chat_id, wallet, start_timestamp, end_timestamp, period_str, call.message.message_id)
                else:
                    from main import process_usdt_request
                    process_usdt_request(chat_id, wallet, start_timestamp, end_timestamp, period_str, call.message.message_id)
                    
            except Exception as e:
                bot.edit_message_text(
                    f"❌ Ошибка при формировании отчета: {str(e)}",
                    chat_id,
                    call.message.message_id
                )

        bot.answer_callback_query(call.id)
            
    except Exception as e:
        bot.answer_callback_query(call.id, "Произошла ошибка при обработке запроса")
