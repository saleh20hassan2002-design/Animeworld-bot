import telebot
import os
import sqlite3
import traceback
from telebot import types

# إعدادات البوت
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

# =========================================================
# الجزء الأول: إدارة قاعدة البيانات (SQL)
# =========================================================
def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    # جدول الأنمي
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT)''')
    # جدول المشرفين
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
    # إضافة المالك إذا لم يكن موجوداً
    cursor.execute("INSERT OR IGNORE INTO admins_v2 VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)", (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# =========================================================
# الجزء الثاني: دوال الصلاحيات والتحقق
# =========================================================
def has_permission(user_id, perm_column):
    if user_id == OWNER_ID:
        return True
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM admins_v2 WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0] == 1:
        return True
    return False

# =========================================================
# الجزء الثالث: القوائم والأزرار (Markup)
# =========================================================
def get_main_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if has_permission(user_id, 'can_add_anime'):
        markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_anime_start"))
        markup.add(types.InlineKeyboardButton("✏️ تعديل أنمي", callback_data="edit_anime_start"))
    if has_permission(user_id, 'can_delete_anime'):
        markup.add(types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime_start"))
    if has_permission(user_id, 'can_manage_admins'):
        markup.add(types.InlineKeyboardButton("🛡 لوحة المشرفين", callback_data="admin_panel_main"))
    if has_permission(user_id, 'can_backup'):
        markup.add(types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="backup_db"))
    if has_permission(user_id, 'can_restore'):
        markup.add(types.InlineKeyboardButton("🔄 استرداد قاعدة", callback_data="restore_db_start"))
    if has_permission(user_id, 'can_list'):
        markup.add(types.InlineKeyboardButton("📋 قائمة الأنميات", callback_data="list_anime_all"))
    return markup

# =========================================================
# الجزء الرابع: معالجة الأحداث (Callback Handlers)
# =========================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        user_id = call.from_user.id
        message = call.message
        bot.answer_callback_query(call.id)
        bot.clear_step_handler_by_chat_id(message.chat.id)

        # 1. لوحة المشرفين
        if call.data == "admin_panel_main":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_start"))
            markup.add(types.InlineKeyboardButton("➖ حذف مشرف", callback_data="delete_admin_start"))
            markup.add(types.InlineKeyboardButton("⚙️ تعديل الصلاحيات", callback_data="perms_menu_start"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu_back"))
            bot.edit_message_text("🛡 لوحة إدارة المشرفين:", message.chat.id, message.message_id, reply_markup=markup)

        # 2. إضافة أنمي
        elif call.data == "add_anime_start":
            msg = bot.send_message(message.chat.id, "أرسل رابط الأنمي أولاً:")
            bot.register_next_step_handler(msg, process_add_anime_link)

        # 3. حذف أنمي
        elif call.data == "delete_anime_start":
            msg = bot.send_message(message.chat.id, "أرسل رابط الأنمي الذي تود حذفه:")
            bot.register_next_step_handler(msg, process_delete_anime)

        # 4. العودة للقائمة الرئيسية
        elif call.data == "main_menu_back":
            bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=get_main_keyboard(user_id))

        # (يمكنك إضافة المزيد من الـ elif هنا لتغطية كافة الخيارات...)

    except Exception as e:
        print(f"Error in callback: {e}")

# =========================================================
# الجزء الخامس: الدوال التنفيذية (التي تأخذ المدخلات)
# =========================================================
def process_add_anime_link(message):
    link = message.text
    msg = bot.send_message(message.chat.id, "الآن أرسل أسماء الأنمي (كل اسم في سطر):")
    bot.register_next_step_handler(msg, lambda m: save_anime_to_db(m, link))

def save_anime_to_db(message, link):
    names = message.text
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO anime (link, names) VALUES (?, ?)", (link, names))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم حفظ الأنمي بنجاح!")

def process_delete_anime(message):
    link = message.text
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anime WHERE link = ?", (link,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🗑 تم حذف الأنمي من القاعدة.")

# =========================================================
# الجزء السادس: التشغيل الآمن
# =========================================================
if __name__ == '__main__':
    # مسح الـ Webhook لمنع خطأ 409
    bot.remove_webhook()
    print("البوت يعمل الآن..")
    # التشغيل بانتظار 60 ثانية لتجنب التعليق
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
