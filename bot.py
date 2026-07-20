import telebot
import os
import sqlite3
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

# تهيئة القاعدة
def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins_v2 (
        user_id INTEGER PRIMARY KEY, name TEXT, can_manage_admins INTEGER DEFAULT 0,
        can_add_anime INTEGER DEFAULT 0, can_delete_anime INTEGER DEFAULT 0,
        can_backup INTEGER DEFAULT 0, can_restore INTEGER DEFAULT 0, can_list INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO admins_v2 (user_id, name, can_manage_admins, can_add_anime, can_delete_anime, can_backup, can_restore, can_list) VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)", (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# فحص الصلاحيات
def has_permission(user_id, perm_column):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM admins_v2 WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

# القائمة الرئيسية
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if has_permission(user_id, 'can_add_anime'):
        markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"))
    if has_permission(user_id, 'can_delete_anime'):
        markup.add(types.InlineKeyboardButton("➖ حذف أنمي (بالرابط)", callback_data="delete_anime"))
    if has_permission(user_id, 'can_manage_admins'):
        markup.add(types.InlineKeyboardButton("🛡 المشرفين والصلاحيات", callback_data="admin_panel"))
    markup.add(types.InlineKeyboardButton("🔄 استرداد/نسخ", callback_data="backup_restore"))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    bot.answer_callback_query(call.id)
    
    if call.data == "admin_panel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_adm"),
                   types.InlineKeyboardButton("➖ حذف مشرف (بالـ ID)", callback_data="del_adm"),
                   types.InlineKeyboardButton("⚙️ تعديل صلاحيات", callback_data="perms_menu"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back"))
        bot.edit_message_text("🛡 لوحة المشرفين:", message.chat.id, message.message_id, reply_markup=markup)

    elif call.data == "add_adm":
        bot.send_message(message.chat.id, "أرسل ID المشرف لإضافته:")
        bot.register_next_step_handler(message, lambda m: add_admin_db(m))
        
    elif call.data == "del_adm":
        bot.send_message(message.chat.id, "أرسل ID المشرف لحذفه:")
        bot.register_next_step_handler(message, lambda m: del_admin_db(m))
        
    elif call.data == "delete_anime":
        bot.send_message(message.chat.id, "أرسل رابط الأنمي المراد حذفه:")
        bot.register_next_step_handler(message, lambda m: del_anime_db(m))

    elif call.data == "back":
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))

# دوال العمليات
def add_admin_db(m):
    try:
        conn = sqlite3.connect('anime.db')
        conn.execute("INSERT OR REPLACE INTO admins_v2 (user_id, name) VALUES (?, 'مشرف')", (int(m.text),))
        conn.commit()
        conn.close()
        bot.reply_to(m, "✅ تم إضافة المشرف.")
    except: bot.reply_to(m, "⚠️ خطأ في الـ ID.")

def del_admin_db(m):
    try:
        conn = sqlite3.connect('anime.db')
        conn.execute("DELETE FROM admins_v2 WHERE user_id = ? AND user_id != ?", (int(m.text), OWNER_ID))
        conn.commit()
        conn.close()
        bot.reply_to(m, "🗑 تم حذف المشرف.")
    except: bot.reply_to(m, "⚠️ خطأ.")

def del_anime_db(m):
    conn = sqlite3.connect('anime.db')
    conn.execute("DELETE FROM anime WHERE link = ?", (m.text,))
    conn.commit()
    conn.close()
    bot.reply_to(m, "🗑 تم حذف الأنمي.")

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "أهلاً بك:", reply_markup=main_menu(m.from_user.id))

if __name__ == '__main__':
    bot.infinity_polling()
