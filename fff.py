import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    FSInputFile
)
import json
import os
import asyncio
from aiohttp import web

# Настройки
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Config:
    TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"
    ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317]
    SUGGESTIONS_FILE = "suggestions.json"
    MAX_ITEMS = 10  # Максимальное количество элементов в предложении

class SuggestionStates(StatesGroup):
    WAITING_CATEGORY = State()
    COLLECTING_CONTENT = State()

# Инициализация
bot = Bot(token=Config.TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class Keyboards:
    @staticmethod
    def main():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Создать предложение")],
                [KeyboardButton(text="📋 Мои предложения")]
            ],
            resize_keyboard=True
        )

    @staticmethod
    def categories():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Конкурс")],
                [KeyboardButton(text="Скоро")],
                [KeyboardButton(text="Другое")]
            ],
            resize_keyboard=True
        )

    @staticmethod
    def confirm():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Подтвердить"), KeyboardButton(text="➕ Добавить")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )

class SuggestionManager:
    @staticmethod
    def load():
        if os.path.exists(Config.SUGGESTIONS_FILE):
            with open(Config.SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    @staticmethod
    def save(suggestion):
        data = SuggestionManager.load()
        data.append(suggestion)
        with open(Config.SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

# Обработчики
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать в бот для предложений!",
        reply_markup=Keyboards.main()
    )

@dp.message(F.text == "📝 Создать предложение")
async def start_suggestion(message: types.Message, state: FSMContext):
    await state.set_state(SuggestionStates.WAITING_CATEGORY)
    await message.answer(
        "Выберите категорию:",
        reply_markup=Keyboards.categories()
    )

@dp.message(SuggestionStates.WAITING_CATEGORY)
async def select_category(message: types.Message, state: FSMContext):
    if message.text not in ["Конкурс", "Скоро", "Другое"]:
        await message.answer("Пожалуйста, выберите категорию из списка!")
        return

    await state.update_data(
        category=message.text,
        items=[],
        count=0
    )
    await state.set_state(SuggestionStates.COLLECTING_CONTENT)
    await message.answer(
        f"Категория: <b>{message.text}</b>\n\n"
        "Теперь отправляйте:\n"
        "- Текстовые предложения\n"
        "- Фотографии\n"
        "- Документы\n"
        "- Видео\n\n"
        "Когда закончите, нажмите <b>✅ Подтвердить</b>",
        reply_markup=Keyboards.confirm(),
        parse_mode="HTML"
    )

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "❌ Отменить")
async def cancel_suggestion(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Создание предложения отменено",
        reply_markup=Keyboards.main()
    )

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "✅ Подтвердить")
async def confirm_suggestion(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("items"):
        await message.answer("Добавьте хотя бы один элемент перед подтверждением!")
        return

    suggestion = {
        "category": data["category"],
        "items": data["items"],
        "author": {
            "id": message.from_user.id,
            "username": message.from_user.username
        },
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Отправка админам
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📨 Новое предложение ({suggestion['category']}) от @{suggestion['author']['username']}"
            )
            for item in suggestion["items"]:
                if item["type"] == "text":
                    await bot.send_message(admin_id, item["data"])
                elif item["type"] == "photo":
                    await bot.send_photo(
                        admin_id,
                        item["file_id"],
                        caption=item.get("caption", "")
                    )
                elif item["type"] == "document":
                    await bot.send_document(
                        admin_id,
                        item["file_id"],
                        caption=item.get("caption", "")
                    )
                elif item["type"] == "video":
                    await bot.send_video(
                        admin_id,
                        item["file_id"],
                        caption=item.get("caption", "")
                    )

        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")

    SuggestionManager.save(suggestion)
    await state.clear()
    await message.answer(
        "✅ Ваше предложение успешно отправлено!",
        reply_markup=Keyboards.main()
    )

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "➕ Добавить")
async def add_more(message: types.Message, state: FSMContext):
    data = await state.get_data()
    count = data.get("count", 0)
    await message.answer(
        f"Текущее количество элементов: {count}\n"
        "Отправьте следующий элемент:",
        reply_markup=Keyboards.confirm()
    )

@dp.message(SuggestionStates.COLLECTING_CONTENT)
async def process_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    count = data.get("count", 0)

    if count >= Config.MAX_ITEMS:
        await message.answer(
            f"Достигнут лимит ({Config.MAX_ITEMS} элементов). "
            "Нажмите ✅ Подтвердить для отправки",
            reply_markup=Keyboards.confirm()
        )
        return

    content = None
    if message.text and message.text not in ["✅ Подтвердить", "➕ Добавить", "❌ Отменить"]:
        content = {"type": "text", "data": message.text}
    elif message.photo:
        content = {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption
        }
    elif message.document:
        content = {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": message.caption
        }
    elif message.video:
        content = {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption
        }

    if content:
        items.append(content)
        count += 1
        await state.update_data(items=items, count=count)
        await message.answer(
            f"Элемент {count}/{Config.MAX_ITEMS} добавлен!\n"
            "Продолжайте отправлять или нажмите ✅ Подтвердить",
            reply_markup=Keyboards.confirm()
        )
    else:
        await message.answer(
            "Пожалуйста, отправьте:\n"
            "- Текст\n"
            "- Фото\n"
            "- Документ\n"
            "- Видео",
            reply_markup=Keyboards.confirm()
        )

@dp.message(F.text == "📋 Мои предложения")
async def show_user_suggestions(message: types.Message):
    user_suggestions = [
        s for s in SuggestionManager.load()
        if s["author"]["id"] == message.from_user.id
    ][-5:]  # Последние 5 предложений

    if not user_suggestions:
        await message.answer("У вас пока нет отправленных предложений")
        return

    response = "📂 Ваши последние предложения:\n\n"
    for i, sugg in enumerate(reversed(user_suggestions), 1):
        response += (
            f"{i}. <b>{sugg['category']}</b> ({sugg['date']})\n"
            f"Элементов: {len(sugg['items'])}\n\n"
        )

    await message.answer(response, parse_mode="HTML")



async def handle(request):
    return web.Response(text="Bot is alive")

async def start_web_app():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

async def anti_sleep_task():
    while True:
        print("⏳ Anti-sleep ping")  # или просто pass
        await asyncio.sleep(30)  # каждые 5 минут

async def main():
    asyncio.create_task(anti_sleep_task())
    await start_web_app()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
