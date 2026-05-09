"""
Обработчики подписки и оплаты
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from datetime import datetime
from database import db
from keyboards import (
    subscription_tiers_keyboard,
    currency_keyboard,
    active_subscription_keyboard,
    payment_keyboard,
    back_keyboard,
    main_menu_keyboard
)
from locales import get_text
from config import TIERS, TRIAL_ACCOUNTS
from services.payment import payment_service
import logging

logger = logging.getLogger(__name__)
router = Router()


def get_account_limit(tier: str) -> int:
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


async def show_success_menu(callback: CallbackQuery, user: dict, tier_name: str, until: datetime, balance_used: float = 0):
    """Показать сообщение об успехе и главное меню"""
    current = await db.get_user_tracking_count(user["user_id"])
    max_accounts = get_account_limit(user["tier"])
    
    text = ""
    if balance_used > 0:
        text += f"💰 С баланса списано: <b>${balance_used:.2f}</b>\n\n"
    
    text += get_text("payment_success", tier=tier_name, until=until.strftime("%d.%m.%Y"))
    text += f"\n\n{'─' * 20}\n\n"
    text += get_text(
        "welcome_subscribed",
        tier=tier_name,
        until=until.strftime("%d.%m.%Y"),
        current=current,
        max=max_accounts
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(current, max_accounts),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscription")
async def callback_subscription(callback: CallbackQuery):
    """Меню подписки"""
    user = await db.get_user(callback.from_user.id)
    
    if not user or user.get("banned"):
        return
    
    if await is_subscription_active(user) and user["tier"] != "trial":
        tier = user["tier"]
        tier_data = TIERS.get(tier, {})
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        days_left = (until - datetime.now()).days
        can_upgrade = tier != "business"
        
        await callback.message.edit_text(
            get_text(
                "subscription_active",
                tier=tier_data.get("name", tier.title()),
                price=tier_data.get("price", 0),
                max=tier_data.get("accounts", 0),
                until=until.strftime("%d.%m.%Y"),
                days_left=max(0, days_left)
            ),
            reply_markup=active_subscription_keyboard(can_upgrade),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            get_text("subscription_choose"),
            reply_markup=subscription_tiers_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("tier_"))
async def callback_select_tier(callback: CallbackQuery):
    """Выбор тарифа"""
    tier = callback.data.replace("tier_", "")
    
    if tier not in TIERS:
        await callback.answer("Неверный тариф")
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    balance = user.get("balance", 0)
    price = TIERS[tier]["price"]
    
    if balance >= price:
        text = f"💰 Ваш баланс: <b>${balance:.2f}</b>\n\n✅ Полностью покрывает стоимость!\n\nВыберите валюту для оформления:"
    elif balance > 0:
        remaining = price - balance
        text = f"💰 Ваш баланс: <b>${balance:.2f}</b>\n💳 К оплате: <b>${remaining:.2f}</b>\n\nВыберите валюту:"
    else:
        text = get_text("choose_currency")
    
    await callback.message.edit_text(
        text,
        reply_markup=currency_keyboard(tier),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def callback_pay(callback: CallbackQuery, bot: Bot):
    """Создание счёта на оплату"""
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка")
        return
    
    tier = parts[1]
    currency = parts[2]
    user_id = callback.from_user.id
    
    if tier not in TIERS or currency not in ["TON", "USDT"]:
        await callback.answer("Неверные параметры")
        return
    
    user = await db.get_user(user_id)
    if not user:
        return
    
    await callback.message.edit_text("⏳ Создаём счёт...")
    
    # Создаём счёт
    invoice_id, pay_url, amount, balance_used = await payment_service.create_invoice(
        user_id=user_id,
        tier=tier,
        currency=currency,
        use_balance=True
    )
    
    if not invoice_id:
        await callback.message.edit_text(
            "❌ Ошибка создания счёта. Попробуйте позже.",
            reply_markup=back_keyboard("subscription")
        )
        return
    
    tier_data = TIERS[tier]
    
    # Если оплата полностью с баланса (pay_url = None)
    if pay_url is None:
        extend = await is_subscription_active(user) and user.get("tier") == tier
        success = await payment_service.process_successful_payment(
            user_id=user_id,
            tier=tier,
            invoice_id=invoice_id,
            extend=extend,
            bot=bot
        )
        
        if success:
            user = await db.get_user(user_id)
            until = datetime.fromisoformat(user["subscription_until"])
            await show_success_menu(callback, user, tier_data["name"], until, balance_used)
            logger.info(f"User {user_id} paid with balance for {tier}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка активации подписки",
                reply_markup=back_keyboard("subscription")
            )
        return
    
    # Обычная оплата через CryptoBot
    text = ""
    if balance_used > 0:
        text = f"💰 С баланса списано: <b>${balance_used:.2f}</b>\n\n"
    
    text += get_text(
        "invoice_created",
        amount=amount,
        currency=currency,
        tier=tier_data["name"]
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=payment_keyboard(pay_url, invoice_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "extend_sub")
async def callback_extend(callback: CallbackQuery):
    """Продление подписки"""
    user = await db.get_user(callback.from_user.id)
    
    if not user or not user.get("tier") or user["tier"] == "trial":
        await callback.message.edit_text(
            get_text("subscription_choose"),
            reply_markup=subscription_tiers_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            get_text("choose_currency"),
            reply_markup=currency_keyboard(user["tier"]),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "upgrade_sub")
async def callback_upgrade(callback: CallbackQuery):
    """Повышение тарифа"""
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        return
    
    current_tier = user.get("tier")
    
    await callback.message.edit_text(
        get_text("subscription_choose"),
        reply_markup=subscription_tiers_keyboard(current_tier),
        parse_mode="HTML"
    )
    await callback.answer()
