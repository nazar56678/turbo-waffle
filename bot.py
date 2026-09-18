import asyncio
import logging
import os
import psycopg2
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from yt_dlp import YoutubeDL

# Твой токен бота от @BotFather
TOKEN = "8791026817:AAHKA-a35vyM7b_T_Um3a791Js29uUj5AgI"

# 🛑 ВПИШИ СЮДА СВОЙ TELEGRAM ID (числом)
ADMIN_ID = 5633221424

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Твоя строка подключения к Neon
DATABASE_URL = "postgresql://neondb_owner:npg_lNroC1Si7cbM@ep-empty-river-b5kuwkg6-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# ==========================================
# 🗄 НАСТРОЙКА БАЗЫ ДАННЫХ (Neon / PostgreSQL)
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица счетчиков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
    """)
    cursor.execute(
        "INSERT INTO stats (key, value) VALUES ('downloads_count', 0) ON CONFLICT (key) DO NOTHING"
    )

    # Таблица настроек и рекламы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute(
        "INSERT INTO settings (key, value) VALUES ('ad_text', '📢 Реклама: Наш спонсор — @example') ON CONFLICT (key) DO NOTHING"
    )
    cursor.execute(
        "INSERT INTO settings (key, value) VALUES ('ad_status', 'OFF') ON CONFLICT (key) DO NOTHING"
    )
    cursor.execute(
        "INSERT INTO settings (key, value) VALUES ('loading_ad_photo', '') ON CONFLICT (key) DO NOTHING"
    )

    conn.commit()
    cursor.close()
    conn.close()


def add_user_to_db(user_id: int, username: str, full_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (user_id, username, full_name) 
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """,
        (user_id, username, full_name),
    )
    conn.commit()
    cursor.close()
    conn.close()


def increment_downloads():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stats SET value = value + 1 WHERE key = 'downloads_count'"
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_stats_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT value FROM stats WHERE key = 'downloads_count'")
    row = cursor.fetchone()
    total_downloads = row[0] if row else 0
    
    cursor.close()
    conn.close()
    return total_users, total_downloads


# Инициализация базы при старте
init_db()


def check_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# --- СКАЧИВАНИЕ ВИДЕО (С КУКАМИ И ЗАЩИТОЙ) ---
def download_video_sync(url: str) -> str:
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=mp4]/best[ext=mp4]/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "cookiefile": "cookies.txt",  # Подключение вашего файла с куками
        "socket_timeout": 30,          # Защита от зависаний
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            for ext in [".mp4", ".mkv", ".webm", ".mov"]:
                if os.path.exists(base + ext):
                    filename = base + ext
                    break

        return filename


# --- ОБЫЧНЫЕ КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    add_user_to_db(user.id, user.username, user.full_name)

    welcome_text = (
        "👋 **Привет! Добро пожаловать в бот для скачивания видео.**\n\n"
        "📥 **Что я умею:**\n"
        "• Скачивать ролики из **TikTok** без водяных знаков.\n"
        "• Загружать видео из **YouTube** и **YouTube Shorts**.\n"
        "• Скачивать видео и Reels из **Instagram**.\n\n"
        "🔗 **Как пользоваться:**\n"
        "Просто отправь мне ссылку на видео в чат!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


# ==========================================
# 👑 АДМИН-ПАНЕЛЬ И УПРАВЛЕНИЕ РЕКЛАМОЙ
# ==========================================
@dp.message(Command("admin", "helpadmin"))
async def cmd_admin_panel(message: types.Message):
    if not check_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return

    admin_menu = (
        "👑 **Панель Администратора**\n\n"
        "📊 **Статистика:**\n"
        "• /stats — Точная статистика\n"
        "• /users — Список пользователей\n\n"
        "📢 **Управление рекламой (при загрузке):**\n"
        "• /advert — Статус и текст рекламы\n"
        "• /ad_on — Включить показ рекламы\n"
        "• /ad_off — Выключить рекламу\n"
        "• /setad [текст] — Изменить рекламный текст\n"
        "• /setphoto [ссылка на фото] — Добавить картинку к рекламе"
    )
    await message.answer(admin_menu, parse_mode="Markdown")


@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    users_count, downloads_count = get_stats_from_db()
    await message.answer(
        f"📊 **Статистика бота:**\n\n👤 Пользователей: `{users_count}`\n📥 Скачиваний: `{downloads_count}`",
        parse_mode="Markdown",
    )


@dp.message(Command("users"))
async def admin_users(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, full_name, joined_date FROM users ORDER BY joined_date DESC LIMIT 15"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        await message.answer("👥 В базе пока нет пользователей.")
        return

    text = "👥 **Последние пользователи:**\n\n"
    for row in rows:
        uid, uname, fname, jdate = row
        username_str = f"@{uname}" if uname else "нет юзернейма"
        text += f"• {fname} ({username_str}) — ID: `{uid}`\n"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("advert"))
async def admin_advert_menu(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'ad_status'")
    status = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = 'ad_text'")
    ad_text = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = 'loading_ad_photo'")
    photo_url = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    text = (
        f"📢 **Настройки рекламы при загрузке:**\n\n"
        f"⚙️ Статус: `{'ВКЛЮЧЕНА ✅' if status == 'ON' else 'ВЫКЛЮЧЕНА ❌'}`\n"
        f"📝 Текст: {ad_text}\n"
        f"🖼 Картинка: `{photo_url if photo_url else 'отсутствует'}`"
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("ad_on"))
async def admin_ad_on(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = 'ON' WHERE key = 'ad_status'")
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer("✅ Реклама при ожидании загрузки включена!")


@dp.message(Command("ad_off"))
async def admin_ad_off(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = 'OFF' WHERE key = 'ad_status'")
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer("❌ Реклама при ожидании загрузки выключена.")


@dp.message(Command("setad"))
async def admin_set_ad(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите текст. Пример: `/setad Текст рекламы`")
        return
    new_text = args[1]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET value = %s WHERE key = 'ad_text'", (new_text,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer(f"✅ Рекламный текст обновлен:\n\n{new_text}")


@dp.message(Command("setphoto"))
async def admin_set_photo(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите прямую ссылку на картинку или отправьте ID файла.")
        return
    photo_val = args[1]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET value = %s WHERE key = 'loading_ad_photo'",
        (photo_val,),
    )
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer("✅ Рекламная картинка для загрузки обновлена!")


# ==========================================
# 📥 ОБРАБОТЧИК ССЫЛОК (YouTube, TikTok, Instagram)
# ==========================================
@dp.message(F.text.regexp(r"https?://(?:www\.)?.+"))
async def handle_url(message: types.Message):
    user = message.from_user
    add_user_to_db(user.id, user.username, user.full_name)

    url = message.text.strip()

    # Проверка на фото-карусели TikTok (они не скачиваются через yt-dlp)
    if "/photo/" in url:
        await message.answer(
            "⚠️ Это пост с фотографиями (карусель), а не видео. Бот скачивает только видео!",
            parse_mode="Markdown"
        )
        return

    supported_domains = [
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "vm.tiktok.com",
        "instagram.com",
        "instagr.am",
    ]

    if not any(domain in url for domain in supported_domains):
        await message.answer(
            "⚠️ Пожалуйста, отправь корректную ссылку на **YouTube**, **TikTok** или **Instagram**.",
            parse_mode="Markdown",
        )
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'ad_status'")
    ad_status = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = 'ad_text'")
    ad_text = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = 'loading_ad_photo'")
    ad_photo = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    loading_text = "⏳ **Анализирую ссылку и скачиваю видео...**"
    if ad_status == "ON":
        loading_text += f"\n\n{ad_text}"

    if ad_status == "ON" and ad_photo:
        try:
            status_msg = await message.answer_photo(
                photo=ad_photo, caption=loading_text, parse_mode="Markdown"
            )
        except Exception:
            status_msg = await message.answer(loading_text, parse_mode="Markdown")
    else:
        status_msg = await message.answer(loading_text, parse_mode="Markdown")

    file_path = None

    try:
        file_path = await asyncio.to_thread(download_video_sync, url)

        if not file_path or not os.path.exists(file_path):
            raise Exception("Файл не был создан после скачивания.")

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50:
            if isinstance(status_msg, types.Message):
                await status_msg.edit_text(
                    f"❌ Видео весит **{file_size_mb:.1f} МБ**.\nЛимит Telegram — 50 МБ.",
                    parse_mode="Markdown",
                )
            return

        video_file = types.FSInputFile(file_path)
        await message.answer_video(
            video=video_file, caption="✅ **Вот твое видео!**", parse_mode="Markdown"
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        increment_downloads()

    except Exception as e:
        logging.error(f"Ошибка при обработке ссылки {url}: {e}")
        try:
            await status_msg.edit_text(
                "❌ **Не удалось скачать видео.**\nВозможно, видео удалено или защищено авторскими правами.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logging.error(f"Не удалось удалить временный файл {file_path}: {e}")


@dp.message()
async def handle_other_text(message: types.Message):
    await message.answer(
        "❓ Я не понял это сообщение. Отправь мне **ссылку** на видео из YouTube, TikTok или Instagram!",
        parse_mode="Markdown",
    )


async def main():
    logging.info("Бот запущен и подключен к базе Neon!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем.")
