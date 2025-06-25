import os
import time
import asyncio
import pandas as pd
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

TOKEN = os.environ.get("TOKEN")
GLEB_ID = 277837387

(
    VOLUME, WEIGHT, PACKAGING_TYPE, PACKAGING_VOLUME,
    DELIVERY_CATEGORY, DELIVERY_VOLUME, DELIVERY_WEIGHT
) = range(7)

user_data = {}
call_tracker = {}

main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать плотность")],
     [KeyboardButton("Рассчитать упаковку")],
     [KeyboardButton("Рассчитать сбор")],
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

# --- Плотность ---
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

# --- Доставка ---
async def delivery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[KeyboardButton("ТНП")], [KeyboardButton("Аксессуары")], [KeyboardButton("Одежда")], [KeyboardButton("Обувь")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите тип товара:", reply_markup=reply_markup)
    return DELIVERY_CATEGORY

async def delivery_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    mapping = {
        "ТНП": "CONSUMER_GOODS",
        "Аксессуары": "ACCESSOIRES",
        "Одежда": "CLOTH",
        "Обувь": "SHOES"
    }
    if text not in mapping:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка")
        return DELIVERY_CATEGORY
    context.user_data['delivery_category'] = mapping[text]
    await update.message.reply_text("Введите объём груза в м³ (например: 1,2)", reply_markup=ReplyKeyboardRemove())
    return DELIVERY_VOLUME

async def delivery_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        volume = float(update.message.text.replace(",", "."))
        if volume <= 0:
            raise ValueError
        context.user_data['delivery_volume'] = volume
        await update.message.reply_text("Введите вес груза в кг (например: 125,5)")
        return DELIVERY_WEIGHT
    except:
        await update.message.reply_text("Введите объём корректно (например: 1,2)")
        return DELIVERY_VOLUME

async def delivery_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        if weight <= 0:
            raise ValueError
        category = context.user_data['delivery_category']
        volume = context.user_data['delivery_volume']
        density = weight / volume

        url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
        df = pd.read_csv(url)

        match_row = df[
            (df['Категория'] == category) &
            (df['Плотность от'] <= density) &
            (df['Плотность до'] > density)
        ]

        if match_row.empty and density == 100:
            match_row = df[(df['Категория'] == category) & (df['Плотность от'] <= 100) & (df['Плотность до'] > 100)]

        if match_row.empty:
            await update.message.reply_text("❗️ Не удалось определить ставку для таких параметров. Проверьте плотность или категорию товара")
            return ConversationHandler.END

        rate = match_row.iloc[0]['Ставка']
        is_volume_based = density < 100
        if is_volume_based:
            total = volume * rate
            rate_str = f"{rate:.0f} $/м³"
        else:
            total = weight * rate
            rate_str = f"{rate:.2f} $/кг"

        await update.message.reply_text(
            f"Объём: {volume} м³\nВес: {weight} кг\nПлотность: {density:.2f} кг/м³\n"
            f"Ставка: {rate_str}\nИтого: {total:.2f} $",
            reply_markup=main_menu_keyboard
        )
        return ConversationHandler.END

    except:
        await update.message.reply_text("Введите вес корректно (например: 125,5)")
        return DELIVERY_WEIGHT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Расчёт отменён.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    delivery_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку \(быстрое авто\)$"), delivery_start)],
        states={
            DELIVERY_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_category)],
            DELIVERY_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_volume)],
            DELIVERY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_weight)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Вернуться в меню$"), start)],
        conversation_timeout=300
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(delivery_conv)
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
