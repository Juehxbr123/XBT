"""
Обработчики фильтров уведомлений
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from keyboards import filters_keyboard
from locales import get_text

router = Router()


@router.callback_query(F.data == "filters")
async def callback_filters(callback: CallbackQuery):
    """Меню фильтров"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    if user.get("banned"):
        await callback.message.edit_text(get_text("banned"))
        return
    
    await callback.message.edit_text(
        get_text("filters_menu"),
        reply_markup=filters_keyboard(
            user.get("filter_retweets", True),
            user.get("filter_replies", True)
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_retweets")
async def callback_toggle_retweets(callback: CallbackQuery):
    """Переключение фильтра ретвитов"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    # Переключаем
    new_value = not user.get("filter_retweets", True)
    await db.update_user(user_id, filter_retweets=int(new_value))
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=filters_keyboard(
            new_value,
            user.get("filter_replies", True)
        )
    )
    await callback.answer(get_text("filter_updated"))


@router.callback_query(F.data == "toggle_replies")
async def callback_toggle_replies(callback: CallbackQuery):
    """Переключение фильтра ответов"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка")
        return
    
    # Переключаем
    new_value = not user.get("filter_replies", True)
    await db.update_user(user_id, filter_replies=int(new_value))
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=filters_keyboard(
            user.get("filter_retweets", True),
            new_value
        )
    )
    await callback.answer(get_text("filter_updated"))
