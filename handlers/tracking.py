"""
Обработчики отслеживания аккаунтов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from database import db
from keyboards import accounts_keyboard, remove_accounts_keyboard, cancel_keyboard, main_menu_keyboard
from locales import get_text
from config import TIERS, TRIAL_ACCOUNTS
from services.twitter import twitter_service
import logging

logger = logging.getLogger(__name__)
router = Router()


class AddAccountStates(StatesGroup):
    waiting_username = State()


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


@router.callback_query(F.data == "accounts")
async def callback_accounts(callback: CallbackQuery, state: FSMContext):
    """Список аккаунтов"""
    await state.clear()
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user.get("banned"):
        return
    
    accounts = await db.get_user_tracking(user_id)
    current = len(accounts)
    max_accounts = get_account_limit(user.get("tier", ""))
    can_add = current < max_accounts and await is_subscription_active(user)
    
    if accounts:
        accounts_list = "\n".join([f"• @{acc['twitter_username']}" for acc in accounts])
        text = get_text("accounts_list", current=current, max=max_accounts, accounts=accounts_list)
    else:
        text = get_text("accounts_empty", current=current, max=max_accounts)
    
    await callback.message.edit_text(
        text,
        reply_markup=accounts_keyboard(accounts, can_add),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "add_account")
async def callback_add_account(callback: CallbackQuery, state: FSMContext):
    """Начало добавления аккаунта"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    if not await is_subscription_active(user):
        await callback.answer(get_text("no_subscription"), show_alert=True)
        return
    
    current = await db.get_user_tracking_count(user_id)
    max_accounts = get_account_limit(user.get("tier", ""))
    
    if current >= max_accounts:
        await callback.answer(get_text("account_limit_reached", max=max_accounts), show_alert=True)
        return
    
    # Устанавливаем состояние
    await state.set_state(AddAccountStates.waiting_username)
    logger.info(f"User {user_id} started adding account, state set to waiting_username")
    
    await callback.message.edit_text(
        get_text("enter_username"),
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AddAccountStates.waiting_username)
async def process_username_input(message: Message, state: FSMContext):
    """Обработка введённого username"""
    user_id = message.from_user.id
    
    logger.info(f"Received username input from {user_id}: {message.text}")
    
    user = await db.get_user(user_id)
    
    if not user:
        await state.clear()
        await message.answer("Напишите /start")
        return
    
    if not await is_subscription_active(user):
        await state.clear()
        await message.answer(get_text("no_subscription"))
        return
    
    # Очищаем username
    raw_input = message.text.strip() if message.text else ""
    username = raw_input.lstrip("@").lower()
    
    logger.info(f"Cleaned username: {username}")
    
    # Валидация
    if not username:
        await message.answer(
            "❌ Введите username. Например: elonmusk или @elonmusk",
            reply_markup=cancel_keyboard()
        )
        return
    
    if len(username) > 15:
        await message.answer(
            "❌ Username слишком длинный (макс 15 символов)",
            reply_markup=cancel_keyboard()
        )
        return
    
    if not username.replace("_", "").isalnum():
        await message.answer(
            "❌ Username содержит недопустимые символы",
            reply_markup=cancel_keyboard()
        )
        return
    
    # Проверяем лимит
    current = await db.get_user_tracking_count(user_id)
    max_accounts = get_account_limit(user.get("tier", ""))
    
    if current >= max_accounts:
        await state.clear()
        await message.answer(get_text("account_limit_reached", max=max_accounts))
        return
    
    # Проверяем, не отслеживается ли уже
    tracking = await db.get_user_tracking(user_id)
    if any(t["twitter_username"] == username for t in tracking):
        await message.answer(
            get_text("account_already_tracking", username=username),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Проверяем существование в Twitter
    status_msg = await message.answer("⏳ Проверяю аккаунт в Twitter...")
    
    try:
        exists, twitter_user_id = await twitter_service.check_user_exists(username)
        logger.info(f"Twitter check for @{username}: exists={exists}, user_id={twitter_user_id}")
    except Exception as e:
        logger.error(f"Twitter check error for @{username}: {e}")
        exists = False
        twitter_user_id = None
    
    if not exists:
        await status_msg.edit_text(
            get_text("account_not_found", username=username),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Добавляем в отслеживание
    success = await db.add_tracking(user_id, username)
    
    if success:
        await state.clear()
        logger.info(f"User {user_id} added tracking for @{username}")
        
        # Обновляем список
        accounts = await db.get_user_tracking(user_id)
        current = len(accounts)
        can_add = current < max_accounts
        
        accounts_list = "\n".join([f"• @{acc['twitter_username']}" for acc in accounts])
        
        await status_msg.edit_text(
            get_text("account_added", username=username) + "\n\n" +
            get_text("accounts_list", current=current, max=max_accounts, accounts=accounts_list),
            reply_markup=accounts_keyboard(accounts, can_add),
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            get_text("account_already_tracking", username=username),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "remove_account")
async def callback_remove_account(callback: CallbackQuery):
    """Выбор аккаунта для удаления"""
    accounts = await db.get_user_tracking(callback.from_user.id)
    
    if not accounts:
        await callback.answer("Нет аккаунтов для удаления")
        return
    
    await callback.message.edit_text(
        get_text("select_account_to_remove"),
        reply_markup=remove_accounts_keyboard(accounts),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_"))
async def callback_delete_account(callback: CallbackQuery):
    """Удаление аккаунта"""
    username = callback.data.replace("del_", "")
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
    
    await db.remove_tracking(user_id, username)
    logger.info(f"User {user_id} removed tracking for @{username}")
    
    accounts = await db.get_user_tracking(user_id)
    current = len(accounts)
    max_accounts = get_account_limit(user.get("tier", ""))
    can_add = current < max_accounts and await is_subscription_active(user)
    
    if accounts:
        accounts_list = "\n".join([f"• @{acc['twitter_username']}" for acc in accounts])
        text = get_text("account_removed", username=username) + "\n\n" + \
               get_text("accounts_list", current=current, max=max_accounts, accounts=accounts_list)
    else:
        text = get_text("account_removed", username=username) + "\n\n" + \
               get_text("accounts_empty", current=current, max=max_accounts)
    
    await callback.message.edit_text(
        text,
        reply_markup=accounts_keyboard(accounts, can_add),
        parse_mode="HTML"
    )
    await callback.answer()
