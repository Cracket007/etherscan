__all__ = ['process_eth_request', 'process_usdt_request']

from datetime import datetime, timezone, timedelta
import os
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from etherscan import Etherscan
import requests
from dotenv import load_dotenv
from handlers.callback_handlers import (
    handle_callback, 
    get_period_keyboard, 
    get_custom_period_keyboard,
    process_custom_period
)
from usdt_handler import (
    process_usdt_transactions, 
    get_usdt_balance, 
    get_usdt_price, 
    USDT_CONTRACT, 
    USDT_DECIMALS
)
from handlers.command_handlers import register_command_handlers, get_wallet_balances_at_date
from database import Database
import signal
import sys
import csv

load_dotenv()
API_KEY = os.getenv('ETHERSCAN_API_KEY')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

bot = TeleBot(BOT_TOKEN)
db = Database()
eth_client = Etherscan(API_KEY)

def get_eth_usd_price():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        data = response.json()
        if 'ethereum' in data and 'usd' in data['ethereum']:
            return float(data['ethereum']['usd'])
        return None
    except Exception:
        return None

def save_to_csv(transactions, filename):
    """Сохраняет транзакции в CSV файл"""
    os.makedirs("reports", exist_ok=True)
    file_path = f"reports/{filename}"

    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=[
            'Date', 'From', 'To', 'Transaction Hash', 'Amount In (ETH)',
            'Amount Out (ETH)', 'Fee (ETH)', 'Fee (USD)', 'CurrentValue', 
            'General amount', 'General amount USD'
        ])
        writer.writeheader()
        writer.writerows(transactions)
    return file_path


def process_transactions(transactions, wallet_address, eth_usd_price):
    processed = []
    for tx in transactions:
        tx_hash = tx['hash']
        timestamp = int(tx['timeStamp'])
        date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%d/%m/%Y')
        
        from_address = tx['from']
        to_address = tx['to']
        
        value_wei = int(tx['value'])
        value_eth = value_wei / 10**18
        
        gas_price_wei = int(tx['gasPrice'])
        gas_used = int(tx['gasUsed'])
        fee_wei = gas_price_wei * gas_used
        fee_eth = fee_wei / 10**18
        fee_usd = fee_eth * eth_usd_price if eth_usd_price else 0
        
        is_outgoing = from_address.lower() == wallet_address.lower()
        amount_out_eth = value_eth if is_outgoing else 0
        
        current_value = value_eth * eth_usd_price if eth_usd_price else 0
        
        general_amount = value_eth if not is_outgoing else amount_out_eth
        if is_outgoing:
            general_amount -= fee_eth
        
        general_amount_usd = general_amount * eth_usd_price

        # Оригинальная строка транзакции
        processed.append({
            'Transaction Hash': tx_hash,
            'Date': date,
            'From': from_address,
            'To': to_address,
            'Amount In (ETH)': value_eth if not is_outgoing else 0,
            'Amount Out (ETH)': amount_out_eth,
            'Fee (ETH)': fee_eth,
            'Fee (USD)': fee_usd,
            'CurrentValue': current_value,
            'General amount': general_amount,
            'General amount USD': general_amount_usd
        })

        # Дополнительная строка для комиссии
        if amount_out_eth > 0 and fee_eth > 0:  # Только для исходящих транзакций
            processed.append({
                'Transaction Hash': tx_hash,  # Дублируем хэш для связности
                'Date': date,
                'From': from_address,
                'To': to_address,
                'Amount In (ETH)': 0,  # Входящая сумма отсутствует
                'Amount Out (ETH)': fee_eth,  # Указываем комиссию как расход
                'Fee (ETH)': 0,  # Поле Fee (ETH) числовое
                'Fee (USD)': 0,  # Поле Fee (USD) числовое
                'CurrentValue': 0,
                'General amount': 0,
                'General amount USD': 0
            })
        
    return processed



def process_eth_request(chat_id, wallet_address, start_timestamp, end_timestamp, period_str, message_id=None):
    try:
        eth = Etherscan(API_KEY)
        eth_usd_price = get_eth_usd_price()
        
        if eth_usd_price is None:
            raise Exception("Не удалось получить курс ETH/USD")
            
        txs = eth.get_normal_txs_by_address(
            address=wallet_address,
            startblock=0,
            endblock=99999999,
            sort='asc'
        )
        
        if start_timestamp:
            txs = [tx for tx in txs if int(tx['timeStamp']) >= start_timestamp]
        if end_timestamp:
            txs = [tx for tx in txs if int(tx['timeStamp']) <= end_timestamp]
            
        if not txs:
            if message_id:
                bot.edit_message_text("❌ ETH транзакции не найдены", chat_id, message_id)
            else:
                bot.send_message(chat_id, "❌ ETH транзакции не найдены")
            return
            
        processed_txs = process_transactions(txs, wallet_address, eth_usd_price)
        
        if not processed_txs:
            raise Exception("Ошибка при обработке транзакций")
            
        filename = f"{wallet_address}_ETH_{period_str.replace(' ', '_')}.csv"
        file_path = save_to_csv(processed_txs, filename)
        
        eth_balance = float(eth.get_eth_balance(wallet_address)) / 10**18
        usdt_balance = get_usdt_balance(eth, wallet_address)
        
        incoming_txs = sum(1 for tx in processed_txs if tx['Amount In (ETH)'] > 0)
        outgoing_txs = sum(1 for tx in processed_txs if tx['Amount Out (ETH)'] > 0)
        total_in = sum(tx['Amount In (ETH)'] for tx in processed_txs)
        total_out = sum(tx['Amount Out (ETH)'] for tx in processed_txs)
        total_fees = sum(tx['Fee (ETH)'] for tx in processed_txs)
        
        with open(file_path, 'rb') as file:
            if message_id:
                bot.edit_message_text(
                    f"✅ Отчет по ETH транзакциям готов",
                    chat_id,
                    message_id
                )
            bot.send_document(
                chat_id,
                file,
                caption=(
                    f"📊 Отчет по ETH транзакциям\n"
                    f"📅 Период: {period_str}\n\n"
                    f"📥 Входящие: {incoming_txs}\n"
                    f"📤 Исходящие: {outgoing_txs}\n"
                    f"💵 Получено: {total_in:.4f} ETH\n"
                    f"💸 Отправлено: {total_out:.4f} ETH\n"
                    f"🏷 Комиссии: {total_fees:.4f} ETH\n\n"
                    f"💰 Текущий баланс:\n"
                    f"🔷 ETH: {eth_balance:.4f}\n"
                    f"💵 USDT: {usdt_balance:.2f}"
                )
            )
            
            bot.send_message(
                ADMIN_ID,
                f"✅ Отчет ETH успешно отправлен\n"
                f"📅 Период: {period_str}"
            )
            
        os.remove(file_path)
        
    except Exception as e:
        error_msg = f"❌ Ошибка при формировании отчета: {str(e)}"
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id)
        else:
            bot.send_message(chat_id, error_msg)
        
        bot.send_message(
            ADMIN_ID,
            f"❌ Ошибка при формировании отчета ETH\n"
            f"📅 Период: {period_str}\n"
            f"⚠️ Ошибка: {str(e)}"
        )

def process_usdt_request(chat_id, wallet_address, start_timestamp, end_timestamp, period_str, message_id=None):
    try:
        eth = Etherscan(API_KEY)
        processed_txs = process_usdt_transactions(eth, wallet_address, start_timestamp, end_timestamp)
        
        if processed_txs:
            csv_transactions = [{
                'Date': tx['date'],
                'From': tx['from'],
                'To': tx['to'],
                'Transaction Hash': tx['hash'],
                'Amount (USDT)': tx['amount'] if tx['type'] == 'out' else 0,
                'Amount Received (USDT)': tx['amount'] if tx['type'] == 'in' else 0,
                'Fee (ETH)': tx['fee'],
                'Fee (USD)': tx['fee'] * get_eth_usd_price() if get_eth_usd_price() else 0
            } for tx in processed_txs]
            
            filename = f"{wallet_address}_USDT_{period_str.replace(' ', '_')}.csv"
            file_path = save_to_csv(csv_transactions, filename)
            
            eth_balance = float(eth.get_eth_balance(wallet_address)) / 10**18
            usdt_balance = get_usdt_balance(eth, wallet_address)
            
            incoming_txs = sum(1 for tx in processed_txs if tx['type'] == 'in')
            outgoing_txs = sum(1 for tx in processed_txs if tx['type'] == 'out')
            total_received = sum(tx['amount'] for tx in processed_txs if tx['type'] == 'in')
            total_sent = sum(tx['amount'] for tx in processed_txs if tx['type'] == 'out')
            
            with open(file_path, 'rb') as file:
                if message_id:
                    bot.edit_message_text(
                        f"✅ Отчет по USDT транзакциям готов",
                        chat_id,
                        message_id
                    )
                bot.send_document(
                    chat_id,
                    file,
                    caption=(
                        f"📊 Отчет по USDT транзакциям\n"
                        f"📅 Период: {period_str}\n\n"
                        f"📥 Входящие: {incoming_txs}\n"
                        f"📤 Исходящие: {outgoing_txs}\n"
                        f"💵 Получено: {total_received:.2f} USDT\n"
                        f"💸 Отправлено: {total_sent:.2f} USDT\n\n"
                        f"💰 Текущий баланс:\n"
                        f"🔷 ETH: {eth_balance:.4f}\n"
                        f"💵 USDT: {usdt_balance:.2f}"
                    )
                )
                
            os.remove(file_path)
        else:
            if message_id:
                bot.edit_message_text("❌ USDT транзакции не найдены", chat_id, message_id)
            else:
                bot.send_message(chat_id, "❌ USDT транзакции не найдены")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при формировании отчета: {str(e)}"
        if message_id:
            bot.edit_message_text(error_msg, chat_id, message_id)
        else:
            bot.send_message(chat_id, error_msg)

def signal_handler(signal, frame):
    """Обработчик сигнала Ctrl+C"""
    print('\n⚠️ Получен сигнал Ctrl+C, завершаю работу...')
    bot.stop_polling()
    sys.exit(0)

def main():
    try:
        # Регистрируем обработчик Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)
        
        # Регистрируем обработчики команд
        register_command_handlers(bot, API_KEY, db)
        
        # Затем регистрируем обработчик текстовых сообщений
        @bot.message_handler(func=lambda message: True)
        def handle_message(message):
            if message.text and message.text.startswith('/'):
                return
                
            chat_id = message.chat.id
            user_state = db.get_user_state(chat_id)
            
            if user_state == 'waiting_period':
                process_custom_period(bot, message, db)
                return
                
            text = message.text.strip() if message.text else ""
            
            try:
                try:
                    target_date = datetime.strptime(text, '%d.%m.%Y')
                    target_date = target_date.replace(hour=23, minute=59, second=59)
                    
                    wallet = db.get_user_wallet(chat_id)
                    if not wallet:
                        bot.reply_to(message, 
                            "❌ Сначала отправьте адрес Ethereum кошелька"
                        )
                        return
                        
                    if target_date > datetime.now():
                        bot.reply_to(message, "❌ Дата не может быть в будущем")
                        return
                        
                    status_message = bot.reply_to(
                        message, 
                        f"⏳ Получаю баланс для кошелька\n{wallet}\nна {text}..."
                    )
                    
                    try:
                        eth_balance, usdt_balance = get_wallet_balances_at_date(eth_client, wallet, target_date)
                        
                        if eth_balance is not None and usdt_balance is not None:
                            response = (
                                f"💰 Баланс кошелька на {text}\n"
                                f"{wallet}:\n\n"
                                f"🔷 ETH: {eth_balance:.4f}\n"
                                f"💵 USDT: {usdt_balance:.2f}"
                            )
                        else:
                            response = "❌ Ошибка при получении баланса"
                            
                        bot.edit_message_text(
                            text=response,
                            chat_id=chat_id,
                            message_id=status_message.message_id
                        )
                    except Exception as e:
                        bot.edit_message_text(
                            text=f"❌ Ошибка при получении баланса: {str(e)}",
                            chat_id=chat_id,
                            message_id=status_message.message_id
                        )
                    return
                    
                except ValueError:
                    if text.startswith('0x') and len(text) == 42:
                        db.update_user_wallet(chat_id, text)
                        markup = get_period_keyboard()
                        bot.send_message(
                            chat_id,
                            "💱 Выберите тип токена для анализа:",
                            reply_markup=markup
                        )
                        return
                    else:
                        bot.reply_to(message, "❌ Пожалуйста, отправьте валидный адрес Ethereum кошелька")
                        return
                
            except Exception as e:
                error_msg = f"❌ Ошибка при обработке сообщения: {str(e)}"
                bot.reply_to(message, error_msg)
        
        # И в конце регистрируем обработчик callback'ов
        @bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            handle_callback(bot, call, db)
            
        bot.infinity_polling(skip_pending=True)
        
    except Exception as e:
        print(f"Ошибка при запуске бота: {str(e)}")

if __name__ == '__main__':
    main()
