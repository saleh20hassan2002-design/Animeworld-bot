import telebot
import os
import sqlite3
import difflib
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    # استخدام جدول anime_v2 الجديد
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime_v2 (
        link TEXT PRIMARY KEY, 
        names TEXT, 
        photo_url TEXT
    )''')
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

def has_permission(user_id, perm_column):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM admins_v2 WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

def get_permissions_keyboard(admin_id):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins_v2 WHERE user_id = ?", (admin_id,))
    admin = cursor.fetchone()
    conn.close()
    if not admin: return None
    perms = {'المشرفين': ('can_manage_admins', admin[2]), 'إضافة أنمي': ('can_add_anime', admin[3]), 'حذف أنمي': ('can_delete_anime', admin[4]), 'نسخ احتياطي': ('can_backup', admin[5]), 'استرداد': ('can_restore', admin[6]), 'القائمة': ('can_list', admin[7])}
    markup = types.InlineKeyboardMarkup(row_width=1)
    for text, (col, val) in perms.items():
        icon = "✅" if val == 1 else "❌"
        markup.add(types.InlineKeyboardButton(f"{text} {icon}", callback_data=f"perm:{admin_id}:{col}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    return markup

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    if has_permission(user_id, 'can_add_anime'): buttons.append(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"))
    if has_permission(user_id, 'can_delete_anime'): buttons.append(types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime"))
    if has_permission(user_id, 'can_manage_admins'): buttons.append(types.InlineKeyboardButton("🛡 المشرفين", callback_data="admin_panel"))
    if has_permission(user_id, 'can_backup'): buttons.append(types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="backup"))
    if has_permission(user_id, 'can_restore'): buttons.append(types.InlineKeyboardButton("🔄 استرداد", callback_data="restore"))
    if has_permission(user_id, 'can_list'): buttons.append(types.InlineKeyboardButton("📋 القائمة", callback_data="list_anime"))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons): markup.add(buttons[i], buttons[i+1])
        else: markup.add(buttons[i])
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "مرحباً! اختر إجراءً:", reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "back_to_main":
        bot.edit_message_text("القائمة الرئيسية:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(user_id))
    elif call.data == "admin_panel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_prompt"), types.InlineKeyboardButton("➖ حذف مشرف", callback_data="del_admin_prompt"), types.InlineKeyboardButton("⚙️ صلاحيات المشرفين", callback_data="edit_perms_list"), types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text("🛡 لوحة تحكم المشرفين:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "add_admin_prompt":
        bot.send_message(call.message.chat.id, "أرسل ID واسم المشرف (مثال: 12345,الاسم):")
        bot.register_next_step_handler(call.message, process_add_admin)
    elif call.data.startswith("perm:"):
        _, target_id, perm_col = call.data.split(":")
        target_id = int(target_id)
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute(f"SELECT {perm_col} FROM admins_v2 WHERE user_id = ?", (target_id,))
        new_val = 0 if cursor.fetchone()[0] == 1 else 1
        cursor.execute(f"UPDATE admins_v2 SET {perm_col} = ? WHERE user_id = ?", (new_val, target_id))
        conn.commit(); conn.close()
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_permissions_keyboard(target_id))
    elif call.data == "add_new":
        bot.send_message(call.message.chat.id, "أرسل رابط الأنمي:")
        bot.register_next_step_handler(call.message, get_names_for_link)
    elif call.data == "restore":
        bot.send_message(call.message.chat.id, "أرسل ملف قاعدة البيانات (anime.db) الآن:")
        bot.register_next_step_handler(call.message, process_restore)
    # [بقية الأزرار الأساسية...]

def get_names_for_link(message):
    link = message.text
    bot.send_message(message.chat.id, "أرسل رابط الصورة:")
    bot.register_next_step_handler(message, lambda m: get_names_for_anime(m, link))

def get_names_for_anime(message, link):
    photo_url = message.text
    bot.send_message(message.chat.id, "أرسل الأسماء:")
    bot.register_next_step_handler(message, lambda m: save_anime_data(m, link, photo_url))

def save_anime_data(message, link, photo_url):
    names = message.text.replace(',', '\n')
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO anime_v2 (link, names, photo_url) VALUES (?, ?, ?)", (link, names, photo_url))
    conn.commit(); conn.close()
    bot.reply_to(message, "✅ تم الحفظ بنجاح!")

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def search_anime(message):
    query = message.text.lower().strip()
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT link, names, photo_url FROM anime_v2")
    all_anime = cursor.fetchall()
    conn.close()
    for link, names, photo_url in all_anime:
        if any(query in n.strip().lower() for n in names.split('\n')):
            try:
                if photo_url and photo_url.startswith('http'):
                    bot.send_photo(message.chat.id, photo_url, caption=f"📺 {names.split('\n')[0]}\n🔗 {link}")
                else:
                    bot.reply_to(message, f"📺 {names.split('\n')[0]}\n🔗 {link}")
            except:
                bot.reply_to(message, f"📺 {names.split('\n')[0]}\n🔗 {link}")
            return

def process_restore(message):
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open('anime.db', 'wb') as new_file: new_file.write(downloaded_file)
        bot.reply_to(message, "✅ تم الاسترداد!")
    else: bot.reply_to(message, "⚠️ خطأ: يجب إرسال ملف .db")

def process_add_admin(message):
    try:
        parts = message.text.split(',')
        new_id = int(parts[0].strip())
        name = parts[1].strip()
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO admins_v2 (user_id, name) VALUES (?, ?)", (new_id, name))
        conn.commit(); conn.close()
        bot.reply_to(message, f"✅ تم إضافة المشرف: {name}")
    except: bot.reply_to(message, "⚠️ خطأ في الصيغة.")

if __name__ == '__main__':
    bot.infinity_polling()
