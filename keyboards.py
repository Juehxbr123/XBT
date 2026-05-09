"""
Клавиатуры и кнопки
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Any
from config import TIERS
from locales import get_text


def main_menu_keyboard(current: int, max_accounts: int) -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"📋 Мои аккаунты ({current}/{max_accounts})",
            callback_data="accounts"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Фильтры", callback_data="filters"),
        InlineKeyboardButton(text="💎 Подписка", callback_data="subscription")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Рефералка", callback_data="referral"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    )
    
    return builder.as_markup()


def welcome_keyboard(trial_available: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура приветствия для новых юзеров"""
    builder = InlineKeyboardBuilder()
    
    if trial_available:
        builder.row(
            InlineKeyboardButton(text="🎁 Триал 1 день", callback_data="trial")
        )
    
    builder.row(
        InlineKeyboardButton(text="💎 Оформить подписку", callback_data="subscription")
    )
    
    return builder.as_markup()


def expired_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для истекшей подписки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 Оформить подписку", callback_data="subscription")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Рефералка", callback_data="referral"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    )
    return builder.as_markup()


def back_keyboard(callback_data: str = "main") -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)
    )
    return builder.as_markup()


def accounts_keyboard(accounts: List[Dict[str, Any]], can_add: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для списка аккаунтов"""
    builder = InlineKeyboardBuilder()
    
    if can_add:
        builder.row(
            InlineKeyboardButton(text="➕ Добавить", callback_data="add_account")
        )
    
    if accounts:
        builder.row(
            InlineKeyboardButton(text="🗑 Удалить", callback_data="remove_account")
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main")
    )
    
    return builder.as_markup()


def remove_accounts_keyboard(accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для удаления аккаунтов"""
    builder = InlineKeyboardBuilder()
    
    for acc in accounts:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ @{acc['twitter_username']}",
                callback_data=f"del_{acc['twitter_username']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="accounts")
    )
    
    return builder.as_markup()


def filters_keyboard(filter_retweets: bool, filter_replies: bool) -> InlineKeyboardMarkup:
    """Клавиатура фильтров"""
    builder = InlineKeyboardBuilder()
    
    rt_status = "✅ ВКЛ" if filter_retweets else "❌ ВЫКЛ"
    rp_status = "✅ ВКЛ" if filter_replies else "❌ ВЫКЛ"
    
    builder.row(
        InlineKeyboardButton(
            text=f"🔄 Ретвиты: {rt_status}",
            callback_data="toggle_retweets"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"💬 Ответы: {rp_status}",
            callback_data="toggle_replies"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main")
    )
    
    return builder.as_markup()


def subscription_tiers_keyboard(current_tier: str = None) -> InlineKeyboardMarkup:
    """Выбор тарифа"""
    builder = InlineKeyboardBuilder()
    
    tier_icons = {"starter": "🥉", "pro": "🥈", "business": "🥇"}
    
    for tier_id, tier_data in TIERS.items():
        if current_tier and tier_id == current_tier:
            continue  # Не показываем текущий тариф
        
        icon = tier_icons.get(tier_id, "💎")
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {tier_data['name']} — ${tier_data['price']}/мес",
                callback_data=f"tier_{tier_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main")
    )
    
    return builder.as_markup()


def currency_keyboard(tier: str) -> InlineKeyboardMarkup:
    """Выбор валюты оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💎 TON", callback_data=f"pay_{tier}_TON"),
        InlineKeyboardButton(text="💵 USDT", callback_data=f"pay_{tier}_USDT")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")
    )
    
    return builder.as_markup()


def active_subscription_keyboard(can_upgrade: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для активной подписки"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Продлить", callback_data="extend_sub")
    )
    
    if can_upgrade:
        builder.row(
            InlineKeyboardButton(text="⬆️ Повысить тариф", callback_data="upgrade_sub")
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="main")
    )
    
    return builder.as_markup()


def payment_keyboard(pay_url: str, invoice_id: str) -> InlineKeyboardMarkup:
    """Кнопка оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", url=pay_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="subscription")
    )
    
    return builder.as_markup()


def extend_keyboard() -> InlineKeyboardMarkup:
    """Кнопка продления из напоминания"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Продлить", callback_data="extend_sub")
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="main")
    )
    return builder.as_markup()
