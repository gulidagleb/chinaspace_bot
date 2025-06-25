import os
import time
import asyncio
import logging
import pandas as pd
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

(
    VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME,
    DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT, DELIVERY_CATEGORY
) = range(8)

user_data = {}
call_tracker = {}

main_menu_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Рассчитать плотность")],
        [KeyboardButton("Рассчитать упаковку")],
        [KeyboardButton("Транспортный сбор")],
        [KeyboardButton("Рассчитать доставку (быстрое авто)")],
        [KeyboardButton("Позвать Глеба")]
    ],
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

delivery_data_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"

def load_delivery_data():
    try:
        return pd.read_csv(delivery_data_url)
    except Exception as e:
        logging.error(f"Ошибка загрузки delivery данных: {e}")
        return pd.DataFrame()

delivery_df = load_delivery_data()

def parse_number(text):
    try:
        return float(text.replace(",", "."))
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=main_menu_keyboard)

def back_to_menu():
    return [MessageHandler(filters.Regex("^Вернуться в меню$"), start)]

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_number(update.message.text)
    if volume and volume > 0:
        context.user_data['volume'] = volume
        await update.message.reply_text("Какой вес груза? (в кг, например: 125,5)")
        return WEIGHT
    await update.message.reply_text("Введите объём в формате 10,5 — положительное число")
    return VOLUME

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = parse_number(update.message.text)
    volume = context.user_data.get('volume')
    if not volume:
        await update.message.reply_text("Сначала введите объём")
        return VOLUME
    if weight and weight > 0:
        density = weight / volume
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("Новый расчёт")],
            [KeyboardButton("Вернуться в меню")]
        ], resize_keyboard=True)
        await update.message.reply_text(f"Плотность: {density:.2f} кг/м³", reply_markup=keyboard)
        return ConversationHandler.END
    await update.message.reply_text("Введите вес корректно (например: 125,5)")
    return WEIGHT

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await density_command(update, context)

async def call_gleb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = time.time()
    if now - call_tracker.get(user.id, 0) < 10:
        await update.message.reply_text("Подождите немного перед повторным вызовом ✋")
        return
    call_tracker[user.id] = now
    await context.bot.send_message(chat_id=GLEB_ID, text=f"🚨 @{user.username or user.first_name} вызывает вас!")
    await update.message.reply_text("Глебу отправлено уведомление ✅")

async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(p)] for p in packaging_options]
    await update.message.reply_text("Выберите упаковку:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PACKAGING_TYPE

async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice in packaging_options:
        context.user_data['packaging_rate'] = packaging_options[choice]
        await update.message.reply_text("Введите объём (в м³, например: 1,2)", reply_markup=ReplyKeyboardRemove())
        return PACKAGING_VOLUME
    await update.message.reply_text("Выберите упаковку из списка")
    return PACKAGING_TYPE

async def get_packaging_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_number(update.message.text)
    if volume and volume > 0:
        cost = (volume / 0.2) * context.user_data['packaging_rate']
        await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    await update.message.reply_text("Введите корректный объём (например: 1,2)")
    return PACKAGING_VOLUME

async def transport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём (в м³, например: 1,0)")
    return DELIVERY_VOLUME

async def get_transport_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_number(update.message.text)
    if volume and volume > 0:
        cost = (volume / 0.2) * 6
        await update.message.reply_text(f"Транспортный сбор: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    await update.message.reply_text("Введите объём корректно (например: 0,5)")
    return DELIVERY_VOLUME

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(cat)] for cat in delivery_df['Категория'].unique()]
    await update.message.reply_text("Выберите категорию товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELIVERY_CATEGORY

async def get_delivery_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    if category not in delivery_df['Категория'].values:
        await update.message.reply_text("Выберите из списка")
        return DELIVERY_CATEGORY
    context.user_data['category'] = category
    await update.message.reply_text("Введите объём груза (в м³):", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_number(update.message.text)
    if volume and volume > 0:
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза (в кг):")
        return DELIVERY_WEIGHT
    await update.message.reply_text("Введите объём корректно (например: 1,0)")
    return DELIVERY_VOLUME

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = parse_number(update.message.text)
    if weight and weight > 0:
        volume = context.user_data['delivery_volume']
        category = context.user_data['category']
        density = weight / volume

        subset = delivery_df[delivery_df['Категория'] == category]
        row = subset[(subset['Плотность от'] <= density) & (subset['Плотность до'] < density + 0.01)].head(1)

        if row.empty:
            await update.message.reply_text("Не удалось найти подходящую ставку")
            return ConversationHandler.END

        rate = row.iloc[0]['Ставка']
        rate_type = row.iloc[0]['Тип ставки']
        if rate_type == 'м3':
            total = rate * volume
            reply = f"Ставка: {rate} $/м³\nИтого: {total:.2f} $"
        else:
            total = rate * weight
            reply = f"Ставка: {rate} $/кг\nИтого: {total:.2f} $"

        await update.message.reply_text(reply, reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    await update.message.reply_text("Введите вес корректно (например: 125,5)")
    return DELIVERY_WEIGHT

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать"),
        BotCommand("density", "Узнать плотность")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    await setup_bot_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("density", density_command), MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command), MessageHandler(filters.Regex("^Новый расчёт$"), restart)],
        states={VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)], WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]},
        fallbacks=back_to_menu(),
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)],
        states={PACKAGING_TYPE: [MessageHandler(filters.TEXT, get_packaging_type)], PACKAGING_VOLUME: [MessageHandler(filters.TEXT, get_packaging_volume)]},
        fallbacks=back_to_menu()
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Транспортный сбор$"), transport_command)],
        states={DELIVERY_VOLUME: [MessageHandler(filters.TEXT, get_transport_volume)]},
        fallbacks=back_to_menu()
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            DELIVERY_CATEGORY: [MessageHandler(filters.TEXT, get_delivery_category)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT, get_delivery_weight)]
        },
        fallbacks=back_to_menu()
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))

    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
