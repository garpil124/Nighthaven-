import zipfile
import os
import time
import threading
from datetime import datetime, timedelta

PARTNER_FILE = "partner.json22"
SETTING_FILE = "setting.json7"
LOG_GROUP_ID = -1003850930583

bot = None

# ================= SET TIMEZONE =================
os.environ["TZ"] = "Asia/Jakarta"
try:
    time.tzset()
except:
    pass

# ================= WAIT TIME =================
def wait_until(hour, minute=0):
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    time.sleep((target - now).total_seconds())

# ================= CREATE BACKUP =================
def create_backup():
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    with zipfile.ZipFile(name, 'w') as z:
        if os.path.exists(PARTNER_FILE):
            z.write(PARTNER_FILE)

        if os.path.exists(SETTING_FILE):
            z.write(SETTING_FILE)

        if os.path.exists("database7"):
            for root, dirs, files in os.walk("database7"):
                for file in files:
                    z.write(os.path.join(root, file))

    return name

# ================= AUTO BACKUP =================
def backup_daily():
    while True:
        wait_until(7, 0)

        try:
            file = create_backup()

            with open(file, "rb") as f:
                bot.send_document(
                    chat_id=LOG_GROUP_ID,
                    document=f,
                    caption="📦 BACKUP HARIAN (07:00 WIB)"
                )

            os.remove(file)

        except Exception as e:
            print("❌ BACKUP ERROR:", e)
            try:
                bot.send_message(LOG_GROUP_ID, f"❌ BACKUP ERROR\n{e}")
            except:
                pass

# ================= AUTO RESTART =================
def restart_daily():
    while True:
        wait_until(0, 0)

        try:
            file = create_backup()

            with open(file, "rb") as f:
                bot.send_document(
                    chat_id=LOG_GROUP_ID,
                    document=f,
                    caption="📦 BACKUP SEBELUM RESTART (00:00 WIB)"
                )

            os.remove(file)

        except Exception as e:
            print("❌ RESTART BACKUP ERROR:", e)
            try:
                bot.send_message(LOG_GROUP_ID, f"❌ RESTART BACKUP ERROR\n{e}")
            except:
                pass

        print("🔄 RESTART BOT")

        # 🔥 RESTART BOT
        os.execv("/root/autobot/venv/bin/python", ["python", "/root/autobot/bot1.py"])

# ================= START SYSTEM =================
def start_system(bot_instance):
    global bot
    bot = bot_instance

    print("📦 SYSTEM BACKUP AKTIF")

    threading.Thread(target=backup_daily, daemon=True).start()
    threading.Thread(target=restart_daily, daemon=True).start()
