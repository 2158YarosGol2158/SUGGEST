import logging
import asyncio
import time
from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN = '7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0'  # Замените на ваш токен
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ID администраторов
ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317, -1002497927834]

# Категории предложений
CATEGORIES = {
    'contest': 'Конкурс',
    'coming_soon': 'Скоро',
    'other': 'Другое'
}

# FSM состояния
class SuggestionStates(StatesGroup):
    waiting_for_category = State()
    collecting_content = State()
    waiting_for_confirmation = State()

# Клавиатура для выбора категории
def get_category_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=value, callback_data=f"category_{key}")]
            for key, value in CATEGORIES.items()
        ]
    )
    return keyboard

# Клавиатура для подтверждения
def get_confirmation_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить отправку")],
            [KeyboardButton(text="➕ Добавить еще")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот для сбора предложений. Используйте /suggest чтобы отправить предложение.")

@dp.message(Command("suggest"))
async def cmd_suggest(message: types.Message, state: FSMContext):
    await state.set_state(SuggestionStates.waiting_for_category)
    await message.answer("Выберите категорию:", reply_markup=get_category_keyboard())

@dp.callback_query(lambda c: c.data.startswith('category_'))
async def process_category(callback: CallbackQuery, state: FSMContext):
    category_key = callback.data.split('_')[1]
    category_name = CATEGORIES[category_key]
    await state.update_data(
        category_key=category_key,
        category_name=category_name,
        content_items=[]
    )
    await state.set_state(SuggestionStates.collecting_content)
    await callback.answer()
    await callback.message.answer(
        f"Вы выбрали: {category_name}\n\n"
        "Теперь отправляйте контент. После этого используйте /confirm."
    )

# Универсальная функция сохранения
async def save_content_item(message: types.Message, state: FSMContext, content_type: str, file_id: str = None, text: str = None, caption: str = None):
    data = await state.get_data()
    content_items = data.get('content_items', [])

    content_item = {
        'content_type': content_type,
        'from_user': {
            'id': message.from_user.id,
            'full_name': message.from_user.full_name,
            'username': message.from_user.username
        }
    }
    if file_id:
        content_item['file_id'] = file_id
    if text:
        content_item['text'] = text
    if caption:
        content_item['caption'] = caption

    content_items.append(content_item)
    await state.update_data(content_items=content_items)

    await message.answer(
        f"✅ {content_type.capitalize()} сохранен. Всего элементов: {len(content_items)}.",
        reply_markup=get_confirmation_keyboard()
    )

    if len(content_items) == 1:
        await state.set_state(SuggestionStates.waiting_for_confirmation)

# Все типы сообщений (пример для текста, остальное аналогично)
@dp.message(SuggestionStates.collecting_content, F.text)
async def collect_text(message: types.Message, state: FSMContext):
    await save_content_item(message, state, 'text', text=message.text)

@dp.message(SuggestionStates.waiting_for_confirmation, F.text)
async def collect_more_text(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить отправку" or message.text == "/confirm":
        await confirm_submission(message, state)
    elif message.text == "➕ Добавить еще":
        await message.answer("Отправьте ещё один элемент.")
    elif message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    else:
        await save_content_item(message, state, 'text', text=message.text)

# Повторяющийся шаблон для других типов контента
async def handle_media(message, state, content_type, file_id, caption=None):
    await save_content_item(message, state, content_type, file_id=file_id, caption=caption)

@dp.message(F.photo)
async def collect_photo(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'photo', file_id=message.photo[-1].file_id, caption=message.caption)

@dp.message(F.video)
async def collect_video(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'video', file_id=message.video.file_id, caption=message.caption)

@dp.message(F.document)
async def collect_document(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'document', file_id=message.document.file_id, caption=message.caption)

@dp.message(F.voice)
async def collect_voice(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'voice', file_id=message.voice.file_id)

@dp.message(F.audio)
async def collect_audio(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'audio', file_id=message.audio.file_id, caption=message.caption)

@dp.message(F.sticker)
async def collect_sticker(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'sticker', file_id=message.sticker.file_id)

@dp.message(F.animation)
async def collect_animation(message: types.Message, state: FSMContext):
    await handle_media(message, state, 'animation', file_id=message.animation.file_id, caption=message.caption)

@dp.message(Command("confirm"))
async def confirm_submission(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category_name = data['category_name']
    content_items = data.get('content_items', [])

    if not content_items:
        await message.answer("Нет контента для отправки.", reply_markup=ReplyKeyboardRemove())
        return

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"Новое предложение в категории: {category_name} от {message.from_user.full_name}")
        for item in content_items:
            ct = item['content_type']
            caption = item.get('caption', '')
            if 'from_user' in item:
                info = f"\n\nОт: {item['from_user']['full_name']} (ID: {item['from_user']['id']})"
                caption = f"{caption}{info}" if caption else info

            try:
                if ct == 'text':
                    await bot.send_message(admin_id, item['text'])
                elif ct == 'photo':
                    await bot.send_photo(admin_id, photo=item['file_id'], caption=caption)
                elif ct == 'video':
                    await bot.send_video(admin_id, video=item['file_id'], caption=caption)
                elif ct == 'document':
                    await bot.send_document(admin_id, document=item['file_id'], caption=caption)
                elif ct == 'voice':
                    await bot.send_voice(admin_id, voice=item['file_id'], caption=caption)
                elif ct == 'audio':
                    await bot.send_audio(admin_id, audio=item['file_id'], caption=caption)
                elif ct == 'sticker':
                    await bot.send_sticker(admin_id, sticker=item['file_id'])
                    await bot.send_message(admin_id, "⬆️ Стикер выше от пользователя.")
                elif ct == 'animation':
                    await bot.send_animation(admin_id, animation=item['file_id'], caption=caption)
            except Exception as e:
                await bot.send_message(admin_id, f"Ошибка при отправке: {ct}\n{str(e)}")

    await message.answer("✅ Предложение отправлено!", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_operation(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("📊 Статистика скоро будет доступна.")
    else:
        await message.answer("❌ Нет доступа к статистике.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🤖 Бот для сбора предложений\n"
        "/start – запуск\n"
        "/suggest – новое предложение\n"
        "/confirm – подтверждение\n"
        "/cancel – отмена\n"
        "/help – помощь"
    )

# Keep alive
async def keep_alive():
    while True:
        logging.info(f"Ping: {time.strftime('%H:%M:%S')}")
        await asyncio.sleep(58)

# FastAPI сервер
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive"}

async def run_http_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# Основной запуск
async def main():
    keep_alive_task = asyncio.create_task(keep_alive())
    http_server_task = asyncio.create_task(run_http_server())
    try:
        await dp.start_polling(bot)
    finally:
        keep_alive_task.cancel()
        http_server_task.cancel()
        await keep_alive_task
        await http_server_task

if __name__ == "__main__":
    asyncio.run(main())
