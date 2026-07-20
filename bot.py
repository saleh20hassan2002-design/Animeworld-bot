import telebot
import os
import sqlite3
import difflib
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
    
    # التأكد من إضافة المالك بصلاحيات كاملة
    cursor.execute("SELECT * FROM admins_v2 WHERE user_id = ?", (OWNER_ID,))
    if not cursor.fetchone():
        cursor.execute('''INSERT INTO admins_v2 
            (user_id, name, can_manage_admins, can_add_anime, can_delete_anime, can_backup, can_restore, can_list) 
            VALUES (?, 'المالك', 1, 1, 1, 1, 1, 1)''', (OWNER_ID,))
    conn.commit()
    conn.close()

init_db()

# ==================== دوال الصلاحيات ====================
def has_permission(user_id, perm_column):
    if user_id == OWNER_ID:
        return True
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
    
    if not admin:
        return None
        
    perms = {
        'المشرفين': ('can_manage_admins', admin[2]),
        'إضافة أنمي': ('can_add_anime', admin[3]),
        'حذف أنمي': ('can_delete_anime', admin[4]),
        'نسخ احتياطي': ('can_backup', admin[5]),
        'استرداد': ('can_restore', admin[6]),
        'القائمة': ('can_list', admin[7])
    }
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for text, (col, val) in perms.items():
        icon = "✅" if val == 1 else "❌"
        markup.add(types.InlineKeyboardButton(f"{text} {icon}", callback_data=f"perm:{admin_id}:{col}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    return markup

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if has_permission(user_id, 'can_add_anime'):
        markup.add(
            types.InlineKeyboardButton("➕ إضافة أنمي", callback_data="add_new"),
            types.InlineKeyboardButton("✏️ تعديل أنمي", callback_data="edit_anime")
        )
        
    buttons = []
    if has_permission(user_id, 'can_delete_anime'):
        buttons.append(types.InlineKeyboardButton("➖ حذف أنمي", callback_data="delete_anime"))
    if has_permission(user_id, 'can_manage_admins'):
        buttons.append(types.InlineKeyboardButton("🛡 المشرفين", callback_data="admin_panel"))
    if has_permission(user_id, 'can_backup'):
        buttons.append(types.InlineKeyboardButton("💾 نسخ احتياطي", callback_data="backup"))
    if has_permission(user_id, 'can_restore'):
        buttons.append(types.InlineKeyboardButton("🔄 استرداد", callback_data="restore"))
    if has_permission(user_id, 'can_list'):
        buttons.append(types.InlineKeyboardButton("📋 القائمة", callback_data="list_anime"))
        
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    return markup

# ==================== الأوامر والبحث ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "مرحباً بك! اختر إجراءً:", reply_markup=main_menu(message.from_user.id))

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/'))
def search_anime_smart(message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT link, names FROM anime")
    all_anime = cursor.fetchall()
    conn.close()
    
    for link, names in all_anime:
        name_list = [n.strip().lower() for n in names.split('\n')]
        if any(query in name or difflib.SequenceMatcher(None, query, name).ratio() > 0.8 for name in name_list):
            display_name = names.split('\n')[0]
            bot.reply_to(message, f"✨ تم العثور على الأنمي!\n\n📺 الاسم: {display_name}\n🔗 {link}")
            return

# ==================== معالجة الأزرار (الـ Callbacks) ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    message = call.message
    
    # إيقاف علامة التحميل في زر تلجرام (خطوة مهمة جداً لمنع التعليق)
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
        
    # تنظيف أي خطوات سابقة بأمان
    bot.clear_step_handler_by_chat_id(message.chat.id)
    
    if call.data == "back_to_main":
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))
    
    # -------- لوحة المشرفين --------
    elif call.data == "admin_panel":
        if not has_permission(user_id, 'can_manage_admins'):
            bot.answer_callback_query(call.id, "لا تملك الصلاحية!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_prompt"), 
            types.InlineKeyboardButton("➖ حذف مشرف", callback_data="del_admin_prompt"), 
            types.InlineKeyboardButton("⚙️ صلاحيات المشرفين", callback_data="edit_perms_list"), 
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
        )
        bot.edit_message_text("🛡 لوحة تحكم المشرفين:", message.chat.id, message.message_id, reply_markup=markup)

    elif call.data == "add_admin_prompt":
        bot.send_message(message.chat.id, "أرسل الـ ID الخاص بالمشرف فقط:")
        bot.register_next_step_handler(message, process_add_admin)
        
    elif call.data == "del_admin_prompt":
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM admins_v2 WHERE user_id != ?", (OWNER_ID,))
        admins = cursor.fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for adm_id, name in admins: 
            markup.add(types.InlineKeyboardButton(f"🗑 حذف: {name}", callback_data=f"del_user:{adm_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        bot.edit_message_text("اختر المشرف للحذف:", message.chat.id, message.message_id, reply_markup=markup)
        
    elif call.data.startswith("del_user:"):
        target_id = int(call.data.split(":")[1])
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins_v2 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "تم حذف المشرف!", show_alert=True)
        bot.edit_message_text("القائمة الرئيسية:", message.chat.id, message.message_id, reply_markup=main_menu(user_id))

    elif call.data == "edit_perms_list":
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM admins_v2 WHERE user_id != ?", (OWNER_ID,))
        admins = cursor.fetchall()
        conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for adm_id, name in admins: 
            markup.add(types.InlineKeyboardButton(f"👤 {name}", callback_data=f"edit_perm_user:{adm_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        bot.edit_message_text("اختر مشرف لتعديل صلاحياته:", message.chat.id, message.message_id, reply_markup=markup)
    
    elif call.data.startswith("edit_perm_user:"):
        target_id = int(call.data.split(":")[1])
        bot.edit_message_text(f"⚙️ صلاحيات ({target_id}):", message.chat.id, message.message_id, reply_markup=get_permissions_keyboard(target_id))

    elif call.data.startswith("perm:"):
        _, target_id, perm_col = call.data.split(":")
        target_id = int(target_id)
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute(f"SELECT {perm_col} FROM admins_v2 WHERE user_id = ?", (target_id,))
        val = cursor.fetchone()[0]
        cursor.execute(f"UPDATE admins_v2 SET {perm_col} = ? WHERE user_id = ?", (0 if val == 1 else 1, target_id))
        conn.commit()
        conn.close()
        bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=get_permissions_keyboard(target_id))

    # -------- الأنمي والإدارة العامة --------
    elif call.data == "add_new":
        if not has_permission(user_id, 'can_add_anime'): return
        bot.send_message(message.chat.id, "أرسل رابط الأنمي:")
        bot.register_next_step_handler(message, get_names_for_link)
        
    elif call.data == "edit_anime":
        if not has_permission(user_id, 'can_add_anime'): return
        bot.send_message(message.chat.id, "أرسل رابط الأنمي الذي تريد تعديله:")
        bot.register_next_step_handler(message, edit_anime_flow)

    elif call.data == "delete_anime":
        if not has_permission(user_id, 'can_delete_anime'): return
        bot.send_message(message.chat.id, "أرسل رابط الأنمي للحذف:")
        bot.register_next_step_handler(message, delete_anime_db)
        
    elif call.data == "backup":
        if not has_permission(user_id, 'can_backup'): return
        try:
            with open('anime.db', 'rb') as f: 
                bot.send_document(message.chat.id, f)
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ لا يوجد بيانات حالياً للنسخ.")
        
    elif call.data == "restore":
        if not has_permission(user_id, 'can_restore'): return
        bot.send_message(message.chat.id, "أرسل ملف القاعدة (anime.db):")
        bot.register_next_step_handler(message, process_restore)
        
    elif call.data == "list_anime":
        if not has_permission(user_id, 'can_list'): return
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("SELECT names FROM anime")
        animes = [a[0].split('\n')[0] for a in cursor.fetchall()]
        conn.close()
        bot.send_message(message.chat.id, "📋 القائمة:\n\n" + "\n".join(animes) if animes else "القائمة فارغة.")

# ==================== دوال الإدخال (Step Handlers) ====================
def process_add_admin(message):
    try:
        new_id = int(message.text.strip())
        conn = sqlite3.connect('anime.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO admins_v2 (user_id, name) VALUES (?, ?)", (new_id, "مشرف جديد"))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم الإضافة!")
    except:
        bot.reply_to(message, "⚠️ خطأ! أرسل الـ ID (أرقام فقط).")

def get_names_for_link(message):
    link = message.text
    bot.send_message(message.chat.id, "أرسل الأسماء (كل اسم في سطر):")
    bot.register_next_step_handler(message, lambda m: save_anime_data(m, link))

def save_anime_data(message, link):
    names = message.text.replace(',', '\n')
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO anime (link, names) VALUES (?, ?)", (link, names))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم الحفظ!")

def edit_anime_flow(message):
    link = message.text
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT names FROM anime WHERE link = ?", (link,))
    res = cursor.fetchone()
    conn.close()
    
    if not res:
        bot.reply_to(message, "⚠️ الرابط غير موجود.")
        return
        
    bot.send_message(message.chat.id, f"الأنمي الحالي: {res[0]}\nأرسل الأسماء الجديدة (كل اسم في سطر):")
    bot.register_next_step_handler(message, lambda m: update_anime_db(m, link))

def update_anime_db(message, link):
    new_names = message.text.replace(',', '\n')
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE anime SET names = ? WHERE link = ?", (new_names, link))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم التحديث!")

def process_restore(message):
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open('anime.db', 'wb') as f: 
                f.write(downloaded_file)
            bot.reply_to(message, "✅ تم الاسترداد بنجاح!")
        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ أثناء الاسترداد: {e}")
    else:
        bot.reply_to(message, "⚠️ يجب إرسال ملف .db")

def delete_anime_db(message):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anime WHERE link = ?", (message.text,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🗑 تم الحذف.")

# ==================== تشغيل البوت ====================
if __name__ == '__main__':
    bot.infinity_polling()
