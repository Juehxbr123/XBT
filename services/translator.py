"""
Переводчик через Google Translate
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_translator = None


def _get_translator():
    global _translator
    if _translator is None:
        try:
            from googletrans import Translator
            _translator = Translator()
        except Exception as e:
            logger.error(f"Failed to init translator: {e}")
    return _translator


async def translate_to_russian(text: str) -> Optional[str]:
    """Перевести текст на русский. Возвращает None если не удалось."""
    if not text or len(text.strip()) < 5:
        return None

    try:
        translator = _get_translator()
        if not translator:
            return None

        # googletrans синхронный, оборачиваем
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: translator.translate(text, dest='ru'))

        if result and result.text and result.src != 'ru':
            return result.text
        return None

    except Exception as e:
        logger.warning(f"Translation error: {e}")
        # Пересоздаём транслятор при ошибке
        global _translator
        _translator = None
        return None
