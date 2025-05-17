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
import os
import json

# Настройки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0"
ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317]
SUGGESTIONS_FILE = "suggestions.json"

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Категории
CATEGORIES = {
    'contest': 'Конкурс',
    'coming_soon': 'Скоро',
    'other': 'Другое'
}

# Состояния
class Form(StatesGroup):
    waiting_category = State()
    collecting_content = State()

# Загрузка/сохранение данных
def load_suggestions():
    if os.path.exists(SUGGESTIONS_FILE):
        with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_suggestion(suggestion):
    data = load_suggestions()
    data.append(suggestion)
    with open(SUGGESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Клавиатуры
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать предложение")],
            [KeyboardButton(text="Мои предложения")]
        ],
        resize_keyboard=True
    )

def categories_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in CATEGORIES.values()],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True
    )

# Обработчики
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "📝 Бот для предложений\nВыберите действие:",
        reply_markup=main_kb()
    )

@dp.message(F.text == "Создать предложение")
async def create_suggestion(message: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_category)
    await message.answer(
        "Выберите категорию:",
        reply_markup=categories_kb()
    )

@dp.message(Form.waiting_category)
async def process_category(message: types.Message, state: FSMContext):
    if message.text not in CATEGORIES.values():
        await message.answer("Выберите категорию из списка!")
        return

    await state.update_data(category=message.text, items=[])
    await state.set_state(Form.collecting_content)
    await message.answer(
        f"Категория: {message.text}\nОтправьте текст или файл:",
        reply_markup=cancel_kb()
    )

@dp.message(Form.collecting_content, F.text == "❌ Отменить")
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено", reply_markup=main_kb())

@dp.message(Form.collecting_content)
async def process_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get('items', [])
    
    # Обработка разных типов контента
    content = {'type': 'text', 'data': message.text} if message.text else None
    
    if message.photo:
        content = {
            'type': 'photo',
            'file_id': message.photo[-1].file_id,
            'caption': message.caption
        }
    elif message.document:
        content = {
            'type': 'document',
            'file_id': message.document.file_id,
            'caption': message.caption
        }
    elif message.video:
        content = {
            'type': 'video',
            'file_id': message.video.file_id,
            'caption': message.caption
        }

    if content:
        items.append(content)
        await state.update_data(items=items)
        
        # Автоподтверждение при 5 элементах
        if len(items) >= 5:
            await confirm_suggestion(message, state)
        else:
            await message.answer(
                f"Добавлено ({len(items)}/5). Отправьте ещё или нажмите '❌ Отменить'",
                reply_markup=cancel_kb()
            )
    else:
        await message.answer("Отправьте текст или файл")

async def confirm_suggestion(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Формируем предложение
    suggestion = {
        'category': data['category'],
        'items': data['items'],
        'author': {
            'id': message.from_user.id,
            'username': message.from_user.username
        },
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Отправка админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📨 Новое предложение ({suggestion['category']}) от @{suggestion['author']['username']}"
            )
            for item in suggestion['items']:
                if item['type'] == 'text':
                    await bot.send_message(admin_id, item['data'])
                elif item['type'] == 'photo':
                    await bot.send_photo(admin_id, item['file_id'], caption=item.get('caption'))
                elif item['type'] == 'document':
                    await bot.send_document(admin_id, item['file_id'], caption=item.get('caption'))
                elif item['type'] == 'video':
                    await bot.send_video(admin_id, item['file_id'], caption=item.get('caption'))
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")

    # Сохраняем
    save_suggestion(suggestion)
    await message.answer(
        "✅ Предложение отправлено!",
        reply_markup=main_kb()
    )
    await state.clear()

@dp.message(F.text == "Мои предложения")
async def show_my_suggestions(message: types.Message):
    user_suggestions = [
        s for s in load_suggestions()
        if s['author']['id'] == message.from_user.id
    ][-5:]  # Последние 5

    if not user_suggestions:
        await message.answer("У вас пока нет предложений")
        return

    response = "Ваши последние предложения:\n\n"
    for i, sugg in enumerate(user_suggestions, 1):
        response += f"{i}. {sugg['category']} ({sugg['date']})\n"
        for item in sugg['items'][:3]:  # Первые 3 элемента
            if item['type'] == 'text':
                response += f"   - {item['data'][:50]}...\n"
            else:
                response += f"   - [{item['type'].upper()}]\n"
    
    await message.answer(response, reply_markup=main_kb())

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
