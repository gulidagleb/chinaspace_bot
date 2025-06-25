import os
import time
import asyncio
import pandas as pd
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME = range(4)
DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(4, 7)
user_data = {}
call_tracker = {}

main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать плотность")],
     [KeyboardButton("Рассчитать упаковку")],
     [KeyboardButton("Рассчитать транспортный сбор")],
     [KeyboardButton("Рассчитать доставку (быстрое авто)")],
     [KeyboardButton("Позвать Глеба")]],
    resize_keyboard=True,
    one_time_keyboard=False
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

def parse_float(text):
    try:
        return float(text.replace(",", ".").strip())
    except:
        return None

url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(url)

def normalize_column_names(df):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

delivery_df = normalize_column_names(delivery_df)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\nВыберите действие:",
        reply_markup=main_menu_keyboard
    )

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("ТНП")],
        [KeyboardButton("Аксессуары")],
        [KeyboardButton("Одежда")],
        [KeyboardButton("Обувь")]
    ]
    await update.message.reply_text("Выберите тип товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELIVERY_TYPE

cargo_map = {
    "ТНП": "CONSUMER_GOODS",
    "Аксессуары": "ACCESSOIRES",
    "Одежда": "CLOTH",
    "Обувь": "SHOES"
}

async def get_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in cargo_map:
        await update.message.reply_text("Пожалуйста, выберите тип товара из списка")
        return DELIVERY_TYPE

    context.user_data["delivery_type"] = cargo_map[choice]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    volume = parse_float(text)
    if volume is None or volume <= 0:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME

    context.user_data["delivery_volume"] = volume
    await update.message.reply_text("Укажите вес груза в кг (например: 125,5)")
    return DELIVERY_WEIGHT

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    weight = parse_float(text)
    if weight is None or weight <= 0:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT

    volume = context.user_data.get("delivery_volume")
    cargo_type = context.user_data.get("delivery_type")

    if not volume or not cargo_type:
        await update.message.reply_text("Ошибка: данные объёма или типа не найдены. Начните заново.")
        return ConversationHandler.END

    density = weight / volume

    row = delivery_df[
        (delivery_df["category"] == cargo_type) &
        (delivery_df["density_from"] <= density) &
        (delivery_df["density_to"] > density)
    ].head(1)

    if row.empty:
        await update.message.reply_text("Не найдена подходящая ставка для заданной плотности")
        return ConversationHandler.END

    row = row.iloc[0]
    rate = row["rate"]
    unit = row["unit"]

    if unit == "м³":
        total = rate * volume
        unit_label = "$/м³"
    else:
        total = rate * weight
        unit_label = "$/кг"

    await update.message.reply_text(
        f"Объём: {volume} м³\n"
        f"Вес: {weight} кг\n"
        f"Плотность: {density:.2f} кг/м³\n"
        f"Ставка: {rate} {unit_label}\n"
        f"Итого: {total:.2f} $",
        reply_markup=main_menu_keyboard
    )
    return ConversationHandler.END

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    delivery_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \\(быстрое авто\\)$"), delivery_start)],
        states={
            DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_type)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_weight)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(delivery_conv)

    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
