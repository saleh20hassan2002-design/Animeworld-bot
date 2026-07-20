import telebot
import os
import sqlite3
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

# ==================== إعداد قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT)''')
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
    cursor.execute("INSERT OR IGNORE INTO admins_v2 (user_id, name, can_manage_admins, can_add_anime, can_delete_anime, can_backup, can_restore, can_list) VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)", (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# ==================== الدوال المساعدة ====================
def has_permission(user_id, perm_column):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM admins_v2 WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if has_permission(user_id, 'can_add_anime'):
        markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"), 
                   types.InlineKeyboardButton("✏️ تعديل أنمي", callback_data="edit_anime"))
    buttons = []
    if has_permission(user_id, 'can_delete_anime'): buttons.append(types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime"))
    if has_permission(user_id, 'can_manage_admins'): buttons.append(types.InlineKeyboardButton("🛡 المشرفين", callback_data="admin_panel"))
    if has_permission(user_id, 'can_backup'): buttons.append(types.InlineKeyboardButton("💾 نسخة", callback_data="backup"))
    if has_permission(user_id, 'can_restore'): buttons.append(types.InlineKeyboardButton("🔄 استرداد", callback_data="restore"))
    if has_permission(user_id, 'can_list'): buttons.append(types.InlineKeyboardButton("📋 القائمة", callback_data="list_anime"))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons): markup.add(buttons[i], buttons[i+1])
        else: markup.add(buttons[i])
    return markup

# ==================== معالج الأزرار ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(message.chat.id)

    if call.data == "back_to_main":
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))
    
    # قسم المشرفين (تم حل مشكلة التعليق باستخدام الـ ID فقط)
    elif call.data == "admin_panel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_prompt"),
                   types.InlineKeyboardButton("➖ حذف مشرف", callback_data="del_admin_prompt"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text("🛡 لوحة الإدارة:", message.chat.id, message.message_id, reply_markup=markup)

    elif call.data == "add_admin_prompt":
        bot.send_message(message.chat.id, "أرسل ID المشرف الجديد:")
        bot.register_next_step_handler(message, lambda m: process_admin_add(m))

    elif call.data == "del_admin_prompt":
        conn = sqlite3.connect('anime.db')
        admins = conn.execute("SELECT user_id FROM admins_v2 WHERE user_id != ?", (OWNER_ID,)).fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup()
        for adm in admins:
            markup.add(types.InlineKeyboardButton(f"🗑 حذف: {adm[0]}", callback_data=f"del_u:{adm[0]}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        bot.edit_message_text("اختر المشرف:", message.chat.id, message.message_id, reply_markup=markup)

    elif call.data.startswith("del_u:"):
        uid = call.data.split(":")[1]
        conn = sqlite3.connect('anime.db')
        conn.execute("DELETE FROM admins_v2 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        bot.edit_message_text("✅ تم الحذف.", message.chat.id, message.message_id, reply_markup=main_menu(user_id))

    # قسم الأنمي
    elif call.data == "add_new":
        bot.send_message(message.chat.id, "أرسل الرابط:")
        bot.register_next_step_handler(message, lambda m: get_names(m))

    elif call.data == "delete_anime":
        bot.send_message(message.chat.id, "أرسل الرابط للحذف:")
        bot.register_next_step_handler(message, lambda m: delete_anime(m))

    elif call.data == "backup":
        try:
            with open('anime.db', 'rb') as f: bot.send_document(message.chat.id, f)
        except: pass

    elif call.data == "restore":
        bot.send_message(message.chat.id, "أرسل الملف:")
        bot.register_next_step_handler(message, lambda m: process_restore(m))

    elif call.data == "list_anime":
        conn = sqlite3.connect('anime.db')
        data = conn.execute("SELECT names FROM anime").fetchall()
        conn.close()
        bot.send_message(message.chat.id, "📋 القائمة:\n" + "\n".join([d[0].split('\n')[0] for d in data]))

# ==================== دوال التنفيذ ====================
def process_admin_add(m):
    try:
        conn = sqlite3.connect('anime.db')
        conn.execute("INSERT OR REPLACE INTO admins_v2 (user_id, name) VALUES (?, 'مشرف')", (int(m.text),))
        conn.commit()
        conn.close()
        bot.reply_to(m, "✅ تم!")
    except: bot.reply_to(m, "⚠️ خطأ!")

def get_names(m):
    link = m.text
    bot.send_message(m.chat.id, "أرسل الأسماء (سطر لكل اسم):")
    bot.register_next_step_handler(m, lambda m2: save_anime(m2, link))

def save_anime(m, link):
    conn = sqlite3.connect('anime.db')
    conn.execute("INSERT OR REPLACE INTO anime (link, names) VALUES (?, ?)", (link, m.text))
    conn.commit()
    conn.close()
    bot.reply_to(m, "✅ تم الحفظ!")

def delete_anime(m):
    conn = sqlite3.connect('anime.db')
    conn.execute("DELETE FROM anime WHERE link = ?", (m.text,))
    conn.commit()
    conn.close()
    bot.reply_to(m, "🗑 تم!")

def process_restore(m):
    if m.document:
        f_info = bot.get_file(m.document.file_id)
        with open('anime.db', 'wb') as f: f.write(bot.download_file(f_info.file_path))
        bot.reply_to(m, "✅ تم استرداد قاعدة البيانات!")

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "مرحباً:", reply_markup=main_menu(m.from_user.id))

if __name__ == '__main__':
    bot.infinity_polling()
