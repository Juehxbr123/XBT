"""
Реферальная программа
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from database import db
from keyboards import back_keyboard
from locales import get_text
from config import ADMIN_ID
import logging

logger = logging.getLogger(__name__)
router = Router()

# Кэш username бота
_bot_username: str = None


async def get_bot_username(bot: Bot) -> str:
    """Получить username бота (с кэшированием)"""
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return _bot_username


@router.callback_query(F.data == "referral")
async def callback_referral(callback: CallbackQuery, bot: Bot):
    """Реферальная программа"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Напишите /start")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    # Получаем статистику
    stats = await db.get_referral_stats(user_id)
    
    # Получаем список приглашённых
    referrals_list = await db.get_user_referrals(user_id)
    
    # Формируем ссылку через username юзера
    bot_username = await get_bot_username(bot)
    user_username = callback.from_user.username or str(user_id)
    referral_link = f"https://t.me/{bot_username}?start={user_username}"
    
    # Формируем список приглашённых
    referrals_text = ""
    if referrals_list:
        referrals_text = "\n\n👥 <b>Приглашённые:</b>\n"
        for ref in referrals_list[:10]:  # Максимум 10
            status = "💎" if ref.get("has_paid") else "⏳"
            ref_username = ref.get("username") or f"id{ref['user_id']}"
            referrals_text += f"{status} @{ref_username}\n"
        if len(referrals_list) > 10:
            referrals_text += f"<i>...и ещё {len(referrals_list) - 10}</i>\n"
    
    text = get_text(
        "referral_menu",
        link=referral_link,
        invited=stats["invited"],
        paid=stats["paid"],
        earned=stats["earned"],
        balance=round(user.get("balance", 0), 2)
    ) + referrals_text
    
    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
