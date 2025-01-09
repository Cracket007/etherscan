from datetime import datetime, timezone
import requests
import os

USDT_CONTRACT = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
USDT_DECIMALS = 6

def get_usdt_balance(eth, address):
    try:
        balance = eth.get_token_balance(
            contract_address=USDT_CONTRACT,
            address=address
        )
        return float(balance) / (10 ** USDT_DECIMALS)
    except Exception:
        return 0

def get_usdt_price():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd')
        return response.json()['tether']['usd']
    except Exception:
        return 1

def get_eth_price():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        return response.json()['ethereum']['usd']
    except Exception:
        return None

def process_usdt_transactions(eth, address, start_timestamp=None, end_timestamp=None):
    try:
        print("\n📡 Отправляем запрос в Etherscan API...")
        
        api_url = f"https://api.etherscan.io/api"
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': USDT_CONTRACT,
            'address': address,
            'startblock': '0',
            'endblock': '99999999',
            'sort': 'asc',
            'apikey': os.getenv('ETHERSCAN_API_KEY')
        }
        
        print(f"🌐 URL запроса: {api_url}")
        print(f"📋 Параметры: {params}")
        
        response = requests.get(api_url, params=params)
        data = response.json()
        
        print(f"✅ Статус ответа: {response.status_code}")
        print(f"📊 Результат: {data.get('message')}")
        
        if data.get('status') == '1' and data.get('result'):
            txs = data['result']
        else:
            print(f"API Error: {data}")
            return []
            
        if start_timestamp or end_timestamp:
            txs = [
                tx for tx in txs 
                if (not start_timestamp or int(tx['timeStamp']) >= start_timestamp) and
                   (not end_timestamp or int(tx['timeStamp']) <= end_timestamp)
            ]
            
        processed_txs = []
        for tx in txs:
            try:
                value = int(tx['value'], 16) if tx['value'].startswith('0x') else int(tx['value'])
                amount = float(value) / (10 ** USDT_DECIMALS)
                
                timestamp = int(tx['timeStamp'])
                date = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
                
                # Используем данные из самой транзакции вместо дополнительного запроса
                gas_price = int(tx['gasPrice'], 16) if tx['gasPrice'].startswith('0x') else int(tx['gasPrice'])
                gas_used = int(tx['gasUsed'], 16) if tx['gasUsed'].startswith('0x') else int(tx['gasUsed'])
                fee = float(gas_price * gas_used) / (10 ** 18)
                
                tx_data = {
                    'date': date,
                    'timestamp': timestamp,
                    'hash': tx['hash'],
                    'from': tx['from'],
                    'to': tx['to'],
                    'amount': amount,
                    'type': 'in' if tx['to'].lower() == address.lower() else 'out',
                    'fee': fee
                }
                processed_txs.append(tx_data)
                
            except Exception as e:
                print(f"Error processing tx: {str(e)}")
                continue
            
        return processed_txs
        
    except Exception as e:
        print(f"General error: {str(e)}")
        return [] 