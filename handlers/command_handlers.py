import requests
from datetime import datetime
from etherscan import Etherscan
from usdt_handler import get_usdt_balance, process_usdt_transactions, get_usdt_price
from telebot import types

def get_wallet_balances(eth_client, wallet_address):
    try:
        eth_balance = float(eth_client.get_eth_balance(wallet_address)) / 10**18
        usdt_balance = get_usdt_balance(eth_client, wallet_address)
        return eth_balance, usdt_balance
    except Exception as e:
        print(f"Ошибка при получении балансов: {str(e)}")
        return None, None

def get_wallet_balances_at_date(eth_client, wallet_address, target_date):
    """Получает балансы ETH и USDT на указанную дату"""
    try:
        # 1. Получаем текущий баланс ETH
        current_eth_balance = float(eth_client.get_eth_balance(wallet_address)) / 10**18
        current_usdt_balance = get_usdt_balance(eth_client, wallet_address)
        
        # 2. Получаем все транзакции ETH и USDT
        eth_txs = eth_client.get_normal_txs_by_address(
            address=wallet_address,
            startblock=0,
            endblock=99999999,
            sort='asc'
        )
        
        usdt_txs = process_usdt_transactions(eth_client, wallet_address)
        
        if not eth_txs and not usdt_txs:
            return current_eth_balance, current_usdt_balance
        
        # 3. Фильтруем транзакции после указанной даты
        target_timestamp = int(target_date.timestamp())
        future_eth_txs = [tx for tx in eth_txs if int(tx['timeStamp']) > target_timestamp]
        future_usdt_txs = [tx for tx in usdt_txs if tx['timestamp'] > target_timestamp]
        
        # 4. Вычисляем баланс ETH на указанную дату
        eth_balance = current_eth_balance
        for tx in future_eth_txs:
            try:
                if tx['from'].lower() == wallet_address.lower():
                    value = float(tx['value']) / 10**18
                    gas_price = float(tx['gasPrice'])
                    gas_used = float(tx['gasUsed'])
                    fee = (gas_price * gas_used) / 10**18
                    
                    eth_balance += value  # Возвращаем отправленные ETH
                    eth_balance += fee    # Возвращаем комиссию
                    
                if tx['to'].lower() == wallet_address.lower():
                    value = float(tx['value']) / 10**18
                    eth_balance -= value  # Убираем полученные ETH
            except Exception:
                continue
                
        # 5. Вычисляем баланс USDT на указанную дату
        usdt_balance = current_usdt_balance
        for tx in future_usdt_txs:
            try:
                if tx['type'] == 'out':
                    usdt_balance += tx['amount']  # Возвращаем отправленные USDT
                else:
                    usdt_balance -= tx['amount']  # Убираем полученные USDT
            except Exception:
                continue
        
        return eth_balance, usdt_balance
        
    except Exception as e:
        print(f"Ошибка при получении балансов: {str(e)}")
        return None, None

def get_wallet_stats(eth_client, wallet_address):
    """Получает статистику транзакций кошелька"""
    try:
        # Получаем ETH транзакции
        eth_txs = eth_client.get_normal_txs_by_address(
            address=wallet_address,
            startblock=0,
            endblock=99999999,
            sort='asc'
        )
        
        # Получаем USDT транзакции
        usdt_txs = process_usdt_transactions(eth_client, wallet_address)
        
        # Статистика ETH
        eth_stats = {
            'total_in': 0,
            'total_out': 0,
            'total_fee': 0,
            'count_in': 0,
            'count_out': 0
        }
        
        for tx in eth_txs:
            try:
                value = float(tx['value']) / 10**18
                gas_price = float(tx['gasPrice'])
                gas_used = float(tx['gasUsed'])
                fee = (gas_price * gas_used) / 10**18
                
                if tx['from'].lower() == wallet_address.lower():
                    eth_stats['total_out'] += value
                    eth_stats['total_fee'] += fee
                    eth_stats['count_out'] += 1
                if tx['to'].lower() == wallet_address.lower():
                    eth_stats['total_in'] += value
                    eth_stats['count_in'] += 1
            except Exception:
                continue
                
        # Статистика USDT
        usdt_stats = {
            'total_in': 0,
            'total_out': 0,
            'count_in': 0,
            'count_out': 0
        }
        
        for tx in usdt_txs:
            try:
                if tx['type'] == 'out':
                    usdt_stats['total_out'] += tx['amount']
                    usdt_stats['count_out'] += 1
                else:
                    usdt_stats['total_in'] += tx['amount']
                    usdt_stats['count_in'] += 1
            except Exception:
                continue
                
        return eth_stats, usdt_stats
        
    except Exception as e:
        print(f"Ошибка при получении статистики: {str(e)}")
        return None, None

def setup_bot_commands(bot):
    bot.set_my_commands([
        ('start', 'Начать работу'),
        ('help', 'Показать справку'),
        ('balance', 'Текущий баланс кошелька'),
        ('balance_at', 'Баланс кошелька на дату'),
        ('stats', 'Статистика транзакций'),
        ('price', 'Текущий курс ETH и USDT')
    ])

def register_command_handlers(bot, api_key, db):
    eth_client = Etherscan(api_key)
    setup_bot_commands(bot)
    
    @bot.message_handler(commands=['start'])
    def start(message):
        chat_id = message.chat.id
        
        # Сбрасываем состояние пользователя при команде /start
        db.update_user_state(chat_id, None)
        
        bot.reply_to(
            message,
            "👋 Привет! Отправьте адрес Ethereum кошелька для анализа"
        )
    
    @bot.message_handler(commands=['help'])
    def help(message):
        bot.reply_to(message,
            "📚 Справка по использованию бота:\n\n"
            "1. Отправьте адрес Ethereum кошелька\n"
            "2. Выберите тип токена (ETH или USDT)\n"
            "3. Выберите период анализа\n"
            "4. Получите отчет в формате CSV\n\n"
            "Доступные команды:\n"
            "/start - Начать работу\n"
            "/help - Показать эту справку\n"
            "/balance - Текущий баланс кошелька\n"
            "/balance_at - Баланс кошелька на определенную дату\n"
            "/stats - Статистика транзакций\n"
            "/price - Текущий курс ETH и USDT"
        )

    @bot.message_handler(commands=['balance'])
    def balance(message):
        chat_id = message.chat.id
        
        # Получаем сохраненный адрес кошелька
        wallet = db.get_user_wallet(chat_id)
        if not wallet:
            bot.reply_to(message,
                "❌ Сначала отправьте адрес кошелька в чат"
            )
            return
            
        try:
            status_message = bot.reply_to(
                message, 
                f"⏳ Получаю баланс для кошелька\n{wallet}..."
            )
            
            eth_balance, usdt_balance = get_wallet_balances(eth_client, wallet)
            
            if eth_balance is not None and usdt_balance is not None:
                response = (
                    f"💰 Текущий баланс кошелька\n"
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

    @bot.message_handler(commands=['balance_at'])
    def balance_at(message):
        chat_id = message.chat.id
        
        # Проверяем наличие сохраненного адреса
        wallet = db.get_user_wallet(chat_id)
        if not wallet:
            bot.reply_to(message,
                "❌ Сначала отправьте адрес кошелька в чат"
            )
            return
        
        bot.reply_to(message,
            "📅 Чтобы узнать баланс на определенную дату, просто отправьте дату в чат в формате:\n"
            "ДД.ММ.ГГГГ\n\n"
            "Например: 25.12.2023\n\n"
            "💡 Не нужно каждый раз вызывать эту команду - просто отправьте дату в чат, и я покажу баланс последнего отправленного кошелька на указанную дату\n\n"
        )

    @bot.message_handler(commands=['price'])
    def price(message):
        try:
            status_message = bot.reply_to(
                message,
                "💱 Получаю текущий курс ETH...\n"
                "⏳ Пожалуйста, подождите..."
            )
            
            eth_price = get_eth_price()
            
            if eth_price is not None:
                response = f"💰 Текущий курс ETH: ${eth_price:,.2f}"
            else:
                response = "❌ Ошибка при получении курса"
                
            bot.edit_message_text(
                text=response,
                chat_id=message.chat.id,
                message_id=status_message.message_id
            )
            
        except Exception as e:
            bot.reply_to(
                message,
                f"❌ Ошибка при получении курса: {str(e)}"
            )

    @bot.message_handler(commands=['stats'])
    def stats(message):
        chat_id = message.chat.id
        wallet = db.get_user_wallet(chat_id)
        if not wallet:
            bot.reply_to(message,
                "❌ Сначала отправьте адрес кошелька в чат"
            )
            return
            
        try:
            status_message = bot.reply_to(
                message, 
                f"⏳ Получаю статистику для кошелька\n{wallet}..."
            )
            
            eth_stats, usdt_stats = get_wallet_stats(eth_client, wallet)
            
            if eth_stats is not None and usdt_stats is not None:
                response = (
                    f"📊 Статистика кошелька\n"
                    f"{wallet}\n\n"
                    f"🔷 ETH:\n"
                    f"Получено: {eth_stats['total_in']:.4f} ({eth_stats['count_in']} транзакций)\n"
                    f"Отправлено: {eth_stats['total_out']:.4f} ({eth_stats['count_out']} транзакций)\n"
                    f"Комиссии: {eth_stats['total_fee']:.4f}\n\n"
                    f"💵 USDT:\n"
                    f"Получено: {usdt_stats['total_in']:.2f} ({usdt_stats['count_in']} транзакций)\n"
                    f"Отправлено: {usdt_stats['total_out']:.2f} ({usdt_stats['count_out']} транзакций)"
                )
            else:
                response = "❌ Ошибка при получении статистики"
                
            bot.edit_message_text(
                text=response,
                chat_id=chat_id,
                message_id=status_message.message_id
            )
            
        except Exception as e:
            bot.edit_message_text(
                text=f"❌ Ошибка при получении статистики: {str(e)}",
                chat_id=chat_id,
                message_id=status_message.message_id
            ) 

def get_eth_price():
    """Получает текущий курс ETH в USD"""
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        return response.json()['ethereum']['usd']
    except Exception:
        return None 