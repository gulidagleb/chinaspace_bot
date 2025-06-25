import os
import time
import asyncio
import logging
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME, TRANSPORT_CATEGORY, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(7)
user_data = {}
call_tracker = {}  # user_id: timestamp

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

delivery_categories = ["ТНП", "Аксессуары", "Одежда", "Обувь"]
delivery_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\nВыберите действие:",
        reply_markup=main_menu_keyboard
    )

# Плотность
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

        keyboard = [
            [KeyboardButton("Новый расчёт")],
            [KeyboardButton("Вернуться в меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            f"Плотность: {density:.2f} кг/м³",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес в формате 125,5 — положительное число, без букв и пробелов")
        return WEIGHT

# Упаковка
async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in packaging_options.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Какая упаковка нужна?", reply_markup=reply_markup)
    return PACKAGING_TYPE

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
        if volume <= 0:
            raise ValueError
        rate = context.user_data['packaging_rate']
        cost = (volume / 0.2) * rate
        await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число, без букв и пробелов")
        return PACKAGING_VOLUME

# Транспортный сбор
async def transport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)")
    return PACKAGING_VOLUME

# Доставка
async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in delivery_categories]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите тип товара:", reply_markup=reply_markup)
    return TRANSPORT_CATEGORY

async def get_delivery_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    if category not in delivery_categories:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка")
        return TRANSPORT_CATEGORY
    context.user_data['delivery_category'] = category.upper()
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", ".").strip())
        if volume <= 0:
            raise ValueError
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 125,5)")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if 'delivery_volume' not in context.user_data:
            await update.message.reply_text("Сначала введите объём груза.")
            return DELIVERY_VOLUME

        weight = float(update.message.text.replace(",", ".").strip())
        if weight <= 0:
            raise ValueError

        volume = context.user_data['delivery_volume']
        density = weight / volume
        category = context.user_data['delivery_category']

        df = pd.read_csv(delivery_url)
        filtered = df[df['Category'].str.upper() == category.upper()]
        match = filtered[(filtered['Density from'] <= density) & (density < filtered['Density to'])]

        if density == 100:
            match = filtered[filtered['Density from'] > 100].head(1)

        if match.empty:
            await update.message.reply_text("Не удалось найти ставку для этих данных")
            return ConversationHandler.END

        row = match.iloc[0]
        rate = row['Rate']
        is_cubic = density < 100
        total = rate * (volume if is_cubic else weight)

        await update.message.reply_text(
            f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
            f"Ставка: {rate} $/{'м³' if is_cubic else 'кг'}\nИтого: {total:.2f} $",
            reply_markup=main_menu_keyboard
        )
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при обработке доставки: {e}")
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT

# Прочее
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
    message_to_gleb = f"🚨 Пользователь @{username} нажал 'Позвать Глеба'"
    await context.bot.send_message(chat_id=GLEB_ID, text=message_to_gleb)
    await update.message.reply_text("Глебу отправлено уведомление ✅")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await density_command(update, context)

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

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
        entry_points=[CommandHandler("density", density_command), MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command)],
        states={
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)],
        states={
            PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_type)],
            PACKAGING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_volume)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            TRANSPORT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_category)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_weight)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    app.add_handler(MessageHandler(filters.Regex("^Новый расчёт$"), restart))
    app.add_handler(MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu))

    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
