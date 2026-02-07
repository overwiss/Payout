import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен вашего бота (замените на реальный)
API_TOKEN = 'YOUR_BOT_TOKEN_HERE'

# ID администратора (ваш Telegram ID)
ADMIN_ID = YOUR_ADMIN_TELEGRAM_ID_HERE  # Замените на ваш ID

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния FSM
class ApplicationForm(StatesGroup):
    screenshots = State()  # Сбор скриншотов (1-6)
    wallet = State()       # Кошелек
    confirm = State()      # Подтверждение

# Стартовая команда
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Привет! 🌟 Это бот для подачи заявок на выплату. "
                        "Давай начнем. Отправь мне 1-6 скриншотов (фото). "
                        "Можешь отправлять по одному или все сразу. Когда закончишь, напиши 'готово'.")
    await ApplicationForm.screenshots.set()

# Сбор скриншотов
@dp.message_handler(content_types=['photo'], state=ApplicationForm.screenshots)
async def process_screenshots(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'screenshots' not in data:
            data['screenshots'] = []
        data['screenshots'].append(message.photo[-1].file_id)
        
        if len(data['screenshots']) >= 6:
            await message.reply("Ты отправил максимум 6 скриншотов. Теперь введи адрес криптокошелька.")
            await ApplicationForm.wallet.set()
        else:
            await message.reply(f"Получил скриншот! Всего: {len(data['screenshots'])}. "
                                "Можешь отправить еще или напиши 'готово' для продолжения.")

@dp.message_handler(Text(equals='готово', ignore_case=True), state=ApplicationForm.screenshots)
async def finish_screenshots(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'screenshots' not in data or len(data['screenshots']) < 1:
            await message.reply("Ты не отправил ни одного скриншота! Отправь хотя бы один.")
            return
        await message.reply("Отлично! Теперь введи адрес криптокошелька.")
        await ApplicationForm.wallet.set()

# Сбор кошелька
@dp.message_handler(state=ApplicationForm.wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['wallet'] = message.text
        data['username'] = message.from_user.username or message.from_user.full_name
        
        # Подтверждение
        confirm_text = (f"Проверь данные:\n"
                        f"Скриншотов: {len(data['screenshots'])}\n"
                        f"Кошелек: {data['wallet']}\n"
                        f"Username: @{data['username']}")
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Подтвердить ✅", callback_data="confirm_yes"))
        keyboard.add(InlineKeyboardButton("Отмена ❌", callback_data="confirm_no"))
        
        await message.reply(confirm_text, reply_markup=keyboard)
        await ApplicationForm.confirm.set()

# Обработка подтверждения
@dp.callback_query_handler(Text(startswith='confirm_'), state=ApplicationForm.confirm)
async def confirm_application(callback: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        if callback.data == 'confirm_yes':
            # Отправка админу
            user_id = callback.from_user.id
            username = data['username']
            wallet = data['wallet']
            screenshots = data['screenshots']
            
            media = types.MediaGroup()
            for file_id in screenshots:
                media.attach_photo(types.InputMediaPhoto(file_id))
            
            await bot.send_message(ADMIN_ID, f"Новая заявка от @{username} (ID: {user_id})\nКошелек: {wallet}")
            await bot.send_media_group(ADMIN_ID, media)
            
            # Кнопки для админа
            admin_keyboard = InlineKeyboardMarkup()
            admin_keyboard.add(InlineKeyboardButton("Принять ✅", callback_data=f"accept_{user_id}"))
            admin_keyboard.add(InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{user_id}"))
            
            await bot.send_message(ADMIN_ID, "Действия:", reply_markup=admin_keyboard)
            
            await callback.message.reply("Заявка отправлена! Жди уведомления. 🚀")
        else:
            await callback.message.reply("Заявка отменена. Начни заново с /start.")
        
        await state.finish()
    await callback.answer()

# Обработка решений админа
@dp.callback_query_handler(Text(startswith=['accept_', 'reject_']))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ты не админ! 😎", show_alert=True)
        return
    
    action, user_id = callback.data.split('_')
    user_id = int(user_id)
    
    if action == 'accept':
        await bot.send_message(user_id, "Твоя заявка принята! 💰")
    else:
        await bot.send_message(user_id, "Твоя заявка отклонена. 😔 Попробуй снова.")
    
    await callback.message.edit_text("Решение принято!")
    await callback.answer("Уведомление отправлено.")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)