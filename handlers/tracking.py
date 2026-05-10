"""
Отслеживание аккаунтов + персональные фильтры
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from database import db
from keyboards import accounts_keyboard, account_settings_keyboard, cancel_keyboard
from locales import get_text
from config import TIERS, TRIAL_ACCOUNTS
from services.twitter import twitter_service
import logging

logger = logging.getLogger(__name__)
router = Router()


class AddAccountStates(StatesGroup):
    waiting_username = State()


def get_limit(tier: str) -> int:
    if tier == "trial":
        return TRIAL_ACCOUNTS
    return TIERS.get(tier, {}).get("accounts", 0)


async def is_active(user: dict) -> bool:
    if not user.get("tier") or not user.get("subscription_until"):
        return False
    until = user["subscription_until"]
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    return until > datetime.now()


@router.callback_query(F.data == "accounts")
async def cb_accounts(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    user = await db.get_user(uid)
    if not user or user.get("banned"):
        return
    accounts = await db.get_user_tracking(uid)
    mx = get_limit(user.get("tier", ""))
    can_add = len(accounts) < mx and await is_active(user)
    text = get_text("accounts_list" if accounts else "accounts_empty", current=len(accounts), max=mx)
    await callback.message.edit_text(text, reply_markup=accounts_keyboard(accounts, can_add), parse_mode="HTML")
    await callback.answer()


# === Настройки аккаунта ===

@router.callback_query(F.data.startswith("accsettings_"))
async def cb_acc_settings(callback: CallbackQuery):
    username = callback.data.replace("accsettings_", "")
    uid = callback.from_user.id
    entry = await db.get_tracking_entry(uid, username)
    if not entry:
        await callback.answer("Аккаунт не найден")
        return
    rt = "✅ ВКЛ" if entry["filter_retweets"] else "❌ ВЫКЛ"
    rp = "✅ ВКЛ" if entry["filter_replies"] else "❌ ВЫКЛ"
    tr = "✅ ВКЛ" if entry["filter_translate"] else "❌ ВЫКЛ"
    await callback.message.edit_text(
        get_text("account_settings", username=username, rt=rt, rp=rp, tr=tr),
        reply_markup=account_settings_keyboard(username, entry["filter_retweets"],
                                                entry["filter_replies"], entry["filter_translate"]),
        parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("tf_rt_"))
async def cb_toggle_rt(callback: CallbackQuery):
    username = callback.data.replace("tf_rt_", "")
    uid = callback.from_user.id
    entry = await db.get_tracking_entry(uid, username)
    if not entry:
        return
    new_val = 0 if entry["filter_retweets"] else 1
    await db.update_tracking_filter(uid, username, "filter_retweets", new_val)
    entry["filter_retweets"] = new_val
    rt = "✅ ВКЛ" if new_val else "❌ ВЫКЛ"
    rp = "✅ ВКЛ" if entry["filter_replies"] else "❌ ВЫКЛ"
    tr = "✅ ВКЛ" if entry["filter_translate"] else "❌ ВЫКЛ"
    await callback.message.edit_text(
        get_text("account_settings", username=username, rt=rt, rp=rp, tr=tr),
        reply_markup=account_settings_keyboard(username, new_val, entry["filter_replies"], entry["filter_translate"]),
        parse_mode="HTML")
    await callback.answer(get_text("filter_updated"))


@router.callback_query(F.data.startswith("tf_rp_"))
async def cb_toggle_rp(callback: CallbackQuery):
    username = callback.data.replace("tf_rp_", "")
    uid = callback.from_user.id
    entry = await db.get_tracking_entry(uid, username)
    if not entry:
        return
    new_val = 0 if entry["filter_replies"] else 1
    await db.update_tracking_filter(uid, username, "filter_replies", new_val)
    entry["filter_replies"] = new_val
    rt = "✅ ВКЛ" if entry["filter_retweets"] else "❌ ВЫКЛ"
    rp = "✅ ВКЛ" if new_val else "❌ ВЫКЛ"
    tr = "✅ ВКЛ" if entry["filter_translate"] else "❌ ВЫКЛ"
    await callback.message.edit_text(
        get_text("account_settings", username=username, rt=rt, rp=rp, tr=tr),
        reply_markup=account_settings_keyboard(username, entry["filter_retweets"], new_val, entry["filter_translate"]),
        parse_mode="HTML")
    await callback.answer(get_text("filter_updated"))


@router.callback_query(F.data.startswith("tf_tr_"))
async def cb_toggle_tr(callback: CallbackQuery):
    username = callback.data.replace("tf_tr_", "")
    uid = callback.from_user.id
    entry = await db.get_tracking_entry(uid, username)
    if not entry:
        return
    new_val = 0 if entry["filter_translate"] else 1
    await db.update_tracking_filter(uid, username, "filter_translate", new_val)
    entry["filter_translate"] = new_val
    rt = "✅ ВКЛ" if entry["filter_retweets"] else "❌ ВЫКЛ"
    rp = "✅ ВКЛ" if entry["filter_replies"] else "❌ ВЫКЛ"
    tr = "✅ ВКЛ" if new_val else "❌ ВЫКЛ"
    await callback.message.edit_text(
        get_text("account_settings", username=username, rt=rt, rp=rp, tr=tr),
        reply_markup=account_settings_keyboard(username, entry["filter_retweets"], entry["filter_replies"], new_val),
        parse_mode="HTML")
    await callback.answer(get_text("filter_updated"))


# === Добавление / Удаление ===

@router.callback_query(F.data == "add_account")
async def cb_add(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    user = await db.get_user(uid)
    if not user or not await is_active(user):
        await callback.answer(get_text("no_subscription"), show_alert=True)
        return
    current = await db.get_user_tracking_count(uid)
    mx = get_limit(user.get("tier", ""))
    if current >= mx:
        await callback.answer(get_text("account_limit_reached", max=mx), show_alert=True)
        return
    await state.set_state(AddAccountStates.waiting_username)
    await callback.message.edit_text(get_text("enter_username"), reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AddAccountStates.waiting_username)
async def process_username(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = await db.get_user(uid)
    if not user or not await is_active(user):
        await state.clear()
        await message.answer(get_text("no_subscription"))
        return
    username = (message.text or "").strip().lstrip("@").lower()
    if not username or len(username) > 15 or not username.replace("_", "").isalnum():
        await message.answer("❌ Неверный username", reply_markup=cancel_keyboard())
        return
    current = await db.get_user_tracking_count(uid)
    mx = get_limit(user.get("tier", ""))
    if current >= mx:
        await state.clear()
        await message.answer(get_text("account_limit_reached", max=mx))
        return
    tracking = await db.get_user_tracking(uid)
    if any(t["twitter_username"] == username for t in tracking):
        await message.answer(get_text("account_already_tracking", username=username), reply_markup=cancel_keyboard(), parse_mode="HTML")
        return
    status_msg = await message.answer("⏳ Проверяю...")
    try:
        exists, _ = await twitter_service.check_user_exists(username)
    except:
        exists = False
    if not exists:
        await status_msg.edit_text(get_text("account_not_found", username=username), reply_markup=cancel_keyboard(), parse_mode="HTML")
        return
    if await db.add_tracking(uid, username):
        await state.clear()
        accounts = await db.get_user_tracking(uid)
        can_add = len(accounts) < mx
        text = get_text("account_added", username=username) + "\n\n" + get_text("accounts_list", current=len(accounts), max=mx)
        await status_msg.edit_text(text, reply_markup=accounts_keyboard(accounts, can_add), parse_mode="HTML")


@router.callback_query(F.data.startswith("del_"))
async def cb_delete(callback: CallbackQuery):
    username = callback.data.replace("del_", "")
    uid = callback.from_user.id
    user = await db.get_user(uid)
    if not user:
        return
    await db.remove_tracking(uid, username)
    accounts = await db.get_user_tracking(uid)
    mx = get_limit(user.get("tier", ""))
    can_add = len(accounts) < mx and await is_active(user)
    text = get_text("account_removed", username=username) + "\n\n"
    text += get_text("accounts_list" if accounts else "accounts_empty", current=len(accounts), max=mx)
    await callback.message.edit_text(text, reply_markup=accounts_keyboard(accounts, can_add), parse_mode="HTML")
    await callback.answer()
