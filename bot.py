import os
import time
import asyncio
import pandas as pd
from io import StringIO
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

# Шаги для ConversationHandler
VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME, TRANSPORT_VOLUME, DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(8)
user_data = {}
call_tracker = {}

# Загрузка таблицы ставок доставки
csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
df = pd.read_csv(StringIO(requests.get(csv_url).text))

# Главное меню
main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать плотность")],
     [KeyboardButton("Рассчитать упаковку")],
     [KeyboardButton("Рассчитать транспортный сбор")],
     [KeyboardButton("Рассчитать доставку (быстрое авто)")],
     [KeyboardButton("Позвать Глеба")]],
    resize_keyboard=True
)

packaging_options = {
    "Скотч-мешок": 2,
    "Обрешетка": 7,
    "Обрешетка усиленная": 10,
    "Паллета": 6,
    "Паллетный борт": 13,
    "Паллетный борт усиленный": 16,
    "Деревянный ящик": 18,
    "Бабл пленка": 4,
    "Бумажные уголки": 6,
    "Без упаковки": 0
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\nВыберите действие:", reply_markup=main_menu_keyboard)

def parse_float(text):
    try:
        return float(text.replace(",", ".").strip())
    except:
        return None


# ========== ПЛОТНОСТЬ ==========
async def density_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        if volume <= 0:
            raise ValueError
        context.user_data['volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 125,5)")
        return WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return VOLUME

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        if weight <= 0:
            raise ValueError
        volume = context.user_data['volume']
        density = weight / volume
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Новый расчёт"), KeyboardButton("Вернуться в меню")]], resize_keyboard=True
        )
        await update.message.reply_text(f"Плотность: {density:.2f} кг/м³", reply_markup=keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return WEIGHT

# ========== УПАКОВКА ==========
async def packaging_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton(k)] for k in packaging_options.keys()]
    await update.message.reply_text("Выберите тип упаковки:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return PACKAGING_TYPE

async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in packaging_options:
        await update.message.reply_text("Пожалуйста, выберите упаковку из списка")
        return PACKAGING_TYPE
    context.user_data['pack_rate'] = packaging_options[choice]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return PACKAGING_VOLUME

async def get_packaging_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        rate = context.user_data['pack_rate']
        cost = (volume / 0.2) * rate
        await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return PACKAGING_VOLUME

# ========== ТРАНСПОРТНЫЙ СБОР ==========
async def transport_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return TRANSPORT_VOLUME

async def get_transport_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        cost = (volume / 0.2) * 6
        await update.message.reply_text(f"Транспортный сбор: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return TRANSPORT_VOLUME

# ========== ДОСТАВКА (БЫСТРОЕ АВТО) ==========
async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите тип товара:", reply_markup=ReplyKeyboardMarkup([
        [KeyboardButton("ТНП"), KeyboardButton("Аксессуары")],
        [KeyboardButton("Одежда"), KeyboardButton("Обувь")]], resize_keyboard=True))
    return DELIVERY_TYPE

async def get_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    mapping = {
        "ТНП": "CONSUMER_GOODS",
        "Аксессуары": "ACCESSOIRES",
        "Одежда": "CLOTH",
        "Обувь": "SHOES"
    }
    context.user_data['category'] = mapping.get(choice)
    await update.message.reply_text("Введите объём груза в м³:", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['volume'] = float(update.message.text.replace(",", "."))
        await update.message.reply_text("Введите вес груза в кг:")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    weight = parse_float(text)
    if weight is None or weight <= 0:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT

    volume = context.user_data.get("delivery_volume")
    if not volume:
        await update.message.reply_text("Сначала введите объём")
        return DELIVERY_VOLUME

    density = weight / volume
    cargo_type = context.user_data.get("delivery_type")

    # Ищем подходящую ставку
    row = delivery_df[
        (delivery_df['category'] == cargo_type) &
        (delivery_df['density_from'] <= density) &
        (delivery_df['density_to'] > density)
    ].head(1)

    if row.empty:
        await update.message.reply_text("Не найдена подходящая ставка для заданной плотности")
        return ConversationHandler.END

    row = row.iloc[0]
    rate = row['rate']
    unit = row['unit']  # 'кг' или 'м³'

    if unit == 'м³':
        total = rate * volume
        unit_label = "$ за м³"
    else:
        total = rate * weight
        unit_label = "$ за кг"

    await update.message.reply_text(
        f"Объём: {volume} м³\n"
        f"Вес: {weight} кг\n"
        f"Плотность: {density:.2f} кг/м³\n"
        f"Ставка: {rate} {unit_label}\n"
        f"Стоимость доставки: {total:.2f} $",
        reply_markup=main_menu_keyboard
    )
    return ConversationHandler.END


# ========== ПРОЧЕЕ ==========
async def call_gleb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = time.time()
    if now - call_tracker.get(user.id, 0) < 10:
        await update.message.reply_text("Подождите 10 секунд перед повторным вызовом")
        return
    call_tracker[user.id] = now
    username = user.username or user.first_name
    await context.bot.send_message(GLEB_ID, f"🚨 @{username} вызвал Глеба")
    await update.message.reply_text("Глебу отправлено уведомление ✅")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await density_start(update, context)

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать"),
        BotCommand("cancel", "Отмена")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать плотность$"), density_start)],
        states={
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_start)],
        states={
            PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_type)],
            PACKAGING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_volume)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать транспортный сбор$"), transport_charge)],
        states={
            TRANSPORT_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_transport_volume)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_type)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_weight)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    app.add_handler(MessageHandler(filters.Regex("^Новый расчёт$"), restart))
    app.add_handler(MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu))

    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
