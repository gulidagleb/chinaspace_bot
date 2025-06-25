import os
import time
import logging
import asyncio
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получение токена из переменной окружения
TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

# Состояния для ConversationHandler
VOLUME, WEIGHT, DELIVERY_TYPE, PACKAGING_TYPE, DELIVERY_RESULT = range(5)
user_data = {}

# Загрузка данных о ставках доставки
DELIVERY_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(DELIVERY_CSV_URL)

CATEGORY_LABELS = {
    "CONSUMER_GOODS": "ТНП",
    "ACCESSOIRES": "Аксессуары",
    "CLOTH": "Одежда",
    "SHOES": "Обувь"
}

REVERSE_CATEGORY_LABELS = {v: k for k, v in CATEGORY_LABELS.items()}

PACKAGING_OPTIONS = {
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

main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать доставку за 5 секунд")],
     [KeyboardButton("Написать менеджеру")]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=main_menu_keyboard)

async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напишите нам 👉 @chinaspace_bot")

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём груза в м³ (например: 1,5):")
    return VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        if volume <= 0:
            raise ValueError
        context.user_data['volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 300):")
        return WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,5)")
        return VOLUME

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        if weight <= 0:
            raise ValueError
        context.user_data['weight'] = weight
        keyboard = [[KeyboardButton(name)] for name in CATEGORY_LABELS.values()]
        await update.message.reply_text("Выберите категорию товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return DELIVERY_TYPE
    except:
        await update.message.reply_text("Введите вес корректно (например: 300)")
        return WEIGHT

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text.strip()
    if selected not in REVERSE_CATEGORY_LABELS:
        await update.message.reply_text("Выберите категорию из списка")
        return DELIVERY_TYPE
    context.user_data['product_type'] = REVERSE_CATEGORY_LABELS[selected]
    keyboard = [[KeyboardButton(name)] for name in PACKAGING_OPTIONS.keys()]
    await update.message.reply_text("Как хотите упаковать?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PACKAGING_TYPE

async def get_packaging(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice not in PACKAGING_OPTIONS:
        await update.message.reply_text("Выберите упаковку из предложенного списка")
        return PACKAGING_TYPE
    context.user_data['packaging_rate'] = PACKAGING_OPTIONS[choice]
    context.user_data['packaging_name'] = choice
    return await calculate_delivery(update, context)

async def calculate_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = context.user_data['volume']
        weight = context.user_data['weight']
        product_type = context.user_data['product_type']
        packaging_rate = context.user_data['packaging_rate']
        packaging_name = context.user_data['packaging_name']

        density = weight / volume
        df_filtered = delivery_df[delivery_df['productType'] == product_type]

        if density <= 100:
            row = df_filtered[df_filtered['min'] < density]
            if row.empty:
                raise ValueError("Нет подходящей ставки")
            rate = float(row.iloc[0]['rate'])
            delivery_cost = volume * rate
            rate_text = f"{rate} $/м³"
        else:
            row = df_filtered[(df_filtered['min'] < density) & (density <= df_filtered['max'])]
            if row.empty:
                raise ValueError("Нет подходящей ставки")
            rate = float(row.iloc[0]['rate'])
            delivery_cost = weight * rate
            rate_text = f"{rate} $/кг"

        packaging_cost = (volume / 0.2) * packaging_rate
        transport_cost = (volume / 0.2) * 6
        total = delivery_cost + packaging_cost + transport_cost

        response = (
            f"**По вашему запросу:**\n"
            f"{CATEGORY_LABELS[product_type]} / {packaging_name}\n"
            f"{volume} м³ {weight} кг (Плотность: {density:.2f} кг/м³)\n\n"
            f"**Расчет:**\n"
            f"Доставка в РФ: {delivery_cost:.2f} $ ({rate_text})\n"
            f"Упаковка: {packaging_cost:.2f} $\n"
            f"Транспортный сбор: {transport_cost:.2f} $\n\n"
            f"**Итого Авто 12-18 дней:**\n"
            f"{total:.2f} $"
        )

        await update.message.reply_text(response, reply_markup=main_menu_keyboard, parse_mode="Markdown")
        return ConversationHandler.END

    except Exception as e:
        logging.exception("Ошибка в расчёте доставки")
        await update.message.reply_text("Произошла ошибка при расчёте. Убедитесь, что вы выбрали все параметры корректно.")
        return ConversationHandler.END

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу"),
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Написать менеджеру$"), contact_manager))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку за 5 секунд$"), delivery_start)],
        states={
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
            PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging)]
        },
        fallbacks=[CommandHandler("start", start)],
        conversation_timeout=300
    ))
    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
