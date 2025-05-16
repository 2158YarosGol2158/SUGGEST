# Стандартные библиотеки
import asyncio
import json
import logging
import os
import socket
import uuid
from datetime import datetime
from pathlib import Path

# Сторонние библиотеки
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

# Веб-сервер
from aiohttp import web
import aiohttp_jinja2
import jinja2

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
class Config:
    TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"
    SUGGESTIONS_CHAT_ID = -1002497927834
    ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317]
    CATEGORIES = {
        'contest': 'Конкурс',
        'coming_soon': 'Скоро',
        'other': 'Другое'
    }
    WEB_SERVER = {
        'host': '0.0.0.0',
        'port': 8080
    }

# Инициализация бота
bot = Bot(token=Config.TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class SuggestionStates(StatesGroup):
    waiting_for_category = State()
    collecting_content = State()
    waiting_for_confirmation = State()

# Глобальные переменные
suggestions = []
visitors_log = []
app = web.Application()
routes = web.RouteTableDef()

def setup_jinja2():
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader('templates'),
        autoescape=True
    )

def create_keyboards():
    """Фабрика клавиатур"""
    class Keyboards:
        @staticmethod
        def categories():
            buttons = [
                [KeyboardButton(text=name)] 
                for name in Config.CATEGORIES.values()
            ]
            return ReplyKeyboardMarkup(
                keyboard=buttons,
                resize_keyboard=True,
                one_time_keyboard=True
            )

        @staticmethod
        def confirmation():
            return ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Подтвердить отправку")],
                    [KeyboardButton(text="➕ Добавить еще")],
                    [KeyboardButton(text="❌ Отменить")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )

        @staticmethod
        def main_menu():
            return ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Создать предложение")],
                    [KeyboardButton(text="Просмотреть сайт предложений")]
                ],
                resize_keyboard=True
            )
    
    return Keyboards()

keyboards = create_keyboards()

async def save_to_json(data: list, filename: str):
    """Сохранение данных в JSON файл"""
    try:
        async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Error saving to {filename}: {e}")

async def load_from_json(filename: str) -> list:
    """Загрузка данных из JSON файла"""
    try:
        if os.path.exists(filename):
            async with aiofiles.open(filename, 'r', encoding='utf-8') as f:
                return json.loads(await f.read())
        return []
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return []

async def collect_visitor_info(request: web.Request) -> dict:
    """Сбор информации о посетителе"""
    info = {
        "timestamp": datetime.now().isoformat(),
        "ip": request.remote,
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "path": request.path,
        "method": request.method,
        "visitor_id": str(uuid.uuid4())
    }
    visitors_log.append(info)
    if len(visitors_log) > 1000:
        visitors_log.pop(0)
    return info

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    await message.answer(
        "👋 Привет! Я бот для сбора предложений.",
        reply_markup=keyboards.main_menu()
    )

# ... (остальные обработчики сообщений)

@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request: web.Request):
    """Главная страница веб-интерфейса"""
    visitor = await collect_visitor_info(request)
    return {
        "suggestions": suggestions[-20:],  # Последние 20 предложений
        "categories": Config.CATEGORIES,
        "visitor": visitor
    }

def setup_web_templates():
    """Инициализация HTML шаблонов"""
    os.makedirs('templates', exist_ok=True)
    
    templates = {
        'index.html': """
        <!DOCTYPE html>
        <html lang="ru">
        <!-- HTML шаблон главной страницы -->
        </html>
        """,
        'success.html': """
        <!DOCTYPE html>
        <html lang="ru">
        <!-- HTML шаблон страницы успеха -->
        </html>
        """
    }
    
    for name, content in templates.items():
        path = Path('templates') / name
        if not path.exists():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

async def startup():
    """Инициализация при запуске"""
    global suggestions
    suggestions = await load_from_json('suggestions.json')
    setup_web_templates()
    setup_jinja2()
    
    # Настройка маршрутов
    app.add_routes(routes)
    
    # Запуск веб-сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner, 
        Config.WEB_SERVER['host'], 
        Config.WEB_SERVER['port']
    )
    await site.start()
    logger.info(f"Web server started at http://{Config.WEB_SERVER['host']}:{Config.WEB_SERVER['port']}")

async def shutdown():
    """Очистка при завершении"""
    await save_to_json(suggestions, 'suggestions.json')
    await bot.session.close()

async def main():
    """Основная функция"""
    await startup()
    
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
