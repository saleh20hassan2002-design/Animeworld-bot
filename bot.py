import telebot
import os
import sqlite3
import difflib
from telebot import types

# جلب التوكن من متغيرات البيئة
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357

def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    # إضافة المالك كأول مشرف
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
    conn.commit()
    conn.close()

# تشغيل التهيئة عند بداية الكود
init_db()

def is_admin(user_id):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"))
    if user_id == OWNER_ID:
        markup.add(
            types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime"),
            types.InlineKeyboardButton("🛡 المشرفين", callback_data="admin_panel"),
            types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="backup"),
            types.InlineKeyboardButton("🔄 استرداد", callback_data="restore"),
            types.InlineKeyboardButton("📋 القائمة", callback_data="list_anime")
        )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "مرحباً! اختر إجراءً:", reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # التحقق من صلاحية المشرف
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "عذراً، هذه الأزرار للمشرفين فقط!")
        return
    
    # حماية أوامر المالك
    if call.data in ["delete_anime", "admin_panel", "backup", "restore", "list_anime"] and call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "هذه الصلاحية للمالك فقط!")
        return

    if call.data == "admin_panel":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ إضافة مشرف جديد", callback_data="add_admin"))
        bot.edit_message_text("⚙️ لوحة تحكم المشرفين:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "add_admin":
        bot.send_message(call.message.chat.id, "أرسل الـ ID الخاص بالمشرف الجديد:")
        bot.register_next_step_handler(call.message, save_new_admin)
    elif call.data == "add_new":
        bot.send_message(call.message.chat.id, "أرسل رابط الأنمي:")
        bot.register_next_step_handler(call.message, get_names_for_link)
    elif call.data == "delete_anime":
        bot.send_message(call.message.chat.id, "أرسل رابط الأنمي للحذف:")
        bot.register_next_step_handler(call.message, delete_anime_db)
    elif call.data == "backup":
        try:
            with open('anime.db', 'rb') as f:
                bot.send_document(call.message.chat.id, f)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"خطأ في النسخ الاحتياطي: {e}")
    elif call.data == "restore":
        bot.send_message(call.message.chat.id, "أرسل ملف قاعدة البيانات (anime.db) الآن:")
        bot.register_next_step_handler(call.message, process_restore)
    elif call.data == "list_anime":
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("SELECT names FROM anime")
        animes = [a[0].split('\n')[0] for a in cursor.fetchall()]
        conn.close()
        text = "📋 قائمة الأنميات:\n\n" + "\n".join(animes) if animes else "القائمة فارغة."
        bot.send_message(call.message.chat.id, text)

# [بقية الدوال كما هي...]
# ملاحظة: تأكد من إبقاء الدوال الأخرى (get_names_for_link, save_anime_data, إلخ) أسفل هذا الكود.

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def search_anime(message):
    query = message.text.lower().strip()
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT link, names FROM anime")
    all_anime = cursor.fetchall()
    conn.close()
    
    for link, names in all_anime:
        name_list = [n.strip().lower() for n in names.split('\n')]
        for name in name_list:
            if query == name or difflib.SequenceMatcher(None, query, name).ratio() > 0.85:
                display_name = names.split('\n')[0]
                bot.reply_to(message, f"✨ تم العثور على الأنمي!\n\n📺 الاسم: {display_name}\n🔗 {link}")
                return

# التصحيح الأهم هنا:
if __name__ == '__main__':
    bot.infinity_polling()
