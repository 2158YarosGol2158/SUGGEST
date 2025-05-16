import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"
ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317]

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Клавиатуры
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать предложение")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )

def get_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

# Состояния
class Form(StatesGroup):
    waiting_for_suggestion = State()

# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для сбора предложений.\n"
        "Нажми кнопку ниже или отправь /help",
        reply_markup=get_main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ Доступные команды:\n"
        "/start - Начать диалог\n"
        "/help - Помощь\n"
        "/cancel - Отменить текущее действие",
        reply_markup=get_main_kb()
    )

@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "отменить")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Действие отменено",
        reply_markup=get_main_kb()
    )

@dp.message(F.text == "Создать предложение")
async def suggest_start(message: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_for_suggestion)
    await message.answer(
        "📝 Напиши свое предложение:",
        reply_markup=get_cancel_kb()
    )

@dp.message(F.text == "Помощь")
async def help_button(message: types.Message):
    await cmd_help(message)

@dp.message(Form.waiting_for_suggestion)
async def process_suggestion(message: types.Message, state: FSMContext):
    suggestion = message.text
    
    # Отправка админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📨 Новое предложение от @{message.from_user.username}:\n\n{suggestion}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    await message.answer(
        "✅ Спасибо! Твое предложение отправлено администраторам.",
        reply_markup=get_main_kb()
    )
    await state.clear()

# Запуск бота
async def main():
    # Порт оставлен для возможных future-расширений
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
