"""
Обработчик реферальной программы
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from keyboards import back_keyboard
from locales import get_text
from config import BOT_TOKEN

router = Router()


def get_bot_username() -> str:
    """Получить username бота из токена"""
    # В реальности нужно получать через bot.get_me()
    # Здесь используем placeholder
    return "your_bot"


@router.callback_query(F.data == "referral")
async def callback_referral(callback: CallbackQuery):
    """Реферальная программа"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    # Получаем статистику
    stats = await db.get_referral_stats(user_id)
    
    # Формируем ссылку
    bot_username = callback.bot.user.username if callback.bot.user else "your_bot"
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    await callback.message.edit_text(
        get_text(
            "referral_menu",
            link=referral_link,
            invited=stats["invited"],
            paid=stats["paid"],
            earned=stats["earned"],
            balance=round(user.get("balance", 0), 2)
        ),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
