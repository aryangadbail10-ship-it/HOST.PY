import os
import telebot
from telebot import types
import sqlite3
import subprocess
import sys
import time

# ⚠️ IMPORTANT: Apna naya token yahan daalo (BotFather se /revoke karke naya lo)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8957015665:AAEUco6LPr5sjYqwiTrVflOimf77MOWrmtU")
OWNER_IDS = [6881325146, 6840561648, 8899999637]

bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = 'bot_data.db'
BOTS_DIR = 'user_bots'
os.makedirs(BOTS_DIR, exist_ok=True)

running_bots = {}  # {user_id: subprocess.Popen}

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def setup_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            vps_created INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'approved' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 0")
        conn.commit()
    if 'vps_created' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN vps_created INTEGER DEFAULT 0")
        conn.commit()
    conn.close()

setup_db()

def add_user(user_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, approved) VALUES (?, ?, 0)", (user_id, username))
        conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, vps_created, approved FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data

def set_approved(user_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET approved = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()

def is_approved(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT approved FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def add_vps(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET vps_created = vps_created + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_admin(user_id):
    if user_id in OWNER_IDS:
        return True
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in cursor.fetchall()]
    conn.close()
    return admins

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    add_user(user_id, username)
    
    data = get_user_data(user_id)
    vps = data[1] if data else 0
    approved = data[2] if data else 0
    
    status = "✅ Approved" if approved else "⏳ Not Approved"
    
    dashboard = (
        f"👋 Hello, {message.from_user.first_name}!\n\n"
        f"📊 *USER DASHBOARD*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Name: {message.from_user.first_name}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🖥️ VPS Created: {vps}\n"
        f"🔐 Status: {status}\n"
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🟢 Create VPS"), types.KeyboardButton("🔵 My VPS"))
    markup.row(types.KeyboardButton("🟠 My Profile"), types.KeyboardButton("🟡 Support"))
    markup.row(types.KeyboardButton("📞 Contact Owner"))
    
    bot.send_message(message.chat.id, dashboard, parse_mode='Markdown', reply_markup=markup)

# ================= ADMIN PANEL =================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ Aap admin nahi hain.")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👑 Add Admin", callback_data="admin_addadmin"),
               types.InlineKeyboardButton("🚫 Remove Admin", callback_data="admin_removeadmin"))
    markup.add(types.InlineKeyboardButton("📋 Admin List", callback_data="admin_list"))
    markup.add(types.InlineKeyboardButton("👥 All Users", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("✉️ Message a User", callback_data="admin_msguser"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast to All", callback_data="admin_broadcast"))
    
    bot.send_message(message.chat.id, "🛠️ *ADMIN PANEL*\nChoose an option:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "Aap admin nahi hain.")
        return
    
    if call.data == "admin_addadmin":
        bot.send_message(call.message.chat.id, "Admin banane ke liye likho:\n`/addadmin USER_ID`", parse_mode='Markdown')
    elif call.data == "admin_removeadmin":
        bot.send_message(call.message.chat.id, "Admin hatane ke liye likho:\n`/removeadmin USER_ID`", parse_mode='Markdown')
    elif call.data == "admin_list":
        admins = get_all_admins()
        if admins:
            text = "👑 *Admin List:*\n" + "\n".join([f"• `{a}`" for a in admins])
        else:
            text = "Koi extra admin nahi hai."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    elif call.data == "admin_users":
        users = get_all_users()
        if not users:
            bot.send_message(call.message.chat.id, "Koi user nahi hai.")
            return
        text = "👥 *All Users:*\n━━━━━━━━━━━━━━━\n"
        for uid, uname in users:
            text += f"• @{uname} - `{uid}`\n"
        if len(text) > 4000:
            text = text[:4000] + "\n...aur bhi hain."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    elif call.data == "admin_msguser":
        bot.send_message(call.message.chat.id, "Message bhejne ke liye likho:\n`/msg USER_ID aapka message`", parse_mode='Markdown')
    elif call.data == "admin_broadcast":
        bot.send_message(call.message.chat.id, "Sabhi users ko message bhejne ke liye likho:\n`/broadcast aapka message`", parse_mode='Markdown')

@bot.message_handler(commands=['addadmin'])
def cmd_addadmin(message):
    if message.from_user.id not in OWNER_IDS:
        bot.send_message(message.chat.id, "❌ Sirf Super Owner admin add kar sakte hain.")
        return
    try:
        uid = int(message.text.split()[1])
        add_admin(uid)
        bot.send_message(message.chat.id, f"✅ User `{uid}` ab admin hai.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/addadmin USER_ID`", parse_mode='Markdown')

@bot.message_handler(commands=['removeadmin'])
def cmd_removeadmin(message):
    if message.from_user.id not in OWNER_IDS:
        bot.send_message(message.chat.id, "❌ Sirf Super Owner admin remove kar sakte hain.")
        return
    try:
        uid = int(message.text.split()[1])
        remove_admin(uid)
        bot.send_message(message.chat.id, f"✅ User `{uid}` ab admin nahi hai.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/removeadmin USER_ID`", parse_mode='Markdown')

@bot.message_handler(commands=['users'])
def cmd_users(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Aap admin nahi hain.")
        return
    users = get_all_users()
    if not users:
        bot.send_message(message.chat.id, "Koi user nahi hai.")
        return
    text = "👥 *All Users:*\n━━━━━━━━━━━━━━━\n"
    for uid, uname in users:
        text += f"• @{uname} - `{uid}`\n"
    if len(text) > 4000:
        text = text[:4000] + "\n...aur bhi hain."
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['msg'])
def cmd_msg(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Aap admin nahi hain.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        uid = int(parts[1])
        msg = parts[2]
        bot.send_message(uid, f"📩 *Admin Message:*\n\n{msg}", parse_mode='Markdown')
        bot.send_message(message.chat.id, f"✅ Message bhej diya user `{uid}` ko.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/msg USER_ID aapka message`", parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Aap admin nahi hain.")
        return
    try:
        msg = message.text.split(maxsplit=1)[1]
    except:
        bot.send_message(message.chat.id, "❌ Format: `/broadcast aapka message`", parse_mode='Markdown')
        return
    
    users = get_all_users()
    sent = 0
    failed = 0
    for uid, _ in users:
        try:
            bot.send_message(uid, f"📢 *Broadcast:*\n\n{msg}", parse_mode='Markdown')
            sent += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ Broadcast complete!\n\nSent: {sent}\nFailed: {failed}", parse_mode='Markdown')

# ================= BUTTON HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "🟢 Create VPS")
def create_vps(message):
    bot.send_message(message.chat.id, "🖥️ Bot host karne ke liye apni file bhejo (.py)")

@bot.message_handler(func=lambda m: m.text == "🔵 My VPS")
def my_vps(message):
    user_id = message.from_user.id
    if user_id in running_bots:
        bot.send_message(message.chat.id, "🖥️ Aapka bot abhi RUN ho raha hai ✅\n\nBand karne ke liye /stop likho.")
    else:
        bot.send_message(message.chat.id, "❌ Aapka koi bot abhi RUN nahi ho raha.")

@bot.message_handler(func=lambda m: m.text == "🟠 My Profile")
def profile(message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    if data:
        status = "✅ Approved" if data[2] else "⏳ Not Approved"
        bot.send_message(message.chat.id, f"👤 Name: {data[0]}\n🆔 ID: `{user_id}`\n🖥️ VPS: {data[1]}\n🔐 Status: {status}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🟡 Support")
def support(message):
    bot.send_message(message.chat.id, "🟡 Support ke liye @finxzzcntctbot se contact karo.")

@bot.message_handler(func=lambda m: m.text == "📞 Contact Owner")
def contact(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📞 Contact Owner", url="https://t.me/finxzzcntctbot"))
    bot.send_message(message.chat.id, "Owner se baat karne ke liye niche click karo:", reply_markup=markup)

# ================= FILE UPLOAD =================
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    file_name = message.document.file_name
    
    if not file_name.endswith('.py'):
        bot.send_message(message.chat.id, "❌ Sirf .py file bhejo.")
        return
    
    user_folder = os.path.join(BOTS_DIR, f"user_{user_id}")
    os.makedirs(user_folder, exist_ok=True)
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    file_path = os.path.join(user_folder, "bot.py")
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)
    
    set_approved(user_id, False)
    
    bot.send_message(message.chat.id, f"✅ File mil gayi: {file_name}\n\n⏳ Admin approval ka wait karo. Approve hone ke baad /run karna.")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
               types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    
    all_admins = OWNER_IDS + get_all_admins()
    for owner_id in set(all_admins):
        try:
            bot.send_document(owner_id, message.document.file_id, 
                              caption=f"📁 *New Bot File*\nUser: @{username}\nID: `{user_id}`\nFile: {file_name}",
                              parse_mode='Markdown')
            bot.send_message(owner_id, f"Approve/Reject: @{username} (`{user_id}`)?", 
                             reply_markup=markup, parse_mode='Markdown')
        except:
            pass

# ================= APPROVE / REJECT =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def approve_reject(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Aap admin nahi hain.")
        return
    
    uid = int(call.data.split("_")[1])
    
    if call.data.startswith("approve_"):
        set_approved(uid, True)
        add_vps(uid)
        bot.send_message(uid, "✅ Aapka bot APPROVE ho gaya! Ab /run likho aur bot chalao. 🚀")
        bot.send_message(call.message.chat.id, f"✅ User `{uid}` approved.", parse_mode='Markdown')
    else:
        set_approved(uid, False)
        if uid in running_bots:
            try:
                running_bots[uid].terminate()
                del running_bots[uid]
            except:
                pass
        bot.send_message(uid, "❌ Aapka bot REJECT kar diya gaya. Aap admin se contact karo.")
        bot.send_message(call.message.chat.id, f"❌ User `{uid}` rejected.", parse_mode='Markdown')

# ================= RUN BOT (WITH ERROR LOGGING) =================
@bot.message_handler(commands=['run'])
def cmd_run(message):
    user_id = message.from_user.id
    
    if not is_approved(user_id):
        bot.send_message(message.chat.id, "❌ Aapka bot abhi approve nahi hua.\n\nAdmin approval ka wait karo.")
        return
    
    user_folder = os.path.join(BOTS_DIR, f"user_{user_id}")
    bot_file = os.path.join(user_folder, "bot.py")
    log_file = os.path.join(user_folder, "error.log")
    
    if not os.path.exists(bot_file):
        bot.send_message(message.chat.id, "❌ Pehle apni bot file bhejo.")
        return
    
    if user_id in running_bots:
        bot.send_message(message.chat.id, "⚠️ Aapka bot already RUN ho raha hai.")
        return
    
    try:
        # Error log file mein save karo
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                [sys.executable, bot_file],
                cwd=user_folder,
                stdout=f,
                stderr=f
            )
        
        running_bots[user_id] = process
        
        # 3 second wait karo, dekho bot zinda hai ya nahi
        time.sleep(3)
        
        if process.poll() is not None:
            # Bot crash ho gaya
            del running_bots[user_id]
            with open(log_file, 'r') as f:
                error = f.read()
            
            if not error:
                error = "Unknown error (koi output nahi)"
            
            # Error message ko chhota karo
            if len(error) > 1000:
                error = error[:1000] + "..."
            
            bot.send_message(message.chat.id, f"❌ *Aapka bot CRASH ho gaya!*\n\n*Error:*\n```\n{error}\n```", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "✅ Aapka bot RUN ho gaya! 🚀\n\nBand karne ke liye /stop likho.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# ================= STOP BOT =================
@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    user_id = message.from_user.id
    if user_id in running_bots:
        try:
            running_bots[user_id].terminate()
            del running_bots[user_id]
            bot.send_message(message.chat.id, "🛑 Aapka bot band kar diya gaya.")
        except:
            bot.send_message(message.chat.id, "❌ Bot band karne mein error.")
    else:
        bot.send_message(message.chat.id, "❌ Aapka koi bot RUN nahi ho raha.")

# ================= ADMIN: STOP ANY BOT =================
@bot.message_handler(commands=['stopbot'])
def cmd_stopbot(message):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        if uid in running_bots:
            running_bots[uid].terminate()
            del running_bots[uid]
            bot.send_message(message.chat.id, f"✅ User `{uid}` ka bot band kar diya.", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"❌ User `{uid}` ka koi bot RUN nahi hai.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/stopbot USER_ID`", parse_mode='Markdown')

bot.polling(none_stop=True, timeout=60)