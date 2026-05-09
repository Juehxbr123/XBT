"""
Админ-команды
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from locales import get_text
from config import ADMIN_ID

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка админа"""
    return user_id == ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Статистика бота"""
    if not is_admin(message.from_user.id):
        return
    
    stats = await db.get_admin_stats()
    
    await message.answer(
        get_text(
            "admin_stats",
            total_users=stats["total_users"],
            active_subs=stats["active_subs"],
            starter=stats["starter"],
            pro=stats["pro"],
            business=stats["business"],
            total_income=stats["total_income"],
            month_income=stats["month_income"],
            tracking=stats["tracking"],
            banned=stats["banned"]
        ),
        parse_mode="HTML"
    )


@router.message(Command("give"))
async def cmd_give(message: Message):
    """Выдать баланс юзеру: /give @username 50"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    
    if len(args) != 3:
        await message.answer("Использование: /give @username 50")
        return
    
    username = args[1].lstrip("@")
    
    try:
        amount = float(args[2])
    except ValueError:
        await message.answer("❌ Неверная сумма")
        return
    
    user = await db.get_user_by_username(username)
    
    if not user:
        await message.answer(get_text("admin_user_not_found"))
        return
    
    await db.add_balance(user["user_id"], amount)
    
    await message.answer(
        get_text("admin_balance_given", username=username, amount=amount),
        parse_mode="HTML"
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    """Забанить юзера: /ban @username"""
    if not is_admin(message.from_user.id):
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
    
    await message.answer(
        get_text("admin_user_banned", username=username),
        parse_mode="HTML"
    )


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Разбанить юзера: /unban @username"""
    if not is_admin(message.from_user.id):
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
    
    await message.answer(
        get_text("admin_user_unbanned", username=username),
        parse_mode="HTML"
    )
