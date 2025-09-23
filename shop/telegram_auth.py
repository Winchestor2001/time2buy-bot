from __future__ import annotations

import hmac
import json
import hashlib
import time
from urllib.parse import parse_qsl

from typing import Tuple, Dict, Any, Optional


def _make_data_check_string(data: Dict[str, str]) -> str:
    """
    Собираем data_check_string: сортируем ключи (кроме 'hash'),
    склеиваем "key=value" через \n.
    """
    parts = []
    for k in sorted(data.keys()):
        if k == "hash":
            continue
        v = data[k]
        parts.append(f"{k}={v}")
    return "\n".join(parts)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age: int = 24 * 3600,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Валидирует initData из Telegram WebApp.

    Алгоритм (согласно Telegram):
      - data_check_string = join(sorted("key=value"), '\n'), исключая 'hash'
      - secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token.encode())
      - computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string.encode()).hexdigest()
      - сравнить с переданным 'hash' (constant time)
      - проверить auth_date на max_age

    Возвращает: (ok, payload_dict, error_message)
      payload_dict включает распарсенные поля (в т.ч. user как dict)
    """
    # Разбираем query-string в словарь (могут быть повторяющиеся ключи — берём последние)
    items = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = items.get("hash")
    if not received_hash:
        return False, {}, "hash отсутствует"

    # Строка для подписи
    data_check_string = _make_data_check_string(items)

    # 1) secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    # 2) computed = HMAC_SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return False, {}, "Подпись недействительна"

    # Возраст
    try:
        auth_date = int(items.get("auth_date", "0"))
    except ValueError:
        return False, {}, "Некорректный auth_date"

    now = int(time.time())
    if max_age and (now - auth_date) > max_age:
        return False, {}, "Сессия просрочена"

    # Развернём поле user (в initData это JSON-строка)
    payload: Dict[str, Any] = {**items}
    if "user" in payload:
        try:
            payload["user"] = json.loads(payload["user"])
        except Exception:
            # если не распарсилось — оставим как строку
            pass

    return True, payload, None