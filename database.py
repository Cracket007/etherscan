import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        """Инициализация подключения к базе данных"""
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.create_tables()
        
    def create_tables(self):
        """Создает необходимые таблицы в базе данных"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                wallet TEXT,
                token_type TEXT,
                state TEXT
            )
        ''')
        self.conn.commit()
        
    def update_user_wallet(self, chat_id: int, wallet: str):
        """Сохраняет адрес кошелька пользователя"""
        wallet = wallet.strip().lower()  # Нормализация адреса
        self.conn.execute('''
            INSERT OR REPLACE INTO users (chat_id, wallet)
            VALUES (?, ?)
        ''', (chat_id, wallet))
        self.conn.commit()
        
    def get_user_wallet(self, chat_id: int) -> str:
        """Получает сохраненный адрес кошелька"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT wallet FROM users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        return result[0] if result else None 
        
    def update_user_token(self, chat_id: int, token: str):
        """Сохраняет выбранный тип токена"""
        self.conn.execute('''
            UPDATE users 
            SET token_type = ?
            WHERE chat_id = ?
        ''', (token, chat_id))
        self.conn.commit()
        
    def get_user_token(self, chat_id: int) -> str:
        """Получает сохраненный тип токена"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT token_type FROM users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        return result[0] if result else None
        
    def update_user_state(self, chat_id: int, state: str):
        """Сохраняет состояние пользователя"""
        self.conn.execute('''
            UPDATE users 
            SET state = ?
            WHERE chat_id = ?
        ''', (state, chat_id))
        self.conn.commit()
        
    def get_user_state(self, chat_id: int) -> str:
        """Получает состояние пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT state FROM users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        return result[0] if result else None 

    def __del__(self):
        """Закрытие соединения при удалении объекта"""
        self.conn.close() 