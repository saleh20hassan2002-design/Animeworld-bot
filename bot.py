import telebot
import os
import sqlite3
from telebot import types

# تأكد من إضافة BOT_TOKEN في Variables على Railway
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 5577477357
DB_NAME = 'anime_v3.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # إنشاء جداول نظيفة
    cursor.execute('''CREATE TABLE IF NOT EXISTS anime (link TEXT PRIMARY KEY, names TEXT, image_url TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins_v3 
                      (user_id INTEGER PRIMARY KEY, username TEXT, 
                       p_admins INTEGER, p_add INTEGER, p_del INTEGER, 
                       p_backup INTEGER, p_restore INTEGER, p_list INTEGER, p_edit INTEGER)''')
    # إضافة المالك
    cursor.execute("INSERT OR IGNORE INTO admins_v3 VALUES (?, ?, 1, 1, 1, 1, 1, 1, 1)", 
                   (OWNER_ID, "Owner", 1, 1, 1, 1, 1, 1, 1))
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins_v3 WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"),
        types.InlineKeyboardButton("✏️ تعديل الأنميات", callback_data="list_edit")
    )
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
    if message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "مرحباً! أنا جاهز للعمل في هذه المجموعة.")
    elif is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "مرحباً بك يا مدير، اختر إجراءً:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if not is_admin(call.from_user.id): return
    
    if call.data == "admin_panel":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin"),
                   types.InlineKeyboardButton("📋 قائمة المشرفين", callback_data="admin_list"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
        bot.edit_message_text("🛡 لوحة تحكم المشرفين:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_main":
        bot.edit_message_text("مرحباً بك يا مدير، اختر إجراءً:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    elif call.data == "list_edit":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT link, names FROM anime")
        animes = cursor.fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup()
        for link, name in animes:
            markup.add(types.InlineKeyboardButton(f"✏️ {name}", callback_data=f"edit_mode_{link}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
        bot.edit_message_text("اختر الأنمي للتعديل:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("edit_mode_"):
        link = call.data.replace("edit_mode_", "")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("تعديل الاسم", callback_data=f"up_name_{link}"),
                   types.InlineKeyboardButton("تعديل الصورة", callback_data=f"up_img_{link}"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="list_edit"))
        bot.edit_message_text("ماذا تريد أن تعدل؟", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith(("up_name_", "up_img_")):
        parts = call.data.split("_", 2)
        field = "names" if parts[1] == "name" else "image_url"
        link = parts[2]
        bot.send_message(call.message.chat.id, "أرسل القيمة الجديدة:")
        bot.register_next_step_handler(call.message, lambda m: update_db(m, link, field))

    elif call.data == "admin_list":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username FROM admins_v3")
        admins = cursor.fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup()
        for uid, name in admins:
            markup.add(types.InlineKeyboardButton(f"👤 {name} 🗑", callback_data=f"del_adm_{uid}"),
                       types.InlineKeyboardButton("⚙️ صلاحيات", callback_data=f"perms_{uid}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        bot.edit_message_text("📋 قائمة المشرفين:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("perms_"):
        uid = int(call.data.split("_")[1])
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT p_admins, p_add, p_del, p_backup, p_restore, p_list, p_edit FROM admins_v3 WHERE user_id = ?", (uid,))
        perms = cursor.fetchone()
        conn.close()
        markup = types.InlineKeyboardMarkup()
        labels = ["المشرفين", "إضافة أنمي", "حذف أنمي", "نسخ احتياطي", "استرداد", "القائمة", "تعديل أنمي"]
        for i, label in enumerate(labels):
            status = "✅" if perms[i] == 1 else "❌"
            markup.add(types.InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{uid}_{i+1}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_list"))
        bot.edit_message_text(f"⚙️ تحكم بصلاحيات المستخدم {uid}:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("toggle_"):
        data_parts = call.data.split("_")
        uid, p_idx = int(data_parts[1]), int(data_parts[2])
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cols = ['p_admins', 'p_add', 'p_del', 'p_backup', 'p_restore', 'p_list', 'p_edit']
        cursor.execute(f"UPDATE admins_v3 SET {cols[p_idx-1]} = NOT {cols[p_idx-1]} WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "تم التحديث!")
        callback_handler(types.CallbackQuery(id=call.id, from_user=call.from_user, chat_instance="", message=call.message, data=f"perms_{uid}"))

    elif call.data == "add_admin":
        bot.send_message(call.message.chat.id, "أرسل ID واسم المشرف (مثال: 12345, الاسم):")
        bot.register_next_step_handler(call.message, save_new_admin)

    elif call.data == "add_new":
        bot.send_message(call.message.chat.id, "أرسل رابط الأنمي:")
        bot.register_next_step_handler(call.message, get_link)

    elif call.data == "delete_anime":
        bot.send_message(call.message.chat.id, "أرسل رابط الأنمي للحذف:")
        bot.register_next_step_handler(call.message, delete_anime_db)

    elif call.data == "backup":
        with open(DB_NAME, 'rb') as f: bot.send_document(call.message.chat.id, f)

    elif call.data == "restore":
        bot.send_message(call.message.chat.id, "أرسل ملف القاعدة:")
        bot.register_next_step_handler(call.message, process_restore)

    elif call.data == "list_anime":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT names FROM anime")
        animes = [a[0] for a in cursor.fetchall()]
        conn.close()
        bot.send_message(call.message.chat.id, "📋 القائمة:\n" + "\n".join(animes) if animes else "فارغة.")

def update_db(message, link, field):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE anime SET {field} = ? WHERE link = ?", (message.text, link))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم التحديث بنجاح!")

def save_new_admin(message):
    try:
        parts = message.text.split(',')
        uid, name = int(parts[0].strip()), parts[1].strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins_v3 (user_id, username, p_admins, p_add, p_del, p_backup, p_restore, p_list, p_edit) VALUES (?, ?, 0,0,0,0,0,0,0)", (uid, name))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة المشرف!")
    except: bot.reply_to(message, "خطأ! تأكد من الصيغة: ID, الاسم")

def get_link(message):
    link = message.text
    bot.send_message(message.chat.id, "أرسل الأسماء:")
    bot.register_next_step_handler(message, lambda m: get_names(m, link))
def get_names(message, link):
    names = message.text
    bot.send_message(message.chat.id, "أرسل رابط الصورة:")
    bot.register_next_step_handler(message, lambda m: save_final(m, link, names))
def save_final(message, link, names):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO anime VALUES (?, ?, ?)", (link, names, message.text))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم الحفظ!")
def delete_anime_db(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anime WHERE link = ?", (message.text,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🗑 تم الحذف.")
def process_restore(message):
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(DB_NAME, 'wb') as f: f.write(downloaded)
        bot.reply_to(message, "✅ تم الاسترداد!")

if __name__ == '__main__':
    bot.infinity_polling()
