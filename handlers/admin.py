"""
Админ-команды
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from locales import get_text
from config import ADMIN_ID

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    stats = await db.get_admin_stats()
    await message.answer(get_text("admin_stats", **stats), parse_mode="HTML")


@router.message(Command("give"))
async def cmd_give(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 4:
        await message.answer("Использование: /give @username 50 USDT")
        return
    username = args[1].lstrip("@")
    try:
        amount = float(args[2])
    except:
        await message.answer("❌ Неверная сумма")
        return
    currency = args[3].upper()
    if currency == "TON":
        currency = "TONCOIN"
    if currency not in ["TONCOIN", "USDT"]:
        await message.answer("❌ Валюта: USDT или TON")
        return
    user = await db.get_user_by_username(username)
    if not user:
        await message.answer(get_text("admin_user_not_found"))
        return
    await db.add_balance(user["user_id"], currency, amount)
    await message.answer(f"✅ @{username}: +{amount} {currency}", parse_mode="HTML")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /ban @username")
        return
    username = args[1].lstrip("@")
    user = await db.get_user_by_username(username)
    if not user:
        await message.answer(get_text("admin_user_not_found"))
        return
    await db.ban_user(user["user_id"])
    await message.answer(get_text("admin_user_banned", username=username), parse_mode="HTML")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /unban @username")
        return
    username = args[1].lstrip("@")
    user = await db.get_user_by_username(username)
    if not user:
        await message.answer(get_text("admin_user_not_found"))
        return
    await db.unban_user(user["user_id"])
    await message.answer(get_text("admin_user_unbanned", username=username), parse_mode="HTML")
