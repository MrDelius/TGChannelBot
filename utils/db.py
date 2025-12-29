import sqlite3
import os
from config import DB_PATH


class Database:
    def __init__(self, db_name=DB_PATH):
        # Создаем папку для базы, если её нет
        if os.path.dirname(db_name):
            os.makedirs(os.path.dirname(db_name), exist_ok=True)

        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        # Включаем поддержку внешних ключей (Foreign Keys)
        # Это критически важно для корректной работы CASCADE DELETE
        self.cursor.execute("PRAGMA foreign_keys = ON;")
        self.create_table()

    def create_table(self):
        """Создание структуры базы данных (Many-to-Many)"""

        # 1. Таблица каналов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                title TEXT
            )
        """)

        # 2. Таблица пользователей (админов и владельцев)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)

        # 3. Промежуточная таблица разрешений (Permissions)
        # Связывает пользователей и каналы + хранит роль (Владелец/Админ)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                user_id INTEGER,
                channel_id TEXT,
                is_owner INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, channel_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()

    def sync_channel_admins(self, channel_id, title, admins_list):
        """
        Полная синхронизация прав доступа для конкретного канала.
        admins_list: список словарей {'id': int, 'username': str, 'is_owner': bool}
        """
        # 1. Обновляем информацию о канале
        self.cursor.execute(
            "INSERT OR REPLACE INTO channels (channel_id, title) VALUES (?, ?)",
            (str(channel_id), title)
        )

        # 2. Очищаем старые связи ТОЛЬКО для этого канала
        self.cursor.execute("DELETE FROM permissions WHERE channel_id = ?", (str(channel_id),))

        # 3. Добавляем админов и создаем новые связи
        for admin in admins_list:
            uid = admin['id']
            username = admin.get('username', 'Unknown')
            is_owner = 1 if admin['is_owner'] else 0

            # Используем UPSERT (INSERT ... ON CONFLICT).
            # Это предотвращает удаление юзера при обновлении (REPLACE = DELETE + INSERT).
            # Благодаря этому ON DELETE CASCADE для этого юзера НЕ срабатывает,
            # и его связи с ДРУГИМИ каналами остаются целыми.
            self.cursor.execute("""
                INSERT INTO users (user_id, username) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
            """, (uid, username))

            # Создаем связь между пользователем и текущим каналом
            self.cursor.execute(
                "INSERT INTO permissions (user_id, channel_id, is_owner) VALUES (?, ?, ?)",
                (uid, str(channel_id), is_owner)
            )

        self.conn.commit()

    def get_user_channels(self, user_id, role="admin"):
        """
        Получение списка каналов пользователя по его роли.
        role="owner" -> каналы, где пользователь создатель (is_owner=1)
        role="admin" -> каналы, где пользователь наемный админ (is_owner=0)
        """
        query = """
            SELECT c.title, c.channel_id 
            FROM channels c
            JOIN permissions p ON c.channel_id = p.channel_id
            WHERE p.user_id = ?
        """

        if role == "owner":
            query += " AND p.is_owner = 1"
        else:
            query += " AND p.is_owner = 0"

        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchall()

    def is_user_owner(self, user_id, channel_id):
        """Проверка, является ли пользователь владельцем канала в БД"""
        self.cursor.execute(
            "SELECT is_owner FROM permissions WHERE user_id = ? AND channel_id = ?",
            (user_id, str(channel_id))
        )
        res = self.cursor.fetchone()
        return bool(res[0]) if res else False

    def remove_user_permission(self, user_id, channel_id):
        """Лишение пользователя прав на конкретный канал в боте"""
        self.cursor.execute(
            "DELETE FROM permissions WHERE user_id = ? AND channel_id = ?",
            (user_id, str(channel_id))
        )
        self.conn.commit()

    def delete_channel(self, channel_id):
        """Полное удаление канала и всех его связей из базы"""
        self.cursor.execute("DELETE FROM channels WHERE channel_id = ?", (str(channel_id),))
        self.conn.commit()

    def get_channel_title(self, channel_id):
        """Получение названия канала по его ID"""
        self.cursor.execute("SELECT title FROM channels WHERE channel_id = ?", (str(channel_id),))
        result = self.cursor.fetchone()
        return result[0] if result else "Неизвестный канал"

    def get_channel_owner_id(self, channel_id):
        """Возвращает user_id владельца канала (где is_owner=1)"""
        self.cursor.execute(
            "SELECT user_id FROM permissions WHERE channel_id = ? AND is_owner = 1",
            (str(channel_id),)
        )
        res = self.cursor.fetchone()
        return res[0] if res else None


db = Database()