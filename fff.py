from aiogram.filters import or_f
from aiogram.filters import Command
from aiogram import Fimport logging
import asyncio
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    FSInputFile, 
    CallbackQuery,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN = '7808934270:AAGlSHM-28yONArUi_Ppy2IdA4nRTz53vn0'  # Замените на ваш токен
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ID администраторов, которые будут получать предложения
ADMIN_IDS = [8044034497, 7111844170, 2112777450, 7945702317, -1002497927834]  # Замените на ID администраторов

# Категории предложений
CATEGORIES = {
    'contest': 'Конкурс',
    'coming_soon': 'Скоро',
    'other': 'Другое'
}

# Определение состояний FSM
class SuggestionStates(StatesGroup):
    waiting_for_category = State()
    collecting_content = State()
    waiting_for_confirmation = State()

# Клавиатура для выбора категории
def get_category_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=value, callback_data=f"category_{key}")]
        for key, value in CATEGORIES.items()
    ])
    return keyboard

# Клавиатура для подтверждения отправки
def get_confirmation_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить отправку")],
            [KeyboardButton(text="➕ Добавить еще")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для сбора предложений. Используйте /suggest чтобы отправить предложение."
    )

# Обработчик команды /suggest
@dp.message(Command("suggest"))
async def cmd_suggest(message: types.Message, state: FSMContext):
    await state.set_state(SuggestionStates.waiting_for_category)
    await message.answer(
        "Выберите категорию вашего предложения:",
        reply_markup=get_category_keyboard()
    )

# Обработчик выбора категории
@dp.callback_query(lambda c: c.data.startswith('category_'))
async def process_category(callback: CallbackQuery, state: FSMContext):
    category_key = callback.data.split('_')[1]
    category_name = CATEGORIES[category_key]
    
    await state.update_data(
        category_key=category_key, 
        category_name=category_name,
        content_items=[]  # Список для хранения собранного контента
    )
    await state.set_state(SuggestionStates.collecting_content)
    
    await callback.answer()
    await callback.message.answer(
        f"Вы выбрали категорию: {category_name}\n\n"
        "Теперь отправляйте ваши предложения. Вы можете отправить текст, фото, видео, документ, "
        "голосовое сообщение, стикер или любую комбинацию этого.\n\n"
        "Отправляйте файлы по очереди. Когда закончите, используйте команду /confirm для подтверждения отправки."
    )

# Функция для сохранения контентного элемента
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
        f"✅ {content_type.capitalize()} сохранен. Всего элементов: {len(content_items)}.\n"
        "Отправьте еще содержимое или используйте /confirm для завершения и отправки.",
        reply_markup=get_confirmation_keyboard()
    )
    
    # Если это первый элемент, переводим в состояние ожидания подтверждения
    if len(content_items) == 1:
        await state.set_state(SuggestionStates.waiting_for_confirmation)

# Обработчики разных типов сообщений в состоянии сбора контента

# Текстовые сообщения
@dp.message(SuggestionStates.collecting_content, lambda message: message.text)
async def collect_text(message: types.Message, state: FSMContext):
    await save_content_item(message, state, 'text', text=message.text)

@dp.message(SuggestionStates.waiting_for_confirmation, lambda message: message.text)
async def collect_more_text(message: types.Message, state: FSMContext):
    if message.text == "✅ Подтвердить отправку" or message.text == "/confirm":
        await confirm_submission(message, state)
    elif message.text == "➕ Добавить еще":
        await message.answer("Отправьте еще один элемент для вашего предложения.")
    elif message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    else:
        await save_content_item(message, state, 'text', text=message.text)

# Фото сообщения
@dp.message(lambda message: message.photo)
async def collect_photo(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        photo_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        await save_content_item(message, state, 'photo', file_id=photo_id, caption=caption)

# Видео сообщения
@dp.message(lambda message: message.video)
async def collect_video(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        video_id = message.video.file_id
        caption = message.caption if message.caption else ""
        await save_content_item(message, state, 'video', file_id=video_id, caption=caption)

# Документы
@dp.message(lambda message: message.document)
async def collect_document(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        document_id = message.document.file_id
        caption = message.caption if message.caption else ""
        await save_content_item(message, state, 'document', file_id=document_id, caption=caption)

# Голосовые сообщения
@dp.message(lambda message: message.voice)
async def collect_voice(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        voice_id = message.voice.file_id
        await save_content_item(message, state, 'voice', file_id=voice_id)

# Аудио файлы
@dp.message(lambda message: message.audio)
async def collect_audio(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        audio_id = message.audio.file_id
        caption = message.caption if message.caption else ""
        await save_content_item(message, state, 'audio', file_id=audio_id, caption=caption)

# Стикеры
@dp.message(lambda message: message.sticker)
async def collect_sticker(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        sticker_id = message.sticker.file_id
        await save_content_item(message, state, 'sticker', file_id=sticker_id)

# Анимации (GIF)
@dp.message(lambda message: message.animation)
async def collect_animation(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [SuggestionStates.collecting_content.state, SuggestionStates.waiting_for_confirmation.state]:
        animation_id = message.animation.file_id
        caption = message.caption if message.caption else ""
        await save_content_item(message, state, 'animation', file_id=animation_id, caption=caption)

# Обработчик команды /confirm или кнопки подтверждения
@dp.message(
    or_f(
        Command("confirm"),
        F.text == "✅ Подтвердить отправку"
    ),
    SuggestionStates.waiting_for_confirmation
)
async def confirm_submission(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    # ... остальной код
    category_name = user_data['category_name']
    content_items = user_data.get('content_items', [])
    
    if not content_items:
        await message.answer("Вы не отправили ни одного элемента контента. Пожалуйста, отправьте что-нибудь.", 
                           reply_markup=ReplyKeyboardRemove())
        return
    
    # Отправка всех элементов предложения администраторам
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"Новое предложение в категории: {category_name}\n"
            f"От пользователя: {message.from_user.full_name} (ID: {message.from_user.id})\n"
            f"Всего элементов: {len(content_items)}"
        )
        
        # Отправка каждого элемента контента
        for item in content_items:
            content_type = item['content_type']
            caption = item.get('caption', '')
            
            if 'from_user' in item:
                user_info = f"От {item['from_user']['full_name']} (ID: {item['from_user']['id']})"
                if caption:
                    caption = f"{caption}\n\n{user_info}"
                else:
                    caption = user_info
            
            try:
                if content_type == 'text':
                    await bot.send_message(admin_id, item['text'])
                elif content_type == 'photo':
                    await bot.send_photo(admin_id, photo=item['file_id'], caption=caption)
                elif content_type == 'video':
                    await bot.send_video(admin_id, video=item['file_id'], caption=caption)
                elif content_type == 'document':
                    await bot.send_document(admin_id, document=item['file_id'], caption=caption)
                elif content_type == 'voice':
                    await bot.send_voice(admin_id, voice=item['file_id'], caption=caption)
                elif content_type == 'audio':
                    await bot.send_audio(admin_id, audio=item['file_id'], caption=caption)
                elif content_type == 'sticker':
                    await bot.send_sticker(admin_id, sticker=item['file_id'])
                    # Для стикеров отправляем дополнительное сообщение с информацией
                    await bot.send_message(admin_id, f"⬆️ Стикер выше от пользователя")
                elif content_type == 'animation':
                    await bot.send_animation(admin_id, animation=item['file_id'], caption=caption)
                else:
                    await bot.send_message(
                        admin_id,
                        f"Получен контент типа {content_type}, который не может быть корректно обработан."
                    )
            except Exception as e:
                await bot.send_message(
                    admin_id,
                    f"Ошибка при отправке контента типа {content_type}: {str(e)}"
                )
    
    await message.answer(
        f"Спасибо! Ваше предложение из {len(content_items)} элементов было отправлено администраторам.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

# Обработчик для отмены текущей операции
@dp.message(Command("cancel") | F.text == "❌ Отменить")
async def cancel_operation(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Нет активных операций для отмены.")

# Обработчик для команды статистики (только для администраторов)
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        # Здесь можно добавить логику сбора статистики
        await message.answer("Функция статистики будет добавлена в следующих версиях.")
    else:
        await message.answer("У вас нет доступа к этой команде.")

# Обработчик для команды помощи
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🤖 Бот для сбора предложений\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/suggest - Отправить новое предложение\n"
        "/confirm - Подтвердить и отправить собранные элементы\n"
        "/cancel - Отменить текущую операцию\n"
        "/help - Показать это сообщение\n\n"
        "Бот поддерживает различные типы контента: текст, фото, видео, документы, "
        "голосовые сообщения, аудио, стикеры и GIF-анимации.\n\n"
        "Вы можете отправить несколько элементов контента подряд, а затем подтвердить отправку."
    )
    await message.answer(help_text)

# Функция "поддержания в живых"
async def keep_alive():
    while True:
        logging.info(f"Keep-alive ping: {time.strftime('%H:%M:%S')}")
        # Здесь можно добавить любую полезную периодическую задачу
        # Например, очистку старых данных, проверку статуса и т.д.
        await asyncio.sleep(58)  # Выполняем каждую минуту

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "alive"}

async def run_http_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


# Функция запуска бота
async def main():
    keep_alive_task = asyncio.create_task(keep_alive())
    http_server_task = asyncio.create_task(run_http_server())

    try:
        await dp.start_polling(bot)
    finally:
        keep_alive_task.cancel()
        http_server_task.cancel()

        try:
            await keep_alive_task
            await http_server_task
        except asyncio.CancelledError:
            logging.info("Background tasks cancelled.")


if __name__ == '__main__':
    asyncio.run(main())
