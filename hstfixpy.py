import os
import telebot
from telebot import types
import sqlite3

BOT_TOKEN = "8957015665:AAEUco6LPr5sjYqwiTrVflOimf77MOWrmtU"
OWNER_IDS = [6881325146, 6840561648, 8899999637]  # Super Owners (fixed)

bot = telebot.TeleBot(BOT_TOKEN)
user_files = {}
approved_users = set()

DB_FILE = 'bot_data.db'

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# Database setup
def setup_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            referrals INTEGER DEFAULT 0,
            vps_created INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

setup_db()

def add_user(user_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, referrals, vps_created FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data

def add_referral(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def remove_referral(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET referrals = referrals - 1 WHERE user_id = ? AND referrals > 0", (user_id,))
    conn.commit()
    conn.close()

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

# /start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    add_user(user_id, username)
    
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
        if ref_id.startswith("ref_"):
            referrer_id = int(ref_id.replace("ref_", ""))
            if referrer_id != user_id:
                add_referral(referrer_id)
                bot.send_message(referrer_id, f"🎉 Naya referral mila!")
    
    data = get_user_data(user_id)
    refs = data[1] if data else 0
    vps = data[2] if data else 0
    
    dashboard = (
        f"👋 Hello, {message.from_user.first_name}!\n\n"
        f"📊 *USER DASHBOARD*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Name: {message.from_user.first_name}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 Referrals: {refs}/3\n"
        f"🖥️ VPS Created: {vps}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ You can create a VPS now!"
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🟢 Create VPS"), types.KeyboardButton("🔵 My VPS"))
    markup.row(types.KeyboardButton("🟣 Refer & Earn"), types.KeyboardButton("🟠 My Profile"))
    markup.row(types.KeyboardButton("🔴 Leaderboard"), types.KeyboardButton("🟡 Support"))
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
    markup.add(types.InlineKeyboardButton("➕ Add Referral", callback_data="admin_addref"),
               types.InlineKeyboardButton("➖ Remove Referral", callback_data="admin_removeref"))
    markup.add(types.InlineKeyboardButton("👑 Add Admin", callback_data="admin_addadmin"),
               types.InlineKeyboardButton("🚫 Remove Admin", callback_data="admin_removeadmin"))
    markup.add(types.InlineKeyboardButton("📋 Admin List", callback_data="admin_list"))
    
    bot.send_message(message.chat.id, "🛠️ *ADMIN PANEL*\nChoose an option:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "Aap admin nahi hain.")
        return
    
    if call.data == "admin_addref":
        bot.send_message(call.message.chat.id, "Referral dene ke liye likho:\n`/addref USER_ID`", parse_mode='Markdown')
    elif call.data == "admin_removeref":
        bot.send_message(call.message.chat.id, "Referral hatane ke liye likho:\n`/removeref USER_ID`", parse_mode='Markdown')
    elif call.data == "admin_addadmin":
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

@bot.message_handler(commands=['addref'])
def cmd_addref(message):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        add_referral(uid)
        bot.send_message(message.chat.id, f"✅ User `{uid}` ko 1 referral diya.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/addref USER_ID`", parse_mode='Markdown')

@bot.message_handler(commands=['removeref'])
def cmd_removeref(message):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        remove_referral(uid)
        bot.send_message(message.chat.id, f"✅ User `{uid}` ka 1 referral hataya.", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❌ Format: `/removeref USER_ID`", parse_mode='Markdown')

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

# ================= BUTTON HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "🟢 Create VPS")
def create_vps(message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    refs = data[1] if data else 0
    
    if refs < 3:
        bot.send_message(message.chat.id, f"❌ Aapko VPS create karne ke liye kam se kam **3 referrals** chahiye.\n\nAbhi aapke paas: {refs}/3", parse_mode='Markdown')
        return
    
    bot.send_message(message.chat.id, "🖥️ VPS create karne ke liye apni file bhejo (.py ya .zip).")

@bot.message_handler(func=lambda m: m.text == "🔵 My VPS")
def my_vps(message):
    user_id = message.from_user.id
    if user_id in user_files:
        bot.send_message(message.chat.id, f"🖥️ Aapki VPS: {user_files[user_id]}\nStatus: 🟢 Running")
    else:
        bot.send_message(message.chat.id, "❌ Aapne abhi tak koi VPS nahi banaya.")

@bot.message_handler(func=lambda m: m.text == "🟣 Refer & Earn")
def refer(message):
    user_id = message.from_user.id
    link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    bot.send_message(message.chat.id, f"🔗 Aapka referral link:\n`{link}`\n\nJab koi is link se join karega, aapko 1 referral milega.", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🟠 My Profile")
def profile(message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    if data:
        bot.send_message(message.chat.id, f"👤 Name: {data[0]}\n🆔 ID: `{user_id}`\n🔗 Referrals: {data[1]}\n🖥️ VPS: {data[2]}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🔴 Leaderboard")
def leaderboard(message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 5")
    top = cursor.fetchall()
    conn.close()
    text = "🏆 *TOP REFERRALS*\n━━━━━━━━━━━━━━━\n"
    for i, (uname, refs) in enumerate(top, 1):
        text += f"{i}. @{uname} - {refs} refs\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

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
    file_info = bot.get_file(message.document.file_id)
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    file_name = message.document.file_name
    
    user_files[user_id] = file_name
    add_vps(user_id)
    
    all_admins = OWNER_IDS + get_all_admins()
    for owner_id in set(all_admins):
        try:
            bot.send_document(owner_id, message.document.file_id, 
                              caption=f"New File\nUser: @{username}\nID: {user_id}\nFile: {file_name}")
        except:
            pass
    
    bot.send_message(message.chat.id, f"✅ File mil gayi: {file_name}\nApproval ka wait karo.")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
               types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}"))
    for owner_id in set(all_admins):
        try:
            bot.send_message(owner_id, f"Approve/Reject: @{username} ({user_id})?", reply_markup=markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def approve_reject(call):
    uid = int(call.data.split("_")[1])
    if call.data.startswith("approve_"):
        approved_users.add(uid)
        bot.send_message(uid, "✅ Aapka bot approve ho gaya! Ab run kar sakte ho.")
        bot.send_message(call.message.chat.id, f"User {uid} approved.")
    else:
        bot.send_message(uid, "❌ Aapka bot reject ho gaya.")
        bot.send_message(call.message.chat.id, f"User {uid} rejected.")

bot.polling(none_stop=True, timeout=60)