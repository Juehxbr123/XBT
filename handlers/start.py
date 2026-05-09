"""
Обработчик /start и главное меню
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from datetime import datetime
from database import db
from keyboards import main_menu_keyboard, welcome_keyboard, expired_keyboard, back_keyboard
from locales import get_text
from config import TIERS, TRIAL_ACCOUNTS, SUPPORT_USERNAME
import logging

logger = logging.getLogger(__name__)
router = Router()


def get_account_limit(tier: str) -> int:
    """Получить лимит аккаунтов по тарифу"""
    if tier == "trial":
        return TRIAL_ACCOUNTS
    return TIERS.get(tier, {}).get("accounts", 0)


async def is_subscription_active(user: dict) -> bool:
    """Проверить активна ли подписка"""
    if not user.get("tier") or not user.get("subscription_until"):
        return False
    until = user["subscription_until"]
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    return until > datetime.now()


async def show_main_menu(message_or_callback, user: dict, edit: bool = True):
    """Показать главное меню"""
    user_id = user["user_id"]
    
    if await is_subscription_active(user):
        current = await db.get_user_tracking_count(user_id)
        max_accounts = get_account_limit(user["tier"])
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        tier_name = TIERS.get(user["tier"], {}).get("name", user["tier"].title())
        
        text = get_text(
            "welcome_subscribed",
            tier=tier_name,
            until=until.strftime("%d.%m.%Y"),
            current=current,
            max=max_accounts
        )
        keyboard = main_menu_keyboard(current, max_accounts)
    else:
        trial_available = not user.get("trial_used")
        if user.get("trial_used"):
            text = get_text("welcome_expired")
            keyboard = expired_keyboard()
        else:
            text = get_text("welcome_new")
            keyboard = welcome_keyboard(trial_available)
    
    if edit and hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    elif edit and hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        target = message_or_callback.message if hasattr(message_or_callback, 'message') else message_or_callback
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def resolve_referrer(ref_code: str, user_id: int) -> int | None:
    """Определить реферера по коду (username или user_id)"""
    if not ref_code:
        return None
    
    # Пробуем как user_id
    try:
        referrer_id = int(ref_code)
        if referrer_id != user_id:
            referrer = await db.get_user(referrer_id)
            if referrer:
                return referrer_id
    except ValueError:
        pass
    
    # Пробуем как username
    referrer = await db.get_user_by_username(ref_code)
    if referrer and referrer["user_id"] != user_id:
        return referrer["user_id"]
    
    return None


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверяем реферальную ссылку
    referred_by = None
    if message.text and len(message.text.split()) > 1:
        ref_code = message.text.split()[1]  # /start ref_code
        referred_by = await resolve_referrer(ref_code, user_id)
        if referred_by:
            logger.info(f"User {user_id} referred by {referred_by}")
    
    # Получаем или создаём юзера
    user = await db.get_user(user_id)
    
    if not user:
        user = await db.create_user(user_id, username, referred_by)
        logger.info(f"New user created: {user_id} (@{username})")
    elif username and user.get("username") != username:
        await db.update_user(user_id, username=username)
        user["username"] = username
    
    # Проверка бана
    if user.get("banned"):
        await message.answer(get_text("banned"))
        return
    
    # Показываем меню
    await show_main_menu(message, user, edit=False)


@router.callback_query(F.data == "main")
async def callback_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Напишите /start")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    await show_main_menu(callback, user)
    await callback.answer()


@router.callback_query(F.data == "trial")
async def callback_trial(callback: CallbackQuery):
    """Активация триала"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Напишите /start")
        return
    
    if user.get("trial_used"):
        await callback.answer(get_text("trial_already_used"), show_alert=True)
        return
    
    if await db.activate_trial(user_id):
        logger.info(f"Trial activated for user {user_id}")
        await callback.message.edit_text(
            get_text("trial_activated"),
            reply_markup=main_menu_keyboard(0, TRIAL_ACCOUNTS),
            parse_mode="HTML"
        )
    else:
        await callback.answer(get_text("trial_already_used"), show_alert=True)


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Помощь"""
    await callback.message.edit_text(
        get_text("help", support=SUPPORT_USERNAME),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
