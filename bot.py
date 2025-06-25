import os
import time
import asyncio
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# ====== НАСТРОЙКИ ======
TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

# Состояния для разных диалогов
VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME = range(4)
DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(4, 7)

user_data = {}
call_tracker = {}

# Загрузка тарифов для доставки
TARIFF_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(TARIFF_URL)

# Главное меню
main_menu_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Рассчитать плотность")],
        [KeyboardButton("Рассчитать упаковку")],
        [KeyboardButton("Рассчитать доставку (быстрое авто)")],
        [KeyboardButton("Рассчитать транспортный сбор")],
        [KeyboardButton("Позвать Глеба")]
    ], resize_keyboard=True
)

packaging_options = {
    "Скотч-мешок": 2, "Обрешетка": 7, "Обрешетка усиленная": 10,
    "Паллета": 6, "Паллетный борт": 13, "Паллетный борт усиленный": 16,
    "Деревянный ящик": 18, "Бабл пленка": 4, "Бумажные уголки": 6,
    "Без упаковки": 0
}

cargo_map = {
    "ТНП": "CONSUMER_GOODS",
    "Аксессуары": "ACCESSOIRES",
    "Одежда": "CLOTH",
    "Обувь": "SHOES"
}

# Утилиты

def parse_float(text):
    try:
        return float(text.replace(",", ".").strip())
    except:
        return None

# === ОБРАБОТЧИКИ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=main_menu_keyboard)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

# === ПЛОТНОСТЬ ===

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

async def get_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_float(update.message.text)
    if not volume or volume <= 0:
        await update.message.reply_text("Введите объём корректно (например: 10,5)")
        return VOLUME
    context.user_data['volume'] = volume
    await update.message.reply_text("Какой вес груза? (в кг, например: 125,5)")
    return WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = parse_float(update.message.text)
    if not weight or weight <= 0:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return WEIGHT
    volume = context.user_data['volume']
    density = weight / volume
    keyboard = [[KeyboardButton("Новый расчёт")], [KeyboardButton("Вернуться в меню")]]
    await update.message.reply_text(f"Плотность: {density:.2f} кг/м³", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ConversationHandler.END

# === УПАКОВКА ===

async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(k)] for k in packaging_options.keys()]
    await update.message.reply_text("Какая упаковка нужна?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PACKAGING_TYPE

async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    option = update.message.text
    if option not in packaging_options:
        await update.message.reply_text("Выберите упаковку из предложенного списка")
        return PACKAGING_TYPE
    context.user_data['packaging_rate'] = packaging_options[option]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return PACKAGING_VOLUME

async def get_packaging_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_float(update.message.text)
    if not volume or volume <= 0:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return PACKAGING_VOLUME
    rate = context.user_data['packaging_rate']
    cost = (volume / 0.2) * rate
    await update.message.reply_text(f"Стоимость упаковки: {cost:.2f} $", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

# === ТРАНСПОРТНЫЙ СБОР ===

async def transport_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объём груза в м³ (например: 2,4)")
    return VOLUME

async def calc_transport_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_float(update.message.text)
    if not volume or volume <= 0:
        await update.message.reply_text("Введите объём корректно (например: 2,4)")
        return VOLUME
    fee = (volume / 0.2) * 6
    await update.message.reply_text(f"Транспортный сбор: {fee:.2f} $", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

# === ДОСТАВКА (быстрое авто) ===

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(k)] for k in cargo_map.keys()]
    await update.message.reply_text("Выберите тип товара:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELIVERY_TYPE

async def get_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in cargo_map:
        await update.message.reply_text("Выберите тип товара из списка")
        return DELIVERY_TYPE
    context.user_data['delivery_type'] = cargo_map[text]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = parse_float(update.message.text)
    if not volume or volume <= 0:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME
    context.user_data['delivery_volume'] = volume
    await update.message.reply_text("Введите вес груза в кг (например: 125,5)")
    return DELIVERY_WEIGHT

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = parse_float(update.message.text)
    if not weight or weight <= 0:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT
    volume = context.user_data['delivery_volume']
    cargo_type = context.user_data['delivery_type']
    density = weight / volume

    row = delivery_df[(delivery_df['producttype'] == cargo_type) &
                      (delivery_df['min'] <= density) &
                      (delivery_df['max'] > density)]

    if row.empty:
        await update.message.reply_text("Не удалось определить ставку по введённым данным")
        return ConversationHandler.END

    r = row.iloc[0]
    rate = r['rate']
    unit = "м³" if density < 100 else "кг"
    total = rate * volume if unit == "м³" else rate * weight

    await update.message.reply_text(
        f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
        f"Ставка: {rate} $/{unit}\nИтого: {total:.2f} $",
        reply_markup=main_menu_keyboard
    )
    return ConversationHandler.END

# === ПОЗВАТЬ ГЛЕБА ===

async def call_gleb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    now = time.time()
    if now - call_tracker.get(user_id, 0) < 10:
        await update.message.reply_text("Вы уже звали Глеба недавно. Подождите 10 секунд ✋")
        return
    call_tracker[user_id] = now
    name = user.username or user.first_name
    await context.bot.send_message(chat_id=GLEB_ID, text=f"🚨 Пользователь @{name} нажал 'Позвать Глеба'")
    await update.message.reply_text("Глебу отправлено уведомление ✅")

# === ОСНОВНОЙ ЗАПУСК ===

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу"),
        BotCommand("density", "Узнать плотность"),
        BotCommand("cancel", "Отменить расчёт")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("density", density_command), MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command), MessageHandler(filters.Regex("^Новый расчёт$"), density_command)],
        states={VOLUME: [MessageHandler(filters.TEXT, get_volume)], WEIGHT: [MessageHandler(filters.TEXT, get_weight)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)],
        states={PACKAGING_TYPE: [MessageHandler(filters.TEXT, get_packaging_type)], PACKAGING_VOLUME: [MessageHandler(filters.TEXT, get_packaging_volume)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать транспортный сбор$"), transport_fee)],
        states={VOLUME: [MessageHandler(filters.TEXT, calc_transport_fee)]},
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            DELIVERY_TYPE: [MessageHandler(filters.TEXT, get_delivery_type)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT, get_delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT, get_delivery_weight)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
