import os
import logging
import asyncpg
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

db_pool = None


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_stats (
                chat_id     BIGINT PRIMARY KEY,
                chat_title  TEXT,
                msg_count   BIGINT DEFAULT 0
            )
        """)
    logger.info("✅ DB hazırdır")


async def increment_count(chat_id: int, chat_title: str):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO group_stats (chat_id, chat_title, msg_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (chat_id) DO UPDATE
            SET msg_count  = group_stats.msg_count + 1,
                chat_title = EXCLUDED.chat_title
        """, chat_id, chat_title)


async def get_stats(chat_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT chat_title, msg_count FROM group_stats WHERE chat_id = $1",
            chat_id
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Bu komut sadece gruplarda çalışır.")
        return

    row = await get_stats(chat.id)
    if not row:
        await update.message.reply_text("Şu ana Kadar Hiçbir Atılmadı.")
        return

    group_name = row["chat_title"] or chat.title or "Qrup"
    count = row["msg_count"]

    await update.message.reply_text(f"{group_name} 💬\n{count}")


async def count_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type in ["group", "supergroup"]:
        await increment_count(chat.id, chat.title or "")


async def post_init(app: Application):
    await init_db()


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tapılmadı!")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL tapılmadı!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stat", stat))
    app.add_handler(MessageHandler(~filters.COMMAND, count_messages))

    logger.info("🤖 Bot işə düşdü")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
