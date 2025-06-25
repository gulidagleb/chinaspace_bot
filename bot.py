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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения и константы
TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

# Этапы диалогов
(
    VOLUME, WEIGHT,
    PACKAGING_TYPE, PACKAGING_VOLUME,
    DELIVERY_CATEGORY, DELIVERY_VOLUME, DELIVERY_WEIGHT
) = range(7)

# Словари для хранения данных пользователя
user_data = {}
call_tracker = {}  # user_id: timestamp

# Главная клавиатура
main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать плотность")],
     [KeyboardButton("Рассчитать упаковку")],
     [KeyboardButton("Рассчитать доставку (быстрое авто)")],
     [KeyboardButton("Позвать Глеба")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Параметры упаковки
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

# Загрузка данных по ставкам доставки из Google Sheets (CSV)
delivery_df = pd.read_csv("https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv")
delivery_df.columns = delivery_df.columns.str.strip()

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\nВыберите действие:",
        reply_markup=main_menu_keyboard
    )

# Команда расчета плотности
async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

# Плотность — шаг 1: объем
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

# Плотность — шаг 2: вес
async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        weight = float(text)
        if weight <= 0:
            raise ValueError
        volume = context.user_data.get('volume')
        if not volume:
            await update.message.reply_text("Сначала введите объем")
            return VOLUME

        density = weight / volume
        keyboard = [[KeyboardButton("Новый расчёт")], [KeyboardButton("Вернуться в меню")]]
        await update.message.reply_text(
            f"Плотность: {density:.2f} кг/м³",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес в формате 125,5 — положительное число, без букв и пробелов")
        return WEIGHT

# Обработка возврата
async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

# Расчет упаковки — шаг 1: выбор упаковки
async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in packaging_options.keys()]
    await update.message.reply_text("Какая упаковка нужна?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PACKAGING_TYPE

# Расчет упаковки — шаг 2: ввод объема
async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in packaging_options:
        await update.message.reply_text("Пожалуйста, выберите упаковку из предложенного списка")
        return PACKAGING_TYPE
    context.user_data['packaging_rate'] = packaging_options[choice]
    await update.message.reply_text("Укажите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return PACKAGING_VOLUME

async def get_packaging_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        if volume <= 0:
            raise ValueError
        rate = context.user_data['packaging_rate']
        cost = (volume / 0.2) * rate
        await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число")
        return PACKAGING_VOLUME

# Расчет доставки — шаг 1: выбор категории
async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = delivery_df['productType'].dropna().unique()
    keyboard = [[KeyboardButton(cat)] for cat in categories]
    await update.message.reply_text("Выберите категорию товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELIVERY_CATEGORY

# Доставка — шаг 2: ввод объема
async def delivery_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['category'] = update.message.text.strip()
    await update.message.reply_text("Введите объём груза в м³:", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

# Доставка — шаг 3: ввод веса и расчет
async def delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг:")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME

async def delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        volume = context.user_data.get('delivery_volume')
        category = context.user_data.get('category')
        if not volume or not category:
            await update.message.reply_text("Ошибка: отсутствуют исходные данные.")
            return ConversationHandler.END

        density = weight / volume
        df = delivery_df[delivery_df['productType'] == category]

        if density < 100:
            row = df[df['Плотность от'] <= density]
            row = row[row['Плотность до'] >= density]
            if row.empty:
                await update.message.reply_text("Не найдена подходящая ставка.")
                return ConversationHandler.END
            rate = row.iloc[0]['Ставка за м3']
            total = rate * volume
            await update.message.reply_text(
                f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
                f"Ставка: {rate} $/м³\nИтого: {total:.2f} $"
            )
        else:
            row = df[(df['Плотность от'] <= density) & (df['Плотность до'] >= density)]
            if row.empty:
                await update.message.reply_text("Не найдена подходящая ставка.")
                return ConversationHandler.END
            rate = row.iloc[0]['Ставка за кг']
            total = rate * weight
            await update.message.reply_text(
                f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
                f"Ставка: {rate} $/кг\nИтого: {total:.2f} $"
            )
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT

# Вызов Глеба
async def call_gleb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    now = time.time()
    if now - call_tracker.get(user_id, 0) < 10:
        await update.message.reply_text("Вы уже звали Глеба недавно. Подождите 10 секунд ✋")
        return
    call_tracker[user_id] = now
    username = user.username or user.first_name
    message = f"🚨 Пользователь @{username} нажал 'Позвать Глеба'"
    await context.bot.send_message(chat_id=GLEB_ID, text=message)
    await update.message.reply_text("Глебу отправлено уведомление ✅")

# Команды и запуск приложения
async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу"),
        BotCommand("density", "Узнать плотность"),
        BotCommand("cancel", "Отменить расчёт")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command))
    app.add_handler(MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command))
    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    app.add_handler(MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start))

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
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={DELIVERY_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_category)], DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_volume)], DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_weight)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
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
