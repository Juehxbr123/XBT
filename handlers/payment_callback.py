"""
Обработчик проверки оплаты
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from datetime import datetime
from database import db
from keyboards import back_keyboard, main_menu_keyboard
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
    if not user.get("tier") or not user.get("subscription_until"):
        return False
    until = user["subscription_until"]
    if isinstance(until, str):
        until = datetime.fromisoformat(until)
    return until > datetime.now()


@router.callback_query(F.data.startswith("check_"))
async def callback_check_payment(callback: CallbackQuery, bot: Bot):
    """Проверка оплаты"""
    invoice_id = callback.data.replace("check_", "")
    user_id = callback.from_user.id
    
    # Получаем платёж из БД
    payment = await db.get_payment_by_invoice(invoice_id)
    
    if not payment:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return
    
    if payment["user_id"] != user_id:
        await callback.answer("❌ Это не ваш платёж", show_alert=True)
        return
    
    if payment["status"] == "paid":
        await callback.answer("✅ Платёж уже обработан", show_alert=True)
        return
    
    # Проверяем статус в CryptoBot
    status_data = await payment_service.check_invoice(invoice_id)
    status = status_data.get("status", "pending")
    
    if status == "paid":
        user = await db.get_user(user_id)
        extend = user.get("tier") == payment["tier"]
        
        success = await payment_service.process_successful_payment(
            user_id=user_id,
            tier=payment["tier"],
            invoice_id=invoice_id,
            extend=extend,
            bot=bot
        )
        
        if success:
            user = await db.get_user(user_id)
            until = datetime.fromisoformat(user["subscription_until"])
            tier_data = TIERS.get(payment["tier"], {})
            
            current = await db.get_user_tracking_count(user_id)
            max_accounts = get_account_limit(user["tier"])
            
            # Показываем успех + главное меню
            text = get_text(
                "payment_success",
                tier=tier_data.get("name", payment["tier"]),
                until=until.strftime("%d.%m.%Y")
            )
            text += f"\n\n{'─' * 20}\n\n"
            text += get_text(
                "welcome_subscribed",
                tier=tier_data.get("name", payment["tier"]),
                until=until.strftime("%d.%m.%Y"),
                current=current,
                max=max_accounts
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=main_menu_keyboard(current, max_accounts),
                parse_mode="HTML"
            )
            
            logger.info(f"User {user_id} payment confirmed for {payment['tier']}")
        else:
            await callback.answer("❌ Ошибка активации", show_alert=True)
    
    elif status == "expired":
        await db.expire_payment(invoice_id)
        await callback.answer("❌ Счёт истёк. Создайте новый.", show_alert=True)
        await callback.message.edit_text(
            "❌ Счёт истёк",
            reply_markup=back_keyboard("subscription")
        )
    
    else:
        await callback.answer("⏳ Ожидаем оплату...", show_alert=False)
