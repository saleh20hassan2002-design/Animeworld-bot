import telebot
import os
import sqlite3
import difflib
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

# تهيئة قاعدة البيانات
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
        cursor.execute('''INSERT INTO admins_v2 
            (user_id, name, can_manage_admins, can_add_anime, can_delete_anime, can_backup, can_restore, can_list) 
            VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)''', (OWNER_ID,))
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

# لوحة صلاحيات المشرف
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

# القائمة الرئيسية
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if has_permission(user_id, 'can_add_anime'):
        markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"), types.InlineKeyboardButton("✏️ تعديل أنمي", callback_data="edit_anime"))
    buttons = []
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
    bot.clear_step_handler(message)
    bot.send_message(message.chat.id, "مرحباً بك! اختر إجراءً:", reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    bot.clear_step_handler(message)
    
    # القائمة الرئيسية
    if call.data == "back_to_main":
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))
    
    # لوحة المشرفين
    elif call.data == "admin_panel":
        if not has_permission(user_id, 'can_manage_admins'): return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_prompt"), 
                   types.InlineKeyboardButton("➖ حذف مشرف", callback_data="del_admin_prompt"), 
                   types.InlineKeyboardButton("⚙️ صلاحيات المشرفين", callback_data="edit_perms_list"), 
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_text("🛡 لوحة تحكم المشرفين:", message.chat.id, message.message_id, reply_markup=markup)

    # وظائف أخرى للأزرار
    elif call.data == "add_new":
        bot.send_message(message.chat.id, "أرسل رابط الأنمي:")
        bot.register_next_step_handler(message, get_names_for_link)
    
    elif call.data == "delete_anime":
        bot.send_message(message.chat.id, "أرسل رابط الأنمي للحذف:")
        bot.register_next_step_handler(message, delete_anime_db)
        
    elif call.data == "backup":
        try:
            with open('anime.db', 'rb') as f: bot.send_document(message.chat.id, f)
        except: bot.send_message(message.chat.id, "خطأ في النسخ!")

    elif call.data == "restore":
        bot.send_message(message.chat.id, "أرسل ملف القاعدة (anime.db):")
        bot.register_next_step_handler(message, process_restore)
        
    elif call.data == "list_anime":
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("SELECT names FROM anime")
        animes = [a[0].split('\n')[0] for a in cursor.fetchall()]
        conn.close()
        text = "📋 القائمة:\n" + "\n".join(animes) if animes else "فارغة."
        bot.send_message(message.chat.id, text)

    # معالجة إضافية (إضافة/حذف مشرف/صلاحيات) كما في الكود السابق...
    # [ملاحظة: ضع باقي منطق الأزرار المشابه للرد السابق هنا]

def delete_anime_db(message):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anime WHERE link = ?", (message.text,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🗑 تم الحذف.")

if __name__ == '__main__':
    bot.infinity_polling()
