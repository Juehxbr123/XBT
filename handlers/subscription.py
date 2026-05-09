"""
Обработчики подписки и оплаты
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime
from database import db
from keyboards import (
    subscription_tiers_keyboard, 
    currency_keyboard, 
    active_subscription_keyboard,
    payment_keyboard,
    back_keyboard
)
from locales import get_text
from config import TIERS
from services.payment import payment_service

router = Router()


async def is_subscription_active(user: dict) -> bool:
    """Проверить активна ли подписка"""
    if not user.get("tier") or not user.get("subscription_until"):
        return False
    
    until = user["subscription_until"]
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    
    return until > datetime.now()


@router.callback_query(F.data == "subscription")
async def callback_subscription(callback: CallbackQuery):
    """Меню подписки"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    if await is_subscription_active(user) and user["tier"] != "trial":
        # Активная подписка
        tier = user["tier"]
        tier_data = TIERS.get(tier, {})
        
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        days_left = (until - datetime.now()).days
        
        # Можно ли повысить тариф
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
        # Нет активной подписки - выбор тарифа
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
        await callback.answer("Ошибка")
        return
    
    # Показываем информацию о балансе
    balance = user.get("balance", 0)
    price = TIERS[tier]["price"]
    
    text = get_text("choose_currency")
    if balance > 0:
        if balance >= price:
            text = f"💰 Ваш баланс: <b>${balance:.2f}</b>\n\nПолностью покрывает стоимость!\nВыберите валюту для оформления:"
        else:
            remaining = price - balance
            text = f"💰 Ваш баланс: <b>${balance:.2f}</b>\n💳 К оплате: <b>${remaining:.2f}</b>\n\nВыберите валюту:"
    
    await callback.message.edit_text(
        text,
        reply_markup=currency_keyboard(tier),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def callback_pay(callback: CallbackQuery):
    """Создание счёта на оплату"""
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка")
        return
    
    tier = parts[1]
    currency = parts[2]
    user_id = callback.from_user.id
    
    if tier not in TIERS:
        await callback.answer("Неверный тариф")
        return
    
    if currency not in ["TON", "USDT"]:
        await callback.answer("Неверная валюта")
        return
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Ошибка")
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
    
    # Если оплата полностью с баланса
    if pay_url is None:
        # Активируем подписку сразу
        extend = await is_subscription_active(user)
        success = await payment_service.process_successful_payment(
            user_id=user_id,
            tier=tier,
            invoice_id=invoice_id,
            extend=extend
        )
        
        if success:
            user = await db.get_user(user_id)
            until = user["subscription_until"]
            if isinstance(until, str):
                until = datetime.fromisoformat(until)
            
            await callback.message.edit_text(
                f"💰 С баланса списано: <b>${balance_used:.2f}</b>\n\n" +
                get_text(
                    "payment_success",
                    tier=tier_data["name"],
                    until=until.strftime("%d.%m.%Y")
                ),
                reply_markup=back_keyboard(),
                parse_mode="HTML"
            )
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
        # Нет подписки для продления - показываем выбор тарифа
        await callback.message.edit_text(
            get_text("subscription_choose"),
            reply_markup=subscription_tiers_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    tier = user["tier"]
    
    await callback.message.edit_text(
        get_text("choose_currency"),
        reply_markup=currency_keyboard(tier),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "upgrade_sub")
async def callback_upgrade(callback: CallbackQuery):
    """Повышение тарифа"""
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    current_tier = user.get("tier")
    
    # Показываем тарифы выше текущего
    await callback.message.edit_text(
        get_text("subscription_choose"),
        reply_markup=subscription_tiers_keyboard(current_tier),
        parse_mode="HTML"
    )
    await callback.answer()
