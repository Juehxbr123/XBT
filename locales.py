"""
Локализация бота (русский)
"""

TEXTS = {
    "welcome_new": """👋 <b>Привет!</b>

Я отслеживаю Twitter аккаунты и мгновенно отправляю тебе новые твиты прямо в Telegram!

⚡️ <b>Как это работает:</b>
1. Добавляешь Twitter аккаунты
2. Получаешь уведомления за секунды

🎁 Попробуй бесплатный триал на 1 день!""",

    "welcome_subscribed": """🏠 <b>Главное меню</b>

📊 Подписка: <b>{tier}</b>
⏰ Активна до: <b>{until}</b>
👥 Аккаунтов: <b>{current}/{max}</b>""",

    "welcome_expired": """⚠️ <b>Подписка истекла</b>

Отслеживание приостановлено. Оформи подписку!""",

    "banned": "🚫 Аккаунт заблокирован.",
    "trial_activated": """✅ <b>Триал активирован!</b>

📅 Действует: <b>1 день</b>
👤 Лимит: <b>1 аккаунт</b>""",
    "trial_already_used": "❌ Вы уже использовали пробный период.",

    "accounts_list": """📋 <b>Мои аккаунты</b> ({current}/{max})

Нажмите на аккаунт для настройки фильтров:""",
    "accounts_empty": """📋 <b>Мои аккаунты</b> ({current}/{max})

У вас пока нет отслеживаемых аккаунтов.""",

    "account_settings": """⚙️ <b>Настройки @{username}</b>

🔄 Ретвиты: {rt}
💬 Ответы: {rp}
🌐 Перевод на русский: {tr}""",

    "account_added": "✅ Аккаунт <b>@{username}</b> добавлен!",
    "account_removed": "🗑 Аккаунт <b>@{username}</b> удалён.",
    "account_not_found": "❌ Twitter аккаунт <b>@{username}</b> не найден.",
    "account_already_tracking": "⚠️ Вы уже отслеживаете <b>@{username}</b>.",
    "account_limit_reached": "❌ Достигнут лимит ({max}). Повысьте тариф.",
    "enter_username": "📝 Введите Twitter username (например: elonmusk или @elonmusk):",
    "no_subscription": "❌ Нужна подписка.",
    "filter_updated": "✅ Фильтр обновлён!",

    "subscription_choose": """💎 <b>Выберите тариф</b>

⭐ <b>Base</b> — $10/мес (30 аккаунтов)
💎 <b>Pro</b> — $40/мес (200 аккаунтов)""",

    "subscription_active": """💎 <b>Ваша подписка</b>

📊 Тариф: <b>{tier}</b>
💰 Цена: <b>${price}/мес</b>
👥 Лимит: <b>{max} аккаунтов</b>
⏰ До: <b>{until}</b>
📅 Осталось: <b>{days_left} дн.</b>""",

    "choose_currency": "💳 Выберите валюту оплаты:",
    "invoice_created": """💳 <b>Счёт создан</b>

💰 Сумма: <b>{amount} {currency}</b>
📊 Тариф: <b>{tier}</b>""",

    "payment_success": """✅ <b>Оплата успешна!</b>

📊 Тариф: <b>{tier}</b>
⏰ До: <b>{until}</b>

Спасибо! 🎉""",

    "referral_menu": """👥 <b>Реферальная программа</b>

<b>30%</b> от каждой оплаты друзей навсегда!

🔗 Ссылка: <code>{link}</code>

📊 Приглашено: <b>{invited}</b> | Оплатили: <b>{paid}</b>

💎 Заработано TON: <b>{earned_ton}</b>
💵 Заработано USDT: <b>{earned_usdt}</b>

💰 <b>Доступно для вывода:</b>
💎 TON: <b>{balance_ton}</b>
💵 USDT: <b>{balance_usdt}</b>""",

    "withdraw_success": "✅ Выведено <b>{amount} {currency}</b> на ваш xRocket кошелёк!",
    "withdraw_min": "❌ Минимум для вывода: <b>{min} {currency}</b>",
    "withdraw_no_balance": "❌ Недостаточно средств.",
    "withdraw_error": "❌ Ошибка вывода. Попробуйте позже.",

    "help": """❓ <b>Помощь</b>

1. Оформите подписку или триал
2. Добавьте Twitter аккаунты
3. Настройте фильтры для каждого
4. Получайте уведомления!

Вопросы: @{support}""",

    "alert_new_post": "📝 <b>Новый пост от @{username}</b>",
    "alert_retweet": "🔄 <b>Ретвит от @{username}</b>",
    "alert_reply": "💬 <b>Ответ от @{username}</b>",
    "alert_footer": "\n\n🕐 {date} МСК\n🔗 {link}",
    "alert_translation": "\n\n🌐 <b>Перевод:</b>\n<i>{text}</i>",

    "reminder_3_days": "⏰ Подписка истекает через <b>3 дня</b>!",
    "reminder_2_days": "⏰ Осталось <b>2 дня</b>!",
    "reminder_1_day": "🚨 Подписка истекает <b>ЗАВТРА</b>!",
    "subscription_expired": "❌ <b>Подписка истекла.</b> Отслеживание приостановлено.",

    "admin_stats": """📊 <b>Статистика</b>

👥 Юзеров: <b>{total_users}</b>
💎 Подписок: <b>{active_subs}</b> (Base: {base}, Pro: {pro})
💰 Доход: <b>${total_income}</b> (мес: ${month_income})
🔄 Акков: <b>{tracking}</b> | 🚫 Бан: <b>{banned}</b>""",

    "admin_balance_given": "✅ @{username}: +<b>${amount}</b>",
    "admin_user_banned": "🚫 @{username} забанен",
    "admin_user_unbanned": "✅ @{username} разбанен",
    "admin_user_not_found": "❌ Юзер не найден",
}


def get_text(key: str, **kwargs) -> str:
    text = TEXTS.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
