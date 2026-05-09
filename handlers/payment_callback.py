"""
Обработчик проверки оплаты
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime
from database import db
from keyboards import payment_keyboard, back_keyboard
from locales import get_text
from config import TIERS
from services.payment import payment_service

router = Router()


@router.callback_query(F.data.startswith("check_"))
async def callback_check_payment(callback: CallbackQuery):
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
        # Обрабатываем успешную оплату
        user = await db.get_user(user_id)
        extend = user.get("tier") == payment["tier"]  # Продление если тот же тариф
        
        success = await payment_service.process_successful_payment(
            user_id=user_id,
            tier=payment["tier"],
            invoice_id=invoice_id,
            extend=extend
        )
        
        if success:
            user = await db.get_user(user_id)
            until = user["subscription_until"]
            if isinstance(until, str):
                until = datetime.fromisoformat(until)
            
            tier_data = TIERS.get(payment["tier"], {})
            
            await callback.message.edit_text(
                get_text(
                    "payment_success",
                    tier=tier_data.get("name", payment["tier"]),
                    until=until.strftime("%d.%m.%Y")
                ),
                reply_markup=back_keyboard(),
                parse_mode="HTML"
            )
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
