import logging
import json
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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"
SUGGESTIONS_CHAT_ID = -1002497927834
ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317]

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Категории предложений
SUGGESTION_CATEGORIES = {
    'contest': 'Конкурс',
    'coming_soon': 'Скоро', 
    'other': 'Другое'
}

# Состояния FSM
class SuggestionStates(StatesGroup):
    waiting_for_category = State()
    collecting_content = State()
    waiting_for_confirmation = State()

# Хранение предложений
suggestions = []

# Клавиатуры
def get_main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать предложение")],
            [KeyboardButton(text="Пусто")]
        ],
        resize_keyboard=True
    )

def get_categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=name)] for key, name in SUGGESTION_CATEGORIES.items()
        ],
        resize_keyboard=True
    )

def get_confirmation_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить отправку")],
            [KeyboardButton(text="➕ Добавить еще")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для сбора предложений.",
        reply_markup=get_main_menu_kb()
    )

@dp.message(F.text == "Создать предложение")
async def create_suggestion(message: types.Message, state: FSMContext):
    await state.set_state(SuggestionStates.waiting_for_category)
    await message.answer(
        "Выберите категорию:",
        reply_markup=get_categories_kb()
    )

@dp.message(SuggestionStates.waiting_for_category)
async def process_category(message: types.Message, state: FSMContext):
    category_name = message.text
    if category_name not in SUGGESTION_CATEGORIES.values():
        await message.answer("Пожалуйста, выберите категорию из списка.")
        return
    
    await state.update_data(
        category=category_name,
        content=[]
    )
    await state.set_state(SuggestionStates.collecting_content)
    await message.answer(
        f"Категория: {category_name}\nОтправьте ваше предложение:",
        reply_markup=get_confirmation_kb()
    )

@dp.message(SuggestionStates.collecting_content)
async def collect_content(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить отправку":
        await confirm_suggestion(message, state)
    elif message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_menu_kb())
    else:
        # Обработка контента
        data = await state.get_data()
        content = data.get('content', [])
        
        if message.text:
            content.append({'type': 'text', 'data': message.text})
        elif message.photo:
            content.append({'type': 'photo', 'file_id': message.photo[-1].file_id})
        elif message.document:
            content.append({'type': 'document', 'file_id': message.document.file_id})
        
        await state.update_data(content=content)
        await message.answer(
            f"Добавлено! Всего элементов: {len(content)}",
            reply_markup=get_confirmation_kb()
        )

async def confirm_suggestion(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data['category']
    content = data['content']
    
    # Формируем сообщение для админов
    admin_message = f"📢 Новое предложение ({category}):\n"
    for item in content:
        if item['type'] == 'text':
            admin_message += f"\n📝 {item['data']}\n"
    
    # Отправляем админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_message)
            # Отправляем медиафайлы если есть
            for item in content:
                if item['type'] == 'photo':
                    await bot.send_photo(admin_id, item['file_id'])
                elif item['type'] == 'document':
                    await bot.send_document(admin_id, item['file_id'])
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    # Сохраняем предложение
    suggestions.append({
        'category': category,
        'content': content,
        'author': message.from_user.username,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await message.answer(
        "✅ Ваше предложение отправлено!",
        reply_markup=get_main_menu_kb()
    )
    await state.clear()


# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
