import os
import logging
import asyncio
import pandas as pd
import aiohttp
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

cached_rates = None
rates_timestamp = None

TOKEN = "8142538757:AAFKoH3QTPZ4oydP5pPM7L9XdDdGIvkGUSc"

VOLUME, WEIGHT, DELIVERY_TYPE, PACKAGING_TYPE = range(4)
DELIVERY_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSsjTJ6lsQrm1SuD9xWWtD2PNPE3f94d9C_fQ1MO5dVt--Fl4jUsOlupp8qksdb_w/pub?gid=1485895245&single=true&output=csv"
delivery_df = pd.read_csv(DELIVERY_CSV_URL)

CATEGORY_LABELS = {
    "CONSUMER_GOODS": "Товары народного потребления",
    "ACCESSOIRES": "Аксессуары",
    "CLOTH": "Одежда",
    "SHOES": "Обувь"
}
REVERSE_CATEGORY_LABELS = {v: k for k, v in CATEGORY_LABELS.items()}
PACKAGING_OPTIONS = {
    "Скотч-мешок": 2,
    "Обрешетка": 7,
    "Паллетный борт": 13,
    "Деревянный ящик": 18,
    "Без упаковки": 0
}

main_menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Рассчитать доставку за 5 секунд")],
     [KeyboardButton("Курс валют")],
     [KeyboardButton("Написать менеджеру")]],
    resize_keyboard=True
)

from datetime import datetime, timedelta

def save_to_google_sheets(data: list):
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)

        sheet = client.open("Cargo22 клиенты").sheet1  # Название таблицы
        sheet.append_row(data)
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")

cached_rates = None
rates_timestamp = None

async def get_exchange_rates():
    global cached_rates, rates_timestamp
    try:
        now = datetime.now()
        if cached_rates and rates_timestamp and now - rates_timestamp < timedelta(minutes=30):
            return cached_rates  # Возвращаем кэш

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.chinaspace.io/exchange-rates/bot/current") as resp:
                data = await resp.json()
                logging.info(f"Ответ от API: {data}")

                usdtrmb = float(data.get("usdtrmb"))
                originalusdtrub = float(data.get("originalusdtrub"))

                usd_rub = originalusdtrub * 1.02
                usd_cny = usdtrmb - 0.1
                cny_rub = usd_rub / usd_cny

                cached_rates = (round(usd_rub, 2), round(cny_rub, 2), round(usd_cny, 2))
                rates_timestamp = now

                return cached_rates
    except Exception as e:
        logging.error(f"Ошибка получения курсов: {e}")
        return None, None, None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋\nВыберите действие:", reply_markup=main_menu_keyboard)

async def contact_manager(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напишите нам 👉 @chinaspace_bot")

async def show_rates(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    usd_rub, cny_rub, usd_cny = await get_exchange_rates()
    if usd_rub is None:
        await update.message.reply_text("Не удалось получить курсы валют, попробуйте позже.")
        return
    await update.message.reply_text(
        f"💱 Курс валют сейчас:\n"
        f"$ = {usd_rub:.2f} ₽\n"
        f"¥ = {cny_rub:.2f} ₽\n"
    )

async def delivery_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите объем в м³ (например 1,5):")
    return VOLUME

async def get_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.replace(",", "."))
        if v <= 0: raise ValueError
        ctx.user_data['volume'] = v
        await update.message.reply_text("Введите вес в кг:")
        return WEIGHT
    except:
        await update.message.reply_text("Некорректно. Пример: 1,5")
        return VOLUME

async def get_weight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        w = float(update.message.text.replace(",", "."))
        if w <= 0: raise ValueError
        ctx.user_data['weight'] = w
        kb = [[InlineKeyboardButton(n, callback_data=f"cat|{k}")] for k, n in CATEGORY_LABELS.items()]
        await update.message.reply_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(kb))
        return DELIVERY_TYPE
    except:
        await update.message.reply_text("Некорректно. Пример: 300")
        return WEIGHT

async def get_category_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, cat = q.data.split("|")
    ctx.user_data['product_type'] = cat
    kb = [[InlineKeyboardButton(n, callback_data=f"pack|{n}")] for n in PACKAGING_OPTIONS]
    await q.message.reply_text("Выберите упаковку:", reply_markup=InlineKeyboardMarkup(kb))
    return PACKAGING_TYPE

async def get_packaging_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, pack = q.data.split("|")
    ctx.user_data['packaging_name'] = pack
    ctx.user_data['packaging_rate'] = PACKAGING_OPTIONS[pack]
    return await calculate_delivery(update, ctx)

async def calculate_delivery(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message or update.callback_query.message

        volume = ctx.user_data['volume']
        weight = ctx.user_data['weight']
        pt = ctx.user_data['product_type']
        pr = ctx.user_data['packaging_rate']
        pn = ctx.user_data['packaging_name']
        density = weight / volume

        df = delivery_df[delivery_df['productType'] == pt]
        if density <= 100:
            row = df[df['min'] < density]
        else:
            row = df[df['min'] == 400] if density >= 400 else df[(df['min'] < density) & (density <= df['max'])]

        if row.empty:
            raise ValueError("Нет ставки")

        rate = float(row.iloc[0]['rate'])
        rcost = volume * rate if density <= 100 else weight * rate
        rate_text = f"{rate} $/м³" if density <= 100 else f"{rate} $/кг"
        pcost = (volume / 0.2) * pr
        tcost = (volume / 0.2) * 6
        total = rcost + pcost + tcost

        resp = (
            f"📦 *По вашему запросу:*\n"
            f"{CATEGORY_LABELS[pt]} / {pn}\n"
            f"{volume} м³ {weight} кг (Плотность: {density:.2f})\n\n"
            f"📊 *Расчет:*\n"
            f"Доставка в МСК: {rcost:.2f}$ ({rate_text})\n"
            f"Упаковка: {pcost:.2f}$\n"
            f"Транспортный сбор: {tcost:.2f}$\n\n"
            f"🚚 *Итого Авто 12–18 дней:*\n"
            f"{total:.2f}$"
        )

        await msg.reply_text(resp, reply_markup=main_menu_keyboard, parse_mode="Markdown")

        # 🔔 Отправка уведомления в группу
        NOTIFY_CHAT_ID = -4790449381
        user = update.effective_user
        username = (
            f"@{user.username}"
            if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        )
        notify_text = f"📢 Пользователь {username} сделал расчёт доставки:\n\n{resp}"
        await ctx.bot.send_message(chat_id=NOTIFY_CHAT_ID, text=notify_text, parse_mode="Markdown")

        user = update.effective_user
        username = (
            f"@{user.username}"
            if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        )
        save_to_google_sheets([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            username,
            volume,
            weight,
            CATEGORY_LABELS[pt],
            pn,
            round(density, 2),
            rate,
            round(rcost, 2),
            round(pcost, 2),
            round(tcost, 2),
            round(total, 2)
        ])

        return ConversationHandler.END

    except Exception as e:
        logging.exception("Ошибка расчёта")
        await msg.reply_text("Ошибка рассчёта. Проверьте ввод.")
        return ConversationHandler.END


async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать"),
        BotCommand("rates", "Курс валют"),
        BotCommand("delivery", "Рассчитать доставку")
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rates", show_rates))
    app.add_handler(CommandHandler("delivery", delivery_start))
    app.add_handler(MessageHandler(filters.Regex("^Написать менеджеру$"), contact_manager))
    app.add_handler(MessageHandler(filters.Regex("^Курс валют$"), show_rates))
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Рассчитать доставку за 5 секунд$"), delivery_start)],
        states={
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            DELIVERY_TYPE: [CallbackQueryHandler(get_category_callback, pattern="^cat\\|")],
            PACKAGING_TYPE: [CallbackQueryHandler(get_packaging_callback, pattern="^pack\\|")]
        },
        fallbacks=[CommandHandler("start", start)],
        conversation_timeout=300
    )
    app.add_handler(conv)
    await setup_bot_commands(app)
    await app.run_polling()

import nest_asyncio
nest_asyncio.apply()

if __name__ == "__main__":
    asyncio.run(main())
