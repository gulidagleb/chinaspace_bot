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

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

CATEGORY_LABELS = {
    "CONSUMER_GOODS": "ТНП",
    "ACCESSOIRES": "Аксессуары",
    "CLOTH": "Одежда",
    "SHOES": "Обувь"
}

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
    [[KeyboardButton("Рассчитать доставку (быстрое авто)")],
     [KeyboardButton("Позвать Глеба")]],
    resize_keyboard=True
)

VOLUME, WEIGHT, DELIVERY_TYPE, PACKAGING = range(4)
user_data = {}
call_tracker = {}

DELIVERY_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(DELIVERY_CSV_URL)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=main_menu_keyboard)

async def call_gleb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    now = time.time()
    last_call = call_tracker.get(user_id, 0)
    if now - last_call < 10:
        await update.message.reply_text("Вы уже звали Глеба недавно. Подождите 10 секунд ✋")
        return
    call_tracker[user_id] = now
    username = user.username or user.first_name
    await context.bot.send_message(chat_id=GLEB_ID, text=f"🚨 Пользователь @{username} нажал 'Позвать Глеба'")
    await update.message.reply_text("Глебу отправлено уведомление ✅")

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = delivery_df['productType'].dropna().unique()
    keyboard = [[KeyboardButton(CATEGORY_LABELS.get(cat, cat))] for cat in categories]
    await update.message.reply_text("Выберите категорию товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELIVERY_TYPE

async def delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reverse_labels = {v: k for k, v in CATEGORY_LABELS.items()}
    user_choice = update.message.text.strip()
    product_type = reverse_labels.get(user_choice)
    if not product_type:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка")
        return DELIVERY_TYPE
    context.user_data['delivery_product_type'] = product_type
    context.user_data['delivery_category_label'] = user_choice
    await update.message.reply_text("Введите объём груза в м³ (например: 1,5)")
    return VOLUME

async def delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 300)")
        return WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,5)")
        return VOLUME

async def delivery_packaging(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        context.user_data['delivery_weight'] = weight
        keyboard = [[KeyboardButton(name)] for name in PACKAGING_OPTIONS.keys()]
        await update.message.reply_text("Как хотите упаковать?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return PACKAGING
    except:
        await update.message.reply_text("Введите вес корректно (например: 300)")
        return WEIGHT

async def delivery_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        packaging_type = update.message.text.strip()
        if packaging_type not in PACKAGING_OPTIONS:
            await update.message.reply_text("Выберите тип упаковки из предложенного списка")
            return PACKAGING

        volume = context.user_data['delivery_volume']
        weight = context.user_data['delivery_weight']
        density = weight / volume
        product_type = context.user_data['delivery_product_type']

        df_filtered = delivery_df[delivery_df['productType'] == product_type]

        if density <= 100:
            row = df_filtered[df_filtered['min'] < density]
            row = row.sort_values(by='min').iloc[-1:]
            price = float(row.iloc[0]['rate'])
            rate_str = f"{price:.2f} $/м³"
            cost = volume * price
        else:
            row = df_filtered[(df_filtered['min'] < density) & (density <= df_filtered['max'])]
            price = float(row.iloc[0]['rate'])
            rate_str = f"{price:.2f} $/кг"
            cost = weight * price

        packaging_cost = (volume / 0.2) * PACKAGING_OPTIONS[packaging_type]
        transport_fee = (volume / 0.2) * 6
        total = cost + packaging_cost + transport_fee

        category_label = context.user_data['delivery_category_label']

        await update.message.reply_text(
            f"<b>По вашему запросу:</b>\n{category_label} / {packaging_type}\n"
            f"{volume:.2f} м³ {weight:.1f} кг (Плотность: {density:.2f} кг/м³)\n\n"
            f"<b>Расчёт:</b>\nДоставка в РФ: {cost:.2f} $ ({rate_str})\n"
            f"Упаковка: {packaging_cost:.2f} $\nТранспортный сбор: {transport_fee:.2f} $\n\n"
            f"<b>Итого Авто 12–18 дней:</b> {total:.2f} $",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard
        )
        return ConversationHandler.END
    except Exception as e:
        logging.exception("Ошибка при расчёте доставки")
        await update.message.reply_text("Произошла ошибка при расчёте. Убедитесь, что вы ввели корректные данные.")
        return PACKAGING

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \\(быстрое авто\\)$"), delivery_start)],
        states={
            DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_volume)],
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_weight)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_packaging)],
            PACKAGING: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_result)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb)],
        conversation_timeout=300
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
