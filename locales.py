"""
Локализация бота (русский)
"""

TEXTS = {
    # Старт
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

Отслеживание приостановлено. Оформи подписку, чтобы продолжить!""",

    # Бан
    "banned": "🚫 Аккаунт заблокирован.",

    # Триал
    "trial_activated": """✅ <b>Триал активирован!</b>

📅 Действует: <b>1 день</b>
👤 Лимит: <b>1 аккаунт</b>

Добавь первый Twitter аккаунт для отслеживания!""",

    "trial_already_used": "❌ Вы уже использовали пробный период.",

    # Аккаунты
    "accounts_list": """📋 <b>Мои аккаунты</b> ({current}/{max})

{accounts}""",

    "accounts_empty": "📋 <b>Мои аккаунты</b> ({current}/{max})\n\nУ вас пока нет отслеживаемых аккаунтов.",

    "account_added": "✅ Аккаунт <b>@{username}</b> добавлен!",
    "account_removed": "🗑 Аккаунт <b>@{username}</b> удалён.",
    "account_not_found": "❌ Twitter аккаунт <b>@{username}</b> не найден.",
    "account_already_tracking": "⚠️ Вы уже отслеживаете <b>@{username}</b>.",
    "account_limit_reached": "❌ Достигнут лимит аккаунтов ({max}). Повысьте тариф для добавления.",
    "enter_username": "📝 Введите Twitter username (например: @elonmusk или elonmusk):",
    "select_account_to_remove": "🗑 Выберите аккаунт для удаления:",
    "no_subscription": "❌ Для отслеживания нужна подписка.",

    # Фильтры
    "filters_menu": """⚙️ <b>Фильтры уведомлений</b>

Выберите, какие твиты получать:""",

    "filter_retweets": "🔄 Ретвиты: {status}",
    "filter_replies": "💬 Ответы: {status}",
    "filter_on": "✅ ВКЛ",
    "filter_off": "❌ ВЫКЛ",
    "filter_updated": "✅ Фильтр обновлён!",

    # Подписка
    "subscription_choose": """💎 <b>Выберите тариф</b>

🥉 <b>Starter</b> — $5/мес
   └ 5 аккаунтов

🥈 <b>Pro</b> — $10/мес
   └ 10 аккаунтов

🥇 <b>Business</b> — $15/мес
   └ 15 аккаунтов""",

    "subscription_active": """💎 <b>Ваша подписка</b>

📊 Тариф: <b>{tier}</b>
💰 Цена: <b>${price}/мес</b>
👥 Лимит: <b>{max} аккаунтов</b>
⏰ Активна до: <b>{until}</b>
📅 Осталось: <b>{days_left} дн.</b>""",

    "choose_currency": "💳 Выберите валюту оплаты:",
    
    "invoice_created": """💳 <b>Счёт создан</b>

💰 Сумма: <b>{amount} {currency}</b>
📊 Тариф: <b>{tier}</b>

Нажмите кнопку ниже для оплаты:""",

    "payment_success": """✅ <b>Оплата успешна!</b>

📊 Тариф: <b>{tier}</b>
⏰ Активен до: <b>{until}</b>

Спасибо за покупку! 🎉""",

    "balance_used": "💰 С баланса списано: <b>${amount}</b>",
    "balance_partial": "💰 С баланса списано: <b>${balance}</b>\n💳 К оплате: <b>{amount} {currency}</b>",

    # Рефералка
    "referral_menu": """👥 <b>Реферальная программа</b>

Приглашай друзей и получай <b>10%</b> от каждой их оплаты навсегда!

🔗 <b>Твоя ссылка:</b>
<code>{link}</code>

📊 <b>Статистика:</b>
├ Приглашено: <b>{invited}</b>
├ Оплатили: <b>{paid}</b>
└ Заработано: <b>${earned}</b>

💰 <b>Баланс:</b> ${balance}
<i>Используется для оплаты подписки</i>""",

    # Помощь
    "help": """❓ <b>Помощь</b>

<b>Как пользоваться:</b>
1. Оформите подписку или активируйте триал
2. Добавьте Twitter аккаунты для отслеживания
3. Настройте фильтры по желанию
4. Получайте уведомления мгновенно!

<b>Вопросы?</b>
Пишите: @{support}""",

    # Алерты
    "alert_new_post": "📝 <b>Новый пост от @{username}</b>",
    "alert_retweet": "🔄 <b>Ретвит от @{username}</b>",
    "alert_reply": "💬 <b>Ответ от @{username}</b>",
    "alert_footer": "\n\n🕐 {date} МСК\n🔗 {link}",

    # Напоминания
    "reminder_3_days": "⏰ Подписка истекает через <b>3 дня</b>!",
    "reminder_2_days": "⏰ Осталось <b>2 дня</b> подписки!",
    "reminder_1_day": "🚨 Подписка истекает <b>ЗАВТРА</b>!",
    "subscription_expired": """❌ <b>Подписка истекла</b>

Отслеживание приостановлено. Оформите подписку, чтобы продолжить.""",

    # Админка
    "admin_stats": """📊 <b>Статистика бота</b>

👥 Всего юзеров: <b>{total_users}</b>
💎 Активных подписок: <b>{active_subs}</b>
├ Starter: <b>{starter}</b>
├ Pro: <b>{pro}</b>
└ Business: <b>{business}</b>

💰 Доход всего: <b>${total_income}</b>
📈 За месяц: <b>${month_income}</b>

🔄 Отслеживается аккаунтов: <b>{tracking}</b>
🚫 Забанено: <b>{banned}</b>""",

    "admin_balance_given": "✅ Юзеру @{username} начислено <b>${amount}</b>",
    "admin_user_banned": "🚫 Юзер @{username} забанен",
    "admin_user_unbanned": "✅ Юзер @{username} разбанен",
    "admin_user_not_found": "❌ Юзер не найден",

    # Кнопки
    "btn_trial": "🎁 Триал 1 день",
    "btn_subscribe": "💎 Оформить подписку",
    "btn_my_accounts": "📋 Мои аккаунты ({current}/{max})",
    "btn_filters": "⚙️ Фильтры",
    "btn_subscription": "💎 Подписка",
    "btn_referral": "👥 Рефералка",
    "btn_help": "❓ Помощь",
    "btn_back": "◀️ Назад",
    "btn_add_account": "➕ Добавить",
    "btn_remove_account": "🗑 Удалить",
    "btn_extend": "🔄 Продлить",
    "btn_upgrade": "⬆️ Повысить тариф",
    "btn_pay": "💳 Оплатить",
    "btn_cancel": "❌ Отмена",
}


def get_text(key: str, **kwargs) -> str:
    """Получить текст с подстановкой параметров"""
    text = TEXTS.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
