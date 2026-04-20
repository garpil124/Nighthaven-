from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime
import pytz
import sqlite3
import math
import traceback

WIB = pytz.timezone("Asia/Jakarta")

# ================= DB =================

db = sqlite3.connect("absen2.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS absen (
    chat_id INTEGER,
    user_id INTEGER,
    name TEXT,
    type TEXT,
    alasan TEXT,
    date TEXT
)
""")
db.commit()

absen_msg = {}
pending_izin = {}
job_refresh = {}

last_day = None
last_week = None


# ================= DEBUG =================

def debug(msg):
    print(f"[ABSEN DEBUG] {msg}")


# ================= BAR =================

def status_bar(value, speed=1.0, length=10):
    t = datetime.now().second * speed
    wave = int((math.sin(t / 2) + 1) * (length / 2))
    return "▰" * wave + "▱" * (length - wave) + f" {value}"


# ================= SAVE (NOW WITH TIME) =================

def save_absen(chat_id, user_id, name, tipe, alasan=None):
    now = datetime.now(WIB).strftime("%H:%M WIB")

    cur.execute("""
        INSERT INTO absen (chat_id, user_id, name, type, alasan, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, name, tipe, alasan, now))
    db.commit()


# ================= LOAD (WITH USER ID + TIME) =================

def load_absen(chat_id):
    cur.execute("""
        SELECT user_id, name, type, alasan, date
        FROM absen
        WHERE chat_id=?
    """, (chat_id,))
    rows = cur.fetchall()

    data = {"hadir": [], "izin": [], "sakit": []}

    for uid, name, tipe, alasan, time in rows:
        if tipe == "hadir":
            data["hadir"].append((uid, name, time))
        elif tipe == "sakit":
            data["sakit"].append((uid, name, time))
        elif tipe == "izin":
            data["izin"].append((uid, name, alasan, time))

    return data


# ================= FORMAT =================

def format_absen(chat_id):
    data = load_absen(chat_id)
    now = datetime.now(WIB)

    total = len(data["hadir"]) + len(data["izin"]) + len(data["sakit"])

    text = f"""
╔════════════════════════════════╗
       ✦ ATTENDANCE AUTO ABSEN ✦
╚════════════════════════════════╝

📅 {now.strftime('%A, %d %B %Y')}
⏰ {now.strftime('%H:%M')} WIB ABSEN DIBUKA

🟢 HADIR : {status_bar(len(data['hadir']), 1.2)}
🟡 IZIN  : {status_bar(len(data['izin']), 0.8)}
🔴 SAKIT : {status_bar(len(data['sakit']), 0.5)}

👥 TOTAL : {total}
────────────────────────
"""

    # HADIR
    for uid, name, time in data["hadir"]:
        text += f"\n➤ 🟢 [{name}](tg://user?id={uid}) — {time}"

    # IZIN
    for uid, name, alasan, time in data["izin"]:
        text += f"\n➤ 🟡 [{name}](tg://user?id={uid}) ({alasan}) — {time}"

    # SAKIT
    for uid, name, time in data["sakit"]:
        text += f"\n➤ 🔴 [{name}](tg://user?id={uid}) — {time}"

    if total == 0:
        text += "\nBelum ada absensi."

    text += "\n────────────────────────\n⚡ SYSTEM: ACTIVE LIVE SYNC\n🛍 @storegarf"

    return text


# ================= KEYBOARD =================

def get_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 HADIR", callback_data="absen_hadir"),
            InlineKeyboardButton("🟡 IZIN", callback_data="absen_izin"),
            InlineKeyboardButton("🔴 SAKIT", callback_data="absen_sakit"),
        ],
        [
            InlineKeyboardButton("🛍 STORE", url="https://t.me/storegarf")
        ]
    ])


# ================= DAILY RESET =================

def daily_reset(context):
    global last_day

    today = datetime.now(WIB).strftime("%Y-%m-%d")

    if last_day == today:
        return

    debug("DAILY RESET TRIGGERED")

    chats = cur.execute("SELECT DISTINCT chat_id FROM absen").fetchall()

    for (chat_id,) in chats:
        try:
            context.bot.send_message(chat_id, "📊 REKAP HARI KEMARIN\n\n" + format_absen(chat_id), parse_mode="Markdown")
        except:
            pass

    cur.execute("DELETE FROM absen")
    db.commit()

    last_day = today


# ================= WEEKLY =================

def weekly_report(context):
    global last_week

    now = datetime.now(WIB)
    week = now.strftime("%Y-%W")

    if last_week == week:
        return

    chats = cur.execute("SELECT DISTINCT chat_id FROM absen").fetchall()

    for (chat_id,) in chats:
        try:
            cur.execute("""
                SELECT name, COUNT(*)
                FROM absen
                WHERE chat_id=? AND type='hadir'
                GROUP BY user_id
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """, (chat_id,))

            rows = cur.fetchall()

            text = "🏆 RANKING MINGGUAN\n\n"

            if not rows:
                text += "Belum ada data."
            else:
                for i, (name, total) in enumerate(rows, 1):
                    text += f"{i}. {name} - {total}x hadir\n"

            context.bot.send_message(chat_id, text)

        except:
            traceback.print_exc()

    last_week = week


# ================= REFRESH =================

def refresh_job(context):
    chat_id = context.job.context

    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=absen_msg.get(chat_id),
            text=format_absen(chat_id),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass


def start_refresh_job(context, chat_id):
    if chat_id in job_refresh:
        job_refresh[chat_id].schedule_removal()

    job_refresh[chat_id] = context.job_queue.run_repeating(
        refresh_job,
        interval=5,
        first=0,
        context=chat_id
    )


# ================= COMMAND =================

def absen_cmd(update, context):
    daily_reset(context)

    chat_id = update.effective_chat.id

    msg = update.message.reply_text(
        format_absen(chat_id),
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )

    absen_msg[chat_id] = msg.message_id

    start_refresh_job(context, chat_id)

    try:
        context.bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
    except:
        pass

    debug(f"/absen OK {chat_id}")


# ================= BUTTON =================

def absen_button(update, context):
    query = update.callback_query
    query.answer()

    daily_reset(context)

    user = query.from_user
    chat_id = query.message.chat.id

    data = query.data.split("_")[1]

    cur.execute("SELECT 1 FROM absen WHERE chat_id=? AND user_id=?", (chat_id, user.id))
    if cur.fetchone():
        return query.answer("❌ Sudah absen", show_alert=True)

    if data == "hadir":
        save_absen(chat_id, user.id, user.first_name, "hadir")

    elif data == "sakit":
        save_absen(chat_id, user.id, user.first_name, "sakit")

    elif data == "izin":
        pending_izin[user.id] = chat_id
        return query.message.reply_text("🟡 Kirim alasan izin:")

    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=absen_msg.get(chat_id),
            text=format_absen(chat_id),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
    except:
        traceback.print_exc()


# ================= IZIN =================

def izin_handler(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id not in pending_izin:
        return

    if pending_izin[user.id] != chat_id:
        return

    save_absen(chat_id, user.id, user.first_name, "izin", update.message.text)

    del pending_izin[user.id]

    debug(f"IZIN SAVED {user.id}")


# ================= REGISTER =================

def register_absen(app):
    debug("ABSEN MODULE LOADED")

    app.add_handler(CommandHandler("absen", absen_cmd))
    app.add_handler(CallbackQueryHandler(absen_button, pattern="absen_"))
    app.add_handler(MessageHandler(Filters.text & ~Filters.command, izin_handler))
