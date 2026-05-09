"""
Обработчик /start и главное меню
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from datetime import datetime
from database import db
from keyboards import main_menu_keyboard, welcome_keyboard, expired_keyboard
from locales import get_text
from config import TIERS, TRIAL_ACCOUNTS, SUPPORT_USERNAME

router = Router()


def get_account_limit(tier: str) -> int:
    """Получить лимит аккаунтов по тарифу"""
    if tier == "trial":
        return TRIAL_ACCOUNTS
    tier_data = TIERS.get(tier)
    return tier_data["accounts"] if tier_data else 0


async def is_subscription_active(user: dict) -> bool:
    """Проверить активна ли подписка"""
    if not user.get("tier") or not user.get("subscription_until"):
        return False
    
    until = user["subscription_until"]
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    
    return until > datetime.now()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверяем реферальную ссылку
    referred_by = None
    if message.text and "ref_" in message.text:
        try:
            ref_part = message.text.split("ref_")[1].split()[0]
            referred_by = int(ref_part)
            if referred_by == user_id:
                referred_by = None  # Нельзя пригласить себя
        except:
            pass
    
    # Получаем или создаём юзера
    user = await db.get_user(user_id)
    
    if not user:
        user = await db.create_user(user_id, username, referred_by)
    elif username and user.get("username") != username:
        # Обновляем username если изменился
        await db.update_user(user_id, username=username)
        user["username"] = username
    
    # Проверка бана
    if user.get("banned"):
        await message.answer(get_text("banned"))
        return
    
    # Проверяем подписку
    if await is_subscription_active(user):
        # Активная подписка - главное меню
        current = await db.get_user_tracking_count(user_id)
        max_accounts = get_account_limit(user["tier"])
        
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        tier_name = TIERS.get(user["tier"], {}).get("name", user["tier"].title())
        
        await message.answer(
            get_text(
                "welcome_subscribed",
                tier=tier_name,
                until=until.strftime("%d.%m.%Y"),
                current=current,
                max=max_accounts
            ),
            reply_markup=main_menu_keyboard(current, max_accounts),
            parse_mode="HTML"
        )
    else:
        # Нет подписки
        trial_available = not user.get("trial_used")
        
        await message.answer(
            get_text("welcome_new"),
            reply_markup=welcome_keyboard(trial_available),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "main")
async def callback_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка, напишите /start")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    if await is_subscription_active(user):
        current = await db.get_user_tracking_count(user_id)
        max_accounts = get_account_limit(user["tier"])
        
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        tier_name = TIERS.get(user["tier"], {}).get("name", user["tier"].title())
        
        await callback.message.edit_text(
            get_text(
                "welcome_subscribed",
                tier=tier_name,
                until=until.strftime("%d.%m.%Y"),
                current=current,
                max=max_accounts
            ),
            reply_markup=main_menu_keyboard(current, max_accounts),
            parse_mode="HTML"
        )
    else:
        trial_available = not user.get("trial_used")
        
        await callback.message.edit_text(
            get_text("welcome_expired") if user.get("trial_used") else get_text("welcome_new"),
            reply_markup=welcome_keyboard(trial_available) if not user.get("trial_used") else expired_keyboard(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data == "trial")
async def callback_trial(callback: CallbackQuery):
    """Активация триала"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    if user.get("trial_used"):
        await callback.answer(get_text("trial_already_used"), show_alert=True)
        return
    
    # Активируем триал
    success = await db.activate_trial(user_id)
    
    if success:
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
    from keyboards import back_keyboard
    
    await callback.message.edit_text(
        get_text("help", support=SUPPORT_USERNAME),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# Middleware для проверки бана на любое сообщение
@router.message()
async def check_ban_middleware(message: Message):
    """Проверка бана на любое сообщение"""
    user = await db.get_user(message.from_user.id)
    
    if user and user.get("banned"):
        await message.answer(get_text("banned"))
        return
    
    # Если это не команда и не обрабатывается другими хендлерами
    # Просто игнорируем (или можно показать меню)
