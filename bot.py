import telebot
import os
import sqlite3
import difflib
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

# =================================================================
#                         قاعدة البيانات
# =================================================================
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
    cursor.execute("SELECT * FROM admins_v2 WHERE user_id = ?", (OWNER_ID,))
    if not cursor.fetchone():
        cursor.execute('''INSERT INTO admins_v2 VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)''', (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# =================================================================
#                         دوال الصلاحيات
# =================================================================
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
    perms = {'إدارة المشرفين': ('can_manage_admins', admin[2]), 'إضافة أنمي': ('can_add_anime', admin[3]), 
             'حذف أنمي': ('can_delete_anime', admin[4]), 'نسخ احتياطي': ('can_backup', admin[5]), 
             'استرداد': ('can_restore', admin[6]), 'عرض القائمة': ('can_list', admin[7])}
    markup = types.InlineKeyboardMarkup(row_width=1)
    for text, (col, val) in perms.items():
        icon = "✅" if val == 1 else "❌"
        markup.add(types.InlineKeyboardButton(f"{text} {icon}", callback_data=f"perm:{admin_id}:{col}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    return markup

# =================================================================
#                         القوائم الرئيسية
# =================================================================
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if has_permission(user_id, 'can_add_anime'):
        markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"), types.InlineKeyboardButton("✏️ تعديل أنمي", callback_data="edit_anime"))
    buttons = []
    if has_permission(user_id, 'can_delete_anime'): buttons.append(types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime"))
    if has_permission(user_id, 'can_manage_admins'): buttons.append(types.InlineKeyboardButton("🛡 لوحة المشرفين", callback_data="admin_panel"))
    if has_permission(user_id, 'can_backup'): buttons.append(types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="backup"))
    if has_permission(user_id, 'can_restore'): buttons.append(types.InlineKeyboardButton("🔄 استرداد", callback_data="restore"))
    if has_permission(user_id, 'can_list'): buttons.append(types.InlineKeyboardButton("📋 القائمة", callback_data="list_anime"))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons): markup.add(buttons[i], buttons[i+1])
        else: markup.add(buttons[i])
    return markup

# =================================================================
#                         معالج الأوامر
# =================================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "أهلاً بك في بوت إدارة الأنمي، اختر من القائمة:", reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    bot.answer_callback_query(call.id)
    
    # القائمة الرئيسية
    if call.data == "back_to_main":
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))
        
    # إدارة المشرفين
    elif call.data == "admin_panel":
        if not has_permission(user_id, 'can_manage_admins'): return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_adm_prompt"),
                   types.InlineKeyboardButton("➖ حذف مشرف", callback_data="del_adm_prompt"),
                   types.InlineKeyboardButton("⚙️ تعديل الصلاحيات", callback_data="perms_menu"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text("🛡 لوحة إدارة المشرفين:", message.chat.id, message.message_id, reply_markup=markup)
        
    elif call.data == "add_adm_prompt":
        bot.send_message(message.chat.id, "أرسل ID المشرف الجديد:")
        bot.register_next_step_handler(message, add_admin)
        
    elif call.data == "del_adm_prompt":
        bot.send_message(message.chat.id, "أرسل ID المشرف لحذفه:")
        bot.register_next_step_handler(message, del_admin)

    elif call.data == "perms_menu":
        conn = sqlite3.connect('anime.db')
        admins = conn.execute("SELECT user_id, name FROM admins_v2 WHERE user_id != ?", (OWNER_ID,)).fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup()
        for adm in admins: markup.add(types.InlineKeyboardButton(f"👤 {adm[1]} ({adm[0]})", callback_data=f"edit_perm_user:{adm[0]}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        bot.edit_message_text("اختر المشرف:", message.chat.id, message.message_id, reply_markup=markup)
        
    elif call.data.startswith("edit_perm_user:"):
        uid = call.data.split(":")[1]
        bot.edit_message_text(f"تعديل صلاحيات {uid}:", message.chat.id, message.message_id, reply_markup=get_permissions_keyboard(uid))
        
    elif call.data.startswith("perm:"):
        _, uid, col = call.data.split(":")
        conn = sqlite3.connect('anime.db')
        val = conn.execute(f"SELECT {col} FROM admins_v2 WHERE user_id = ?", (uid,)).fetchone()[0]
        conn.execute(f"UPDATE admins_v2 SET {col} = ? WHERE user_id = ?", (0 if val == 1 else 1, uid))
        conn.commit()
        conn.close()
        bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=get_permissions_keyboard(uid))

    # العمليات الأخرى (إضافة، حذف، إلخ...)
    elif call.data == "add_new":
        bot.send_message(message.chat.id, "أرسل الرابط:")
        bot.register_next_step_handler(message, lambda m: get_names(m))
        
    elif call.data == "delete_anime":
        bot.send_message(message.chat.id, "أرسل الرابط للحذف:")
        bot.register_next_step_handler(message, delete_anime)
        
    elif call.data == "backup":
        with open('anime.db', 'rb') as f: bot.send_document(message.chat.id, f)
        
    elif call.data == "restore":
        bot.send_message(message.chat.id, "أرسل ملف القاعدة:")
        bot.register_next_step_handler(message, process_restore)

    elif call.data == "list_anime":
        conn = sqlite3.connect('anime.db')
        data = conn.execute("SELECT names FROM anime").fetchall()
        conn.close()
        text = "\n".join([d[0] for d in data])
        bot.send_message(message.chat.id, f"📋 القائمة:\n{text}")

# =================================================================
#                         بقية الدوال التنفيذية
# =================================================================
def add_admin(m):
    try:
        conn = sqlite3.connect('anime.db')
        conn.execute("INSERT OR REPLACE INTO admins_v2 (user_id, name) VALUES (?, 'مشرف')", (int(m.text),))
        conn.commit()
        conn.close()
        bot.reply_to(m, "✅ تم الإضافة.")
    except: bot.reply_to(m, "⚠️ خطأ في الـ ID.")

def del_admin(m):
    conn = sqlite3.connect('anime.db')
    conn.execute("DELETE FROM admins_v2 WHERE user_id = ? AND user_id != ?", (int(m.text), OWNER_ID))
    conn.commit()
    conn.close()
    bot.reply_to(m, "🗑 تم الحذف.")

def get_names(m):
    link = m.text
    msg = bot.send_message(m.chat.id, "أرسل الأسماء:")
    bot.register_next_step_handler(msg, lambda m2: save_anime(m2, link))

def save_anime(m, link):
    conn = sqlite3.connect('anime.db')
    conn.execute("INSERT OR REPLACE INTO anime (link, names) VALUES (?, ?)", (link, m.text))
    conn.commit()
    conn.close()
    bot.reply_to(m, "✅ تم حفظ الأنمي.")

def delete_anime(m):
    conn = sqlite3.connect('anime.db')
    conn.execute("DELETE FROM anime WHERE link = ?", (m.text,))
    conn.commit()
    conn.close()
    bot.reply_to(m, "🗑 تم حذف الأنمي.")

def process_restore(m):
    if m.document:
        f_info = bot.get_file(m.document.file_id)
        with open('anime.db', 'wb') as f: f.write(bot.download_file(f_info.file_path))
        bot.reply_to(m, "✅ تم الاسترداد.")

# =================================================================
#                         نقطة التشغيل
# =================================================================
if __name__ == '__main__':
    bot.remove_webhook()
    print("البوت يعمل الآن بكامل الميزات...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
