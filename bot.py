import os
import time
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME = range(4)
user_data = {}
call_tracker = {}  # user_id: timestamp

main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать плотность")],
     [KeyboardButton("Рассчитать упаковку")],
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\nВыберите действие:",
        reply_markup=main_menu_keyboard
    )

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Какие габариты груза? (в м³, например: 10,5)")
    return VOLUME

async def packaging_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(name)] for name in packaging_options.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
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
    message_to_gleb = f"🚨 Пользователь @{username} нажал 'Позвать Глеба'"
    await context.bot.send_message(chat_id=GLEB_ID, text=message_to_gleb)

    log_entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - @{username} ({user_id}) вызвал Глеба"
    print(log_entry)

    await update.message.reply_text("Глебу отправлено уведомление ✅")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать работу"),
        BotCommand("density", "Узнать плотность"),
        BotCommand("cancel", "Отменить расчёт")
    ])

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    density_conv = ConversationHandler(
        entry_points=[
            CommandHandler("density", density_command),
            MessageHandler(filters.Regex("^Рассчитать плотность$"), density_command),
            MessageHandler(filters.Regex("^Новый расчёт$"), restart)
        ],
        states={
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)
        ],
        conversation_timeout=300
    )

    packaging_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Рассчитать упаковку$"), packaging_command)
        ],
        states={
            PACKAGING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_type)],
            PACKAGING_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_packaging_volume)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^Вернуться в меню$"), return_to_menu)
        ],
        conversation_timeout=300
    )

    app.add_handler(density_conv)
    app.add_handler(packaging_conv)
    app.add_handler(MessageHandler(filters.Regex("^Позвать Глеба$"), call_gleb))

    async def run():
        await setup_bot_commands(app)
        await app.run_polling()

    asyncio.run(run())

if __name__ == "__main__":
    main()
