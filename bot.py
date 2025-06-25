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

VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME, TRANSPORT_VOLUME, DELIVERY_TYPE, DELIVERY_VOLUME, DELIVERY_WEIGHT = range(8)
user_data = {}
call_tracker = {}

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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

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
    message_to_gleb = f"🚨 Пользователь @{username} нажал 'Позвать Глеба'"
    await context.bot.send_message(chat_id=GLEB_ID, text=message_to_gleb)
    await update.message.reply_text("Глебу отправлено уведомление ✅")

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
        await update.message.reply_text("Введите объём в формате 10,5 — положительное число")
        return VOLUME

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        weight = float(text)
        if weight <= 0:
            raise ValueError
        volume = context.user_data['volume']
        density = weight / volume
        reply = f"Плотность: {density:.2f} кг/м³"
        keyboard = [[KeyboardButton("Новый расчёт")], [KeyboardButton("Вернуться в меню")]]
        await update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите вес в формате 125,5 — положительное число")
        return WEIGHT

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await density_command(update, context)

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = ["Скотч-мешок", "Обрешетка", "Обрешетка усиленная", "Паллета", "Паллетный борт",
               "Паллетный борт усиленный", "Деревянный ящик", "Бабл пленка", "Бумажные уголки", "Без упаковки"]
    keyboard = [[KeyboardButton(o)] for o in options]
    await update.message.reply_text("Какая упаковка нужна?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PACKAGING_TYPE

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

async def get_packaging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in packaging_options:
        await update.message.reply_text("Пожалуйста, выберите упаковку из списка")
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
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число")
        return PACKAGING_VOLUME

async def transport_charge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите объём груза в м³ (например: 1,2)")
    return TRANSPORT_VOLUME

async def get_transport_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        volume = float(text)
        if volume <= 0:
            raise ValueError
        charge = (volume / 0.2) * 6
        await update.message.reply_text(f"Транспортный сбор: {charge:.2f} $", reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except:
        await update.message.reply_text("Введите объём в формате 1,2 — положительное число")
        return TRANSPORT_VOLUME

async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types = [[KeyboardButton(t)] for t in delivery_df['Категория'].unique()]
    await update.message.reply_text("Выберите тип товара:", reply_markup=ReplyKeyboardMarkup(types, resize_keyboard=True))
    return DELIVERY_TYPE

async def get_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['delivery_type'] = update.message.text
    await update.message.reply_text("Укажите объём груза в м³:", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def get_delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Укажите вес груза в кг:")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём в формате 1,2")
        return DELIVERY_VOLUME

async def get_delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        category = context.user_data['delivery_type']
        volume = context.user_data['delivery_volume']
        density = weight / volume
        df = delivery_df[delivery_df['Категория'] == category]
        row = df[(df['Плотность от'] <= density) & (df['Плотность до'] > density)]
        if row.empty:
            await update.message.reply_text("Не удалось найти подходящую ставку")
            return ConversationHandler.END

        rate = row.iloc[0]['Ставка']
        unit = row.iloc[0]['Тип']
        if unit == 'м3':
            total = rate * volume
            reply = f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\nСтавка: {rate} $/м³\nИтого: {total:.2f} $"
        else:
            total = rate * weight
            reply = f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\nСтавка: {rate} $/кг\nИтого: {total:.2f} $"

        await update.message.reply_text(reply, reply_markup=main_menu_keyboard)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text("Ошибка. Проверьте формат данных")
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
        entry_points=[CommandHandler("density", density_command),
                      MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command),
                      MessageHandler(filters.Regex("^Новый расчёт$"), restart)],
        states={VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
                WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)],
        states={PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_type)],
                PACKAGING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_volume)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать транспортный сбор$"), transport_charge_command)],
        states={TRANSPORT_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_transport_volume)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={DELIVERY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_type)],
                DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_volume)],
                DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_weight)]},
        fallbacks=[CommandHandler("cancel", cancel),
                   MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)],
        conversation_timeout=300
    ))

    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))
    await setup_bot_commands(app)
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
