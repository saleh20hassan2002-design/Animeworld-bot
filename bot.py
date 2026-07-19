import telebot
import os
import sqlite3
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    # إنشاء الجدولين لضمان التوافق مع أي نسخة سابقة
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime_v2 (link TEXT PRIMARY KEY, names TEXT, photo_url TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT, photo_url TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins_v2 (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        can_manage_admins INTEGER DEFAULT 0,
        can_add_anime INTEGER DEFAULT 0,
        can_delete_anime INTEGER DEFAULT 0,
        can_backup INTEGER DEFAULT 0,
        can_restore INTEGER DEFAULT 0,
        can_list INTEGER DEFAULT 0
    )''')
    cursor.execute('''INSERT OR IGNORE INTO admins_v2 
        (user_id, name, can_manage_admins, can_add_anime, can_delete_anime, can_backup, can_restore, can_list) 
        VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)''', (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# بقية دوال الصلاحيات والقوائم كما هي...
def has_permission(user_id, perm_column):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM admins_v2 WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def search_anime(message):
    query = message.text.lower().strip()
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    
    # البحث في الجدولين anime_v2 و anime
    cursor.execute("SELECT link, names, photo_url FROM anime_v2")
    data_v2 = cursor.fetchall()
    cursor.execute("SELECT link, names, photo_url FROM anime")
    data_old = cursor.fetchall()
    
    all_anime = data_v2 + data_old
    conn.close()
    
    for link, names, photo_url in all_anime:
        if names and any(query in n.strip().lower() for n in names.split('\n')):
            try:
                if photo_url and photo_url.startswith('http'):
                    bot.send_photo(message.chat.id, photo_url, caption=f"📺 {names.split('\n')[0]}\n🔗 {link}")
                else:
                    bot.reply_to(message, f"📺 {names.split('\n')[0]}\n🔗 {link}")
            except Exception as e:
                bot.reply_to(message, f"📺 {names.split('\n')[0]}\n🔗 {link}")
            return

def save_anime_data(message, link, photo_url):
    names = message.text.replace(',', '\n')
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    # الحفظ في الجدول الجديد دائماً
    cursor.execute("INSERT OR REPLACE INTO anime_v2 (link, names, photo_url) VALUES (?, ?, ?)", (link, names, photo_url))
    conn.commit(); conn.close()
    bot.reply_to(message, "✅ تم الحفظ بنجاح في الجدول الجديد!")

# دالة get_names_for_anime و get_names_for_link و process_restore و process_add_admin 
# تبقى كما كانت في كودك السابق.

if __name__ == '__main__':
    bot.infinity_polling()
