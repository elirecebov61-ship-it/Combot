import os
import logging
import pg8000.native
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    """DATABASE_URL-dən bağlantı aç"""
    u = urlparse(DATABASE_URL)
    return pg8000.native.Connection(
        host     = u.hostname,
        port     = u.port or 5432,
        database = u.path.lstrip("/"),
        user     = u.username,
        password = u.password,
        ssl_context = True   # Railway PostgreSQL SSL tələb edir
    )


def init_db():
    conn = get_db()
    conn.run("""
        CREATE TABLE IF NOT EXISTS group_stats (
            chat_id    BIGINT PRIMARY KEY,
            chat_title TEXT,
            msg_count  BIGINT DEFAULT 0
        )
    """)
    conn.close()
    logger.info("✅ DB hazırdır")


def increment_count(chat_id: int, chat_title: str):
    conn = get_db()
    conn.run("""
        INSERT INTO group_stats (chat_id, chat_title, msg_count)
        VALUES (:chat_id, :title, 1)
        ON CONFLICT (chat_id) DO UPDATE
        SET msg_count  = group_stats.msg_count + 1,
            chat_title = EXCLUDED.chat_title
    """, chat_id=chat_id, title=chat_title)
    conn.close()


def get_stats(chat_id: int):
    conn = get_db()
    rows = conn.run(
        "SELECT chat_title, msg_count FROM group_stats WHERE chat_id = :cid",
        cid=chat_id
    )
    conn.close()
    return rows[0] if rows else None   # [chat_title, msg_count]


# ── Komandalar ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass   # heç nə yazmır


async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Bu komut sadece gruplarda çalışır.")
        return

    row = get_stats(chat.id)
    if not row:
        await update.message.reply_text("Hələ heç bir mesaj qeydə alınmayıb.")
        return

    group_name = row[0] or chat.title or "Qrup"
    count      = row[1]

    await update.message.reply_text(f"{group_name} 💬\n{count}")


async def count_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type in ["group", "supergroup"]:
        increment_count(chat.id, chat.title or "")


# ── Main ─────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tapılmadı!")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL tapılmadı!")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", stat))
    app.add_handler(MessageHandler(~filters.COMMAND, count_messages))

    logger.info("🤖 Bot işə düşdü")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
