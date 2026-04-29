import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiohttp import web  # Додано для веб-сервера
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

# ВАШІ ДАНІ
API_TOKEN = '8507313496:AAE-sPawQ0JdJp4heCreq_zJKCDZmLTSy50'

# НАЛАШТУВАННЯ КРАЇН ТА ДНІВ
COUNTRY_RULES = {
    "Туреччина": 183,
    "Єгипет": 183,
    "Туніс": 183,
    "ОАЕ": 183,
    "Таїланд": 183,
    "Греція": 183,
    "Іспанія": 183,
    "Чорногорія": 183,
    "Хорватія": 183,
    "Албанія": 183,
    "Шрі-Ланка": 183
}

logging.basicConfig(level=logging.INFO)
# На Render використовуємо чистий Bot без проксі
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    country = State()
    start_date = State()
    nights = State()

# --- КЛАВІАТУРИ (Твоя логіка) ---

def get_start_keyboard():
    builder = ReplyKeyboardBuilder()
    for country in COUNTRY_RULES.keys():
        builder.add(types.KeyboardButton(text=country))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_restart_button():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🔄 НОВИЙ РОЗРАХУНОК"))
    return builder.as_markup(resize_keyboard=True)

# --- ОБРОБНИКИ (Твоя логіка) ---

@dp.message(F.text == "🔄 НОВИЙ РОЗРАХУНОК")
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Вітаю!\n"
        "Я допоможу Вам перевірити термін дії закордонного паспорта для отримання візи.\n\n"
        "Оберіть країну відпочинку:",
        reply_markup=get_start_keyboard()
    )
    await state.set_state(Form.country)

@dp.message(Form.country)
async def process_country(message: types.Message, state: FSMContext):
    if message.text not in COUNTRY_RULES:
        if message.text == "🔄 НОВИЙ РОЗРАХУНОК":
            await cmd_start(message, state)
            return
        await message.answer("Будь ласка, оберіть країну з кнопок.")
        return
        
    await state.update_data(country=message.text)
    await message.answer(
        f"🌍 Обрано: {message.text}\nТепер оберіть дату початку подорожі на календарі:",
        reply_markup=await SimpleCalendar().start_calendar()
    )
    await state.set_state(Form.start_date)

@dp.callback_query(SimpleCalendarCallback.filter(), Form.start_date)
async def process_simple_calendar(callback_query: types.CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if selected:
        await state.update_data(start_date=date.strftime("%d.%m.%Y"))
        await callback_query.message.answer(
            f"✅ Дата вильоту: {date.strftime('%d.%m.%Y')}\n\n"
            "Скільки ночей Ви плануєте відпочивати?"
        )
        await state.set_state(Form.nights)

@dp.message(Form.nights)
async def process_nights(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введіть тільки число (кількість ночей).")
        return

    user_data = await state.get_data()
    start_dt = datetime.strptime(user_data['start_date'], "%d.%m.%Y")
    nights = int(message.text)
    country = user_data['country']
    buffer_days = COUNTRY_RULES.get(country, 183)
    
    final_dt = start_dt + timedelta(days=nights) + timedelta(days=buffer_days)
    
    result = (
        f"Для отримання візи до країни **{country}** — термін дії паспорта повинен бути не менше ніж до:\n\n"
        f"👉 **{final_dt.strftime('%d.%m.%Y')}**\n\n"
        f"_(Вимога: +{buffer_days} днів з кінця поїздки)_"
    )
    
    await message.answer(result, parse_mode="Markdown")
    await state.clear()
    await message.answer("Бажаєте зробити ще один розрахунок?", reply_markup=get_restart_button())

# --- ТЕХНІЧНА ЧАСТИНА ДЛЯ RENDER ---

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render автоматично надає порт через змінну оточення PORT
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    # Запуск веб-сервера у фоні
    asyncio.create_task(start_web_server())
    
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запустити розрахунок")
    ])
    
    # Цикл для стійкості бота
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Помилка підключення: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
