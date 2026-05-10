"""
xRocket Payment Service
"""
import httpx
from typing import Optional, Dict, Any, Tuple
from aiogram import Bot
from config import XROCKET_TOKEN, XROCKET_API_URL, TIERS, REFERRAL_PERCENT, MIN_WITHDRAW_TON, MIN_WITHDRAW_USDT
from database import db
import logging
import uuid

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=XROCKET_API_URL,
            headers={"Rocket-Pay-Key": XROCKET_TOKEN, "Content-Type": "application/json"},
            timeout=30.0)

    async def create_invoice(self, user_id: int, tier: str, currency: str
    ) -> Tuple[Optional[str], Optional[str], float]:
        """Создать счёт. Returns: (invoice_id, pay_url, amount)"""
        tier_data = TIERS.get(tier)
        if not tier_data:
            return None, None, 0

        price_usd = tier_data["price"]

        # Конвертация для TON
        if currency == "TONCOIN":
            rate = await self._get_rate("TONCOIN")
            amount = round(price_usd / rate, 4) if rate > 0 else price_usd
        else:
            amount = price_usd

        try:
            resp = await self.client.post("/invoices", json={
                "amount": amount,
                "currency": currency,
                "description": f"Подписка {tier_data['name']} — {tier_data['accounts']} аккаунтов",
                "numPayments": 1,
                "expiredIn": 3600,
                "payload": f"{user_id}:{tier}:{currency}"
            })

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    result = data.get("data", {})
                    invoice_id = str(result.get("id"))
                    pay_url = result.get("link")
                    await db.create_payment(user_id, amount, currency, tier, invoice_id)
                    logger.info(f"Invoice {invoice_id} for user {user_id}: {amount} {currency}")
                    return invoice_id, pay_url, amount

            logger.error(f"Create invoice error: {resp.text}")
        except Exception as e:
            logger.error(f"Create invoice exception: {e}")

        return None, None, 0

    async def check_invoice(self, invoice_id: str) -> str:
        """Проверить статус. Returns: paid/pending/expired"""
        try:
            resp = await self.client.get(f"/invoices/{invoice_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("data", {}).get("status", "pending")
        except Exception as e:
            logger.error(f"Check invoice error: {e}")
        return "pending"

    async def process_successful_payment(self, user_id: int, tier: str,
                                          invoice_id: str, extend: bool = False,
                                          bot: Bot = None) -> bool:
        try:
            await db.activate_subscription(user_id, tier, extend)
            await db.complete_payment(invoice_id)

            # Реферальная комиссия
            payment = await db.get_payment_by_invoice(invoice_id)
            user = await db.get_user(user_id)
            if user and user.get("referred_by") and payment:
                referrer_id = user["referred_by"]
                amount = payment["amount"]
                currency = payment["currency"]
                commission = round(amount * REFERRAL_PERCENT / 100, 6)

                await db.add_referral_commission(referrer_id, user_id, amount, currency, commission)
                logger.info(f"Referral: {commission} {currency} to {referrer_id}")

                if bot:
                    try:
                        referrer = await db.get_user(referrer_id)
                        uname = user.get("username") or f"id{user_id}"
                        bal_ton = referrer.get("balance_ton", 0) if referrer else 0
                        bal_usdt = referrer.get("balance_usdt", 0) if referrer else 0
                        await bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 <b>Реферальный бонус!</b>\n\n"
                                 f"@{uname} оплатил подписку.\n"
                                 f"Вам: <b>+{commission} {currency}</b>\n\n"
                                 f"💎 TON: {bal_ton + (commission if currency == 'TONCOIN' else 0):.4f}\n"
                                 f"💵 USDT: {bal_usdt + (commission if currency == 'USDT' else 0):.2f}",
                            parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Notify referrer error: {e}")

            return True
        except Exception as e:
            logger.error(f"Process payment error: {e}")
            return False

    async def withdraw(self, user_id: int, currency: str) -> Tuple[bool, str]:
        """Вывести баланс через xRocket transfer"""
        user = await db.get_user(user_id)
        if not user:
            return False, "Ошибка"

        field = "balance_ton" if currency == "TONCOIN" else "balance_usdt"
        balance = user.get(field, 0)
        min_amount = MIN_WITHDRAW_TON if currency == "TONCOIN" else MIN_WITHDRAW_USDT

        if balance < min_amount:
            return False, f"Минимум: {min_amount} {currency}"

        if balance <= 0:
            return False, "Нет средств"

        try:
            transfer_id = str(uuid.uuid4())
            resp = await self.client.post("/transfers", json={
                "tgUserId": user_id,
                "currency": currency,
                "amount": balance,
                "transferId": transfer_id,
                "description": "Вывод реферального баланса"
            })

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    await db.deduct_balance(user_id, currency, balance)
                    await db.create_withdrawal(user_id, balance, currency)
                    logger.info(f"Withdrawal: {balance} {currency} to {user_id}")
                    return True, f"{balance} {currency}"
                else:
                    logger.error(f"Withdraw failed: {data}")
                    return False, data.get("message", "Ошибка xRocket")
            else:
                logger.error(f"Withdraw HTTP {resp.status_code}: {resp.text}")
                return False, "Ошибка сервера"

        except Exception as e:
            logger.error(f"Withdraw exception: {e}")
            return False, str(e)

    async def _get_rate(self, currency: str) -> float:
        """Курс к USD"""
        try:
            resp = await self.client.get("/app/info")
            if resp.status_code == 200:
                data = resp.json()
                # Fallback: используем внешний курс
        except:
            pass

        # Пробуем через coingecko
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd")
                if r.status_code == 200:
                    return r.json().get("the-open-network", {}).get("usd", 3.0)
        except:
            pass

        return 3.0  # fallback

    async def close(self):
        await self.client.aclose()


payment_service = PaymentService()
