import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
import json
import os
import asyncio
from aiohttp import web
import aiohttp

# Настройки
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Config:
    TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"  # <-- Вставь свой токен
    ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317, -1002497927834]
    SUGGESTIONS_FILE = "suggestions.json"
    MAX_ITEMS = 10

class Texts:
    WELCOME = "Добро пожаловать в бот для предложений!"
    SELECT_CATEGORY = "Выберите категорию:"
    INVALID_CATEGORY = "Пожалуйста, выберите категорию из списка!"
    CATEGORY_MESSAGES = {
        "Розыгрыши": "Категория: <b>Розыгрыши</b>\nОтправьте детали розыгрыша.\nНажмите <b>✅ Подтвердить</b> после завершения",
        "Реклама": "Категория: <b>Реклама</b>\nПрикрепите рекламные материалы.\nНажмите <b>✅ Подтвердить</b> после загрузки",
        "Заявки": "Категория: <b>Заявки</b>\nОпишите, что вам нужно.\nПосле завершения нажмите <b>✅ Подтвердить</b>",
        "Предложения": "Категория: <b>Предложения</b>\nОпишите идею или улучшение.\nПосле окончания нажмите <b>✅ Подтвердить</b>"
    }
    CANCELLED = "Создание предложения отменено"
    ADD_MORE = "Текущее количество элементов: {count}"
    ELEMENT_ADDED = "Элемент {count}/{max} добавлен!"
    LIMIT_REACHED = "Достигнут лимит элементов. Нажмите ✅ Подтвердить"
    INVALID_CONTENT = "Пожалуйста, отправьте допустимый контент."
    CONFIRM_EMPTY = "Добавьте хотя бы один элемент!"
    SUGGESTION_SENT = "✅ Ваше предложение успешно отправлено!"
    YOUR_SUGGESTIONS_EMPTY = "У вас пока нет отправленных предложений"
    YOUR_SUGGESTIONS = "📂 Ваши последние предложения:\n\n"
    SUGGESTION_ADMIN_HEAD = "📨 Новое предложение ({category}) от @{username}"

class SuggestionStates(StatesGroup):
    WAITING_CATEGORY = State()
    COLLECTING_CONTENT = State()

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
            ], resize_keyboard=True
        )

    @staticmethod
    def categories():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Розыгрыши")],
                [KeyboardButton(text="Заявки")],
                [KeyboardButton(text="Реклама")],
                [KeyboardButton(text="Предложения")]
            ], resize_keyboard=True
        )

    @staticmethod
    def confirm():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Подтвердить"), KeyboardButton(text="➕ Добавить")],
                [KeyboardButton(text="❌ Отменить")]
            ], resize_keyboard=True
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

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(Texts.WELCOME, reply_markup=Keyboards.main())

@dp.message(F.text == "📝 Создать предложение")
async def start_suggestion(message: types.Message, state: FSMContext):
    await state.set_state(SuggestionStates.WAITING_CATEGORY)
    await message.answer(Texts.SELECT_CATEGORY, reply_markup=Keyboards.categories())

@dp.message(SuggestionStates.WAITING_CATEGORY)
async def select_category(message: types.Message, state: FSMContext):
    if message.text not in Texts.CATEGORY_MESSAGES:
        return await message.answer(Texts.INVALID_CATEGORY)
    await state.update_data(category=message.text, items=[], count=0)
    await state.set_state(SuggestionStates.COLLECTING_CONTENT)
    await message.answer(Texts.CATEGORY_MESSAGES[message.text], reply_markup=Keyboards.confirm(), parse_mode="HTML")

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "❌ Отменить")
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(Texts.CANCELLED, reply_markup=Keyboards.main())

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "✅ Подтвердить")
async def confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("items"):
        return await message.answer(Texts.CONFIRM_EMPTY)

    suggestion = {
        "category": data["category"],
        "items": data["items"],
        "author": {"id": message.from_user.id, "username": message.from_user.username},
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, Texts.SUGGESTION_ADMIN_HEAD.format(
                category=suggestion['category'], username=suggestion['author']['username']))
            for item in suggestion["items"]:
                if item["type"] == "text":
                    await bot.send_message(admin_id, item["data"])
                elif item["type"] == "photo":
                    await bot.send_photo(admin_id, item["file_id"], caption=item.get("caption", ""))
                elif item["type"] == "document":
                    await bot.send_document(admin_id, item["file_id"], caption=item.get("caption", ""))
                elif item["type"] == "video":
                    await bot.send_video(admin_id, item["file_id"], caption=item.get("caption", ""))
        except Exception as e:
            logger.exception(f"Ошибка отправки админу {admin_id}: {e}")

    SuggestionManager.save(suggestion)
    await state.clear()
    await message.answer(Texts.SUGGESTION_SENT, reply_markup=Keyboards.main())

@dp.message(SuggestionStates.COLLECTING_CONTENT, F.text == "➕ Добавить")
async def add_more(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(Texts.ADD_MORE.format(count=data.get("count", 0)))

@dp.message(SuggestionStates.COLLECTING_CONTENT)
async def collect_item(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    count = data.get("count", 0)

    if count >= Config.MAX_ITEMS:
        return await message.answer(Texts.LIMIT_REACHED)

    item = None
    if message.text and message.text not in ["✅ Подтвердить", "➕ Добавить", "❌ Отменить"]:
        item = {"type": "text", "data": message.text}
    elif message.photo:
        item = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption}
    elif message.document:
        item = {"type": "document", "file_id": message.document.file_id, "caption": message.caption}
    elif message.video:
        item = {"type": "video", "file_id": message.video.file_id, "caption": message.caption}

    if item:
        items.append(item)
        count += 1
        await state.update_data(items=items, count=count)
        await message.answer(Texts.ELEMENT_ADDED.format(count=count, max=Config.MAX_ITEMS), reply_markup=Keyboards.confirm())
    else:
        await message.answer(Texts.INVALID_CONTENT, reply_markup=Keyboards.confirm())

@dp.message(F.text == "📋 Мои предложения")
async def my_suggestions(message: types.Message):
    suggestions = [s for s in SuggestionManager.load() if s["author"]["id"] == message.from_user.id][-5:]
    if not suggestions:
        return await message.answer(Texts.YOUR_SUGGESTIONS_EMPTY)

    text = Texts.YOUR_SUGGESTIONS
    for i, s in enumerate(reversed(suggestions), 1):
        text += f"{i}. <b>{s['category']}</b> ({s['date']})\nЭлементов: {len(s['items'])}\n\n"
    await message.answer(text, parse_mode="HTML")

async def handle(request):
    return web.Response(text="<h1>404</h1>", content_type="text/html")

async def start_web_app():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_route("*", "/{tail:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

async def anti_sleep_task():
    url = "https://api.open-meteo.com/v1/forecast?latitude=50.45&longitude=30.52&current_weather=true"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    await resp.text()
        except Exception as e:
            print(f"Ошибка антиспячки: {e}")
        await asyncio.sleep(10)

async def main():
    try:
        await asyncio.gather(
            anti_sleep_task(),
            start_web_app(),
            dp.start_polling(bot)
        )
    except Exception as e:
        logging.exception("Ошибка в одной из задач")

if __name__ == "__main__":
    asyncio.run(main())
