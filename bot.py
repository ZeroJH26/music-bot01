#!/usr/bin/env python3
import logging
import os
import shutil

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    ALLOWED_USERS,
    AUDIO_QUALITY,
    BOT_TOKEN,
    DOWNLOADS_DIR,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
)
from downloader import MusicDownloader
from spotify import get_track_query, is_spotify_url

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

dl = MusicDownloader(output_dir=DOWNLOADS_DIR, quality=AUDIO_QUALITY)


def _allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or str(user_id) in ALLOWED_USERS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f3b5 <b>Музыкальный бот</b>\n\n"
        "Просто отправь название трека или ссылку:\n"
        "• YouTube\n"
        "• SoundCloud\n"
        "• Spotify\n\n"
        "Пришлю MP3 в 320 kbps с обложкой.\n\n"
        "Используй /help для подробностей.",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Как использовать:</b>\n\n"
        "\U0001f50d <b>Поиск по названию:</b>\n"
        "<code>Eminem - Lose Yourself</code>\n\n"
        "\U0001f517 <b>Прямые ссылки:</b>\n"
        "<code>https://youtube.com/watch?v=…</code>\n"
        "<code>https://soundcloud.com/…</code>\n"
        "<code>https://open.spotify.com/track/…</code>\n\n"
        "⚙️ Качество: <b>320 kbps MP3</b> с обложкой и метаданными.",
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    text = update.message.text.strip()
    if not text:
        return

    status = await update.message.reply_text("\U0001f50d Ищу трек…")
    result = None

    try:
        if is_spotify_url(text):
            await status.edit_text("\U0001f3b5 Получаю информацию с Spotify…")
            track = await get_track_query(text, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            if not track:
                await status.edit_text("❌ Не удалось получить данные о треке.")
                return
            query = track["search_query"]
            await status.edit_text(f"\U0001f4e5 Скачиваю: <b>{query}</b>…", parse_mode="HTML")
            result = await dl.search_and_download(query)
            if result and not result.get("error"):
                if track.get("title"):
                    result["title"] = track["title"]
                if track.get("artist"):
                    result["artist"] = track["artist"]

        elif text.startswith(("http://", "https://")):
            await status.edit_text("\U0001f4e5 Скачиваю…")
            result = await dl.download_url(text)

        else:
            await status.edit_text(f"\U0001f50d Ищу: <b>{text}</b>…", parse_mode="HTML")
            result = await dl.search_and_download(text)

        if not result:
            await status.edit_text("❌ Трек не найден или произошла ошибка.")
            return

        if result.get("error") == "too_large":
            await status.edit_text("❌ Файл слишком большой для отправки (>50 MB).")
            return

        await status.edit_text("\U0001f4e4 Отправляю…")
        with open(result["path"], "rb") as f:
            await update.message.reply_audio(
                audio=f,
                title=result["title"],
                performer=result["artist"],
                duration=result["duration"] or None,
            )

        await status.delete()

    except Exception:
        logger.exception("Error while handling message")
        await status.edit_text("❌ Произошла ошибка. Попробуй ещё раз.")
    finally:
        if result and result.get("path"):
            dl.cleanup(result["path"])


def main():
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("ffmpeg not found — install it before running the bot")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    port = int(os.getenv("PORT", "8080"))

    if webhook_url:
        logger.info(f"Webhook mode: {webhook_url}/webhook on port {port}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook",
            webhook_url=f"{webhook_url}/webhook",
            drop_pending_updates=True,
        )
    else:
        logger.info("Polling mode")
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
