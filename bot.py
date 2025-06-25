import os
import time
import asyncio
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME, TRANSPORT_VOLUME, DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(8)
user_data = {}
call_tracker = {}  # user_id: timestamp

import requests
from io import StringIO

csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
response = requests.get(csv_url)
delivery_df = pd.read_csv(StringIO(response.text))

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

delivery_types = {
    "ТНП": "CONSUMER_GOODS",
    "Аксессуары": "ACCESSOIRES",
    "Одежда": "CLOTH",
    "Обувь": "SHOES"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\nВыберите действие:",
        reply_markup=main_menu_keyboard
    )

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in delivery_types.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите тип товара:", reply_markup=reply_markup)
    return DELIVERY_TYPE

async def get_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text
    if selected not in delivery_types:
        await update.message.reply_text("Выберите тип из списка")
        return DELIVERY_TYPE
    context.user_data['delivery_product'] = delivery_types[selected]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        volume = float(text)
        if volume <= 0:
            raise ValueError
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 100,5)")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно, например: 1,2")
        return DELIVERY_VOLUME

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        weight = float(text)
        if weight <= 0:
            raise ValueError
        volume = context.user_data['delivery_volume']
        density = weight / volume
        product_type = context.user_data['delivery_product']

        subset = delivery_df[(delivery_df['deliveryType'] == 'FAST_CAR') &
                             (delivery_df['productType'] == product_type)]

        match = subset[(subset['min'] <= density) & (density < subset['max'])].head(1)
        if match.empty:
            await update.message.reply_text("Не удалось найти ставку для заданной плотности")
            return ConversationHandler.END

        rate = float(match.iloc[0]['rate'])

        if density < 100:
            total = rate * volume
            rate_str = f"{rate:.2f} $/м³"
        else:
            total = rate * weight
            rate_str = f"{rate:.2f} $/кг"

        await update.message.reply_text(
            f"Объём: {volume:.2f} м³\nВес: {weight:.2f} кг\nПлотность: {density:.2f} кг/м³\n"
            f"Ставка: {rate_str}\nИтого: {total:.2f} $",
            reply_markup=main_menu_keyboard
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес корректно, например: 100,5")
        return DELIVERY_WEIGHT

# ... (остальной код остаётся прежним, включая другие команды и conv handlers)

if __name__ == "__main__":
    from telegram.ext import ApplicationBuilder

    app = ApplicationBuilder().token(TOKEN).build()

    # ConversationHandlers как раньше + новый:
    delivery_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_type)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_weight)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(delivery_conv)
    # (остальные add_handler и conv остаются прежними)

    asyncio.get_event_loop().create_task(setup_bot_commands(app))
    app.run_polling()
