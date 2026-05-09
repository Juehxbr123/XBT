"""
CryptoBot Payment Service
"""
import httpx
from typing import Optional, Dict, Any, Tuple
from aiogram import Bot
from config import CRYPTOBOT_TOKEN, CRYPTOBOT_API_URL, TIERS, REFERRAL_PERCENT
from database import db
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    """Сервис оплаты через CryptoBot"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=CRYPTOBOT_API_URL,
            headers={"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN},
            timeout=30.0
        )
    
    async def get_exchange_rate(self, currency: str) -> float:
        """Получить курс валюты к USD"""
        try:
            response = await self.client.get("/getExchangeRates")
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for rate in data.get("result", []):
                        if rate.get("source") == currency and rate.get("target") == "USD":
                            return float(rate.get("rate", 1))
            return 1.0
        except Exception as e:
            logger.error(f"Get exchange rate error: {e}")
            return 1.0
    
    async def create_invoice(
        self,
        user_id: int,
        tier: str,
        currency: str,
        use_balance: bool = True
    ) -> Tuple[Optional[str], Optional[str], float, float]:
        """
        Создать счёт на оплату
        Returns: (invoice_id, pay_url, amount_to_pay, balance_used)
        """
        tier_data = TIERS.get(tier)
        if not tier_data:
            return None, None, 0, 0
        
        price_usd = tier_data["price"]
        balance_used = 0
        
        # Списываем баланс если нужно
        if use_balance:
            user = await db.get_user(user_id)
            user_balance = user.get("balance", 0) if user else 0
            
            if user_balance >= price_usd:
                # Баланс покрывает полностью
                balance_used = await db.deduct_balance(user_id, price_usd)
                
                # Создаём "виртуальный" платёж
                payment_id = await db.create_payment(
                    user_id=user_id,
                    amount=price_usd,
                    currency="BALANCE",
                    tier=tier,
                    invoice_id=f"balance_{user_id}_{tier}_{payment_id}"
                )
                
                return f"balance_{payment_id}", None, 0, balance_used
            
            elif user_balance > 0:
                # Частичное списание
                balance_used = await db.deduct_balance(user_id, user_balance)
                price_usd -= balance_used
        
        # Конвертируем в нужную валюту
        if currency == "USDT":
            amount = price_usd
        else:  # TON
            rate = await self.get_exchange_rate("TON")
            amount = round(price_usd / rate, 2) if rate > 0 else price_usd
        
        try:
            response = await self.client.post("/createInvoice", json={
                "asset": currency,
                "amount": str(amount),
                "description": f"Подписка {tier_data['name']} - {tier_data['accounts']} аккаунтов",
                "hidden_message": f"Спасибо за покупку! Подписка {tier_data['name']} активирована.",
                "payload": f"{user_id}:{tier}:{balance_used}",
                "expires_in": 3600  # 1 час
            })
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    invoice_id = str(result.get("invoice_id"))
                    pay_url = result.get("pay_url")
                    
                    # Сохраняем платёж
                    await db.create_payment(
                        user_id=user_id,
                        amount=price_usd + balance_used,  # Полная цена тарифа
                        currency=currency,
                        tier=tier,
                        invoice_id=invoice_id
                    )
                    
                    logger.info(f"Invoice created for user {user_id}: {invoice_id}")
                    return invoice_id, pay_url, amount, balance_used
            
            logger.error(f"Create invoice error: {response.text}")
            
        except Exception as e:
            logger.error(f"Create invoice exception: {e}")
            
            # Возвращаем баланс если ошибка
            if balance_used > 0:
                await db.add_balance(user_id, balance_used)
        
        return None, None, 0, 0
    
    async def check_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Проверить статус счёта
        Returns: {"status": "paid/pending/expired", "amount": float}
        """
        # Проверка "балансового" платежа
        if invoice_id.startswith("balance_"):
            return {"status": "paid", "amount": 0}
        
        try:
            response = await self.client.get(
                "/getInvoices",
                params={"invoice_ids": invoice_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    items = data.get("result", {}).get("items", [])
                    if items:
                        invoice = items[0]
                        status = invoice.get("status", "pending")
                        amount = float(invoice.get("amount", 0))
                        return {"status": status, "amount": amount}
            
        except Exception as e:
            logger.error(f"Check invoice error: {e}")
        
        return {"status": "pending", "amount": 0}
    
    async def process_successful_payment(
        self,
        user_id: int,
        tier: str,
        invoice_id: str,
        extend: bool = False,
        bot: Bot = None
    ) -> bool:
        """Обработка успешного платежа"""
        try:
            # Активируем подписку
            await db.activate_subscription(user_id, tier, extend)
            
            # Отмечаем платёж
            if not invoice_id.startswith("balance_"):
                await db.complete_payment(invoice_id)
            
            # Начисляем реферальный бонус
            user = await db.get_user(user_id)
            if user and user.get("referred_by"):
                referrer_id = user["referred_by"]
                tier_price = TIERS[tier]["price"]
                commission = round(tier_price * REFERRAL_PERCENT / 100, 2)
                
                await db.add_referral_commission(
                    referrer_id=referrer_id,
                    referred_id=user_id,
                    payment_amount=tier_price,
                    commission=commission
                )
                
                logger.info(f"Referral commission ${commission} to user {referrer_id}")
                
                # Уведомляем реферера
                if bot:
                    try:
                        referrer = await db.get_user(referrer_id)
                        user_username = user.get("username") or f"id{user_id}"
                        await bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 <b>Реферальный бонус!</b>\n\n"
                                 f"Ваш друг @{user_username} оплатил подписку.\n"
                                 f"Вам начислено: <b>${commission}</b>\n\n"
                                 f"💰 Ваш баланс: <b>${referrer.get('balance', 0) + commission:.2f}</b>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify referrer {referrer_id}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Process payment error: {e}")
            return False
    
    async def close(self):
        """Закрыть клиент"""
        await self.client.aclose()


# Глобальный инстанс
payment_service = PaymentService()
