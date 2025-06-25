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
VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME, TRANSPORT_VOLUME, DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(8)
user_data = {}
call_tracker = {}  # user_id: timestamp

# Загрузка данных о ставках доставки
DELIVERY_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(DELIVERY_CSV_URL)

CATEGORY_LABELS = {
    "CONSUMER_GOODS": "ТНП",
    "ACCESSOIRES": "Аксессуары",
    "CLOTH": "Одежда",
    "SHOES": "Обувь"
}

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
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=main_menu_keyboard)

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        volume = float(text)
        if volume <= 0:
            raise ValueError
        context.user_data['volume'] = volume
        await update.message.reply_text("Какой вес груза? (в кг, например: 125,5)")
        return WEIGHT
    except:
        await update.message.reply_text("Введите объём в формате 10,5 — положительное число, без букв и пробелов")
        return VOLUME

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        weight = float(text)
        if weight <= 0:
            raise ValueError
        volume = context.user_data['volume']
        density = weight / volume
        keyboard = [[KeyboardButton("Новый расчёт")], [KeyboardButton("Вернуться в меню")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(f"Плотность: {density:.2f} кг/м³", reply_markup=reply_markup)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес в формате 125,5 — положительное число, без букв и пробелов")
        return WEIGHT

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await density_command(update, context)

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

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

async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in packaging_options.keys()]
    return await update.message.reply_text("Какая упаковка нужна?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)), PACKAGING_TYPE

async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in packaging_options:
        await update.message.reply_text("Пожалуйста, выберите упаковку из предложенного списка")
        return PACKAGING_TYPE
    context.user_data['packaging_rate'] = packaging_options[choice]
    await update.message.reply_text("Укажите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return PACKAGING_VOLUME

async def get_packaging_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        volume = float(text)
        rate = context.user_data['packaging_rate']
        cost = (volume / 0.2) * rate
        await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число, без букв и пробелов")
        return PACKAGING_VOLUME

async def transport_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите объём груза в м³ (например: 1,2)")
    return TRANSPORT_VOLUME

async def calculate_transport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", ".").strip())
        cost = (volume / 0.2) * 6
        await update.message.reply_text(f"Стоимость транспортного сбора: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число, без букв и пробелов")
        return TRANSPORT_VOLUME

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
    await update.message.reply_text("Введите объём груза в м³ (например: 1,5)")
    return DELIVERY_VOLUME

async def delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 300)")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,5)")
        return DELIVERY_VOLUME

async def delivery_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        product_type = context.user_data['delivery_product_type']
        volume = context.user_data['delivery_volume']
        density = weight / volume

        df_filtered = delivery_df[delivery_df['productType'] == product_type]
        row = df_filtered[(df_filtered['min'] < density) & (density <= df_filtered['max'])]
        if density <= 100:
            row = df_filtered[df_filtered['min'] < density]
            price_per_m3 = float(row.iloc[0]['rate'])
            total = volume * price_per_m3
            await update.message.reply_text(
                f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
                f"Ставка: {price_per_m3} $/м³\nИтого: {total:.2f} $",
                reply_markup=main_menu_keyboard
            )
        else:
            price_per_kg = float(row.iloc[0]['rate'])
            total = weight * price_per_kg
            await update.message.reply_text(
                f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
                f"Ставка: {price_per_kg} $/кг\nИтого: {total:.2f} $",
                reply_markup=main_menu_keyboard
            )
        return ConversationHandler.END
    except Exception as e:
        logging.exception("Ошибка при расчёте доставки")
        await update.message.reply_text("Произошла ошибка при расчёте. Убедитесь, что вы ввели корректные данные.")
        return DELIVERY_WEIGHT

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу"),
        BotCommand("density", "Узнать плотность"),
        BotCommand("cancel", "Отменить расчёт")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command)],
        states={VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)], WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)],
        states={PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_type)], PACKAGING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_volume)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать транспортный сбор$"), transport_charge)],
        states={TRANSPORT_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate_transport)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_volume)], DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_weight)], DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_result)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    app.add_handler(MessageHandler(filters.Regex("^Новый расчёт$"), restart))

    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
