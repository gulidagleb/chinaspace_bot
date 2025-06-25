import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне объём в м³ и вес в кг — я рассчитаю плотность.\nПример: 0.8 200")

async def calculate_density(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = text.replace(",", ".").split()
        if len(parts) != 2:
            raise ValueError("Нужно ввести 2 числа: объём и вес.")

        volume = float(parts[0])
        weight = float(parts[1])

        if volume <= 0 or weight <= 0:
            raise ValueError("Объём и вес должны быть больше нуля.")

        density = weight / volume
        await update.message.reply_text(f"Плотность: {density:.2f} кг/м³")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}\nПример ввода: 0.8 200")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, calculate_density))
    app.run_polling()

if __name__ == "__main__":
    main()
