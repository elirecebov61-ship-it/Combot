import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Railway environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    """PostgreSQL bağlantısı aç"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Cədvəli yarat (əgər yoxdursa)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_stats (
            chat_id     BIGINT PRIMARY KEY,
            chat_title  TEXT,
            msg_count   BIGINT DEFAULT 0
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ DB hazırdır")


def increment_count(chat_id: int, chat_title: str):
    """Mesaj sayını 1 artır, qrup yoxdursa yarat"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO group_stats (chat_id, chat_title, msg_count)
        VALUES (%s, %s, 1)
        ON CONFLICT (chat_id) DO UPDATE
        SET msg_count  = group_stats.msg_count + 1,
            chat_title = EXCLUDED.chat_title
    """, (chat_id, chat_title))
    conn.commit()
    cur.close()
    conn.close()


def get_stats(chat_id: int):
    """Qrupun adını və mesaj sayını qaytar"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT chat_title, msg_count FROM group_stats WHERE chat_id = %s",
        (chat_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row  # {"chat_title": ..., "msg_count": ...} və ya None


# ── Komandalar ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - heç nə etmir
    """
    pass


async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /stat - qrup adı 💬 + mesaj sayı
    """
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Bu komanda yalnız qruplarda işləyir.")
        return

    row = get_stats(chat.id)
    if not row:
        await update.message.reply_text("Hələ heç bir mesaj qeydə alınmayıb.")
        return

    group_name = row["chat_title"] or chat.title or "Qrup"
    count = row["msg_count"]

    await update.message.reply_text(f"{group_name} 💬\n{count}")


async def count_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hər mesajı DB-yə yaz"""
    chat = update.effective_chat
    if chat and chat.type in ["group", "supergroup"]:
        increment_count(chat.id, chat.title or "")


# ── Main ─────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable tapılmadı!")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable tapılmadı!")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", stat))
    app.add_handler(MessageHandler(~filters.COMMAND, count_messages))

    logger.info("🤖 Bot işə düşdü")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
