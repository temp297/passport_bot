import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

# ВАШІ ДАНІ
API_TOKEN = os.getenv("API_TOKEN")

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
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    country = State()
    start_date = State()
    nights = State()

# --- КЛАВІАТУРИ (Inline) ---

def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    for country in COUNTRY_RULES.keys():
        builder.add(types.InlineKeyboardButton(text=country, callback_data=f"select_{country}"))
    builder.adjust(2)
    return builder.as_markup()

def get_restart_button():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔄 НОВИЙ РОЗРАХУНОК", callback_data="restart"))
    return builder.as_markup()

# --- ОБРОБНИКИ ---

@dp.callback_query(F.data == "restart")
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        "👋 Вітаю!\n"
        "Я допоможу Вам перевірити термін дії закордонного паспорта для отримання візи.\n\n"
        "Оберіть країну відпочинку:"
    )
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=get_start_keyboard())
    else:
        await message.answer(text, reply_markup=get_start_keyboard())
        
    await state.set_state(Form.country)

@dp.callback_query(F.data.startswith("select_"), Form.country)
async def process_country(callback: types.CallbackQuery, state: FSMContext):
    country = callback.data.split("_")[1]
    
    await state.update_data(country=country)
    
    await callback.message.edit_text(
        f"🌍 Обрано: {country}\nТепер оберіть дату початку подорожі на календарі:",
        reply_markup=await SimpleCalendar().start_calendar()
    )
    await state.set_state(Form.start_date)

@dp.callback_query(SimpleCalendarCallback.filter(), Form.start_date)
async def process_simple_calendar(callback_query: types.CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    
    if selected:
        await state.update_data(start_date=date.strftime("%d.%m.%Y"))
        await callback_query.message.edit_text(
            f"✅ Дата вильоту: {date.strftime('%d.%m.%Y')}\n\n"
            "Скільки ночей Ви плануєте відпочивати?"
        )
        await state.set_state(Form.nights)
    else:
        await callback_query.answer()

@dp.message(Form.start_date)
async def process_manual_date(message: types.Message):
    await message.answer("⚠️ Будь ласка, оберіть дату, натиснувши на відповідну кнопку в календарі.")

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
    
    # ВИПРАВЛЕНИЙ РЯДОК:
    result = (
        f"Для отримання візи до країни **{country}** — термін дії паспорта повинен бути не менше ніж до:\n\n"
        f"👉 **{final_dt.strftime('%d.%m.%Y')}**\n\n"
        f"_(Вимога: +{buffer_days} дні з кінця поїздки)_"
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
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запустити розрахунок")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
