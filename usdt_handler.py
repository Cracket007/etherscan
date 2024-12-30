from datetime import datetime, timezone
import requests

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

def process_usdt_transactions(eth, address, start_timestamp=None, end_timestamp=None):
    try:
        txs = eth.get_token_transfer_events(
            contract_address=USDT_CONTRACT,
            address=address,
            startblock=0,
            endblock=99999999,
            sort='asc'
        )
        
        if start_timestamp or end_timestamp:
            txs = [
                tx for tx in txs 
                if (not start_timestamp or int(tx['timeStamp']) >= start_timestamp) and
                   (not end_timestamp or int(tx['timeStamp']) <= end_timestamp)
            ]
            
        processed_txs = []
        for tx in txs:
            try:
                value = int(tx['value'])
                amount = float(value) / (10 ** USDT_DECIMALS)
                
                timestamp = int(tx['timeStamp'])
                date = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')
                
                tx_details = eth.get_proxy_transaction_by_hash(tx['hash'])
                
                gas_price = int(tx_details.get('gasPrice', '0'))
                gas_used = int(tx_details.get('gas', '0'))
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
                
            except Exception:
                continue
            
        return processed_txs
        
    except Exception:
        return [] 