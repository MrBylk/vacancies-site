import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config

# Человек не успеет заполнить форму быстрее, а бот отправляет её мгновенно
MIN_FILL_SECONDS = 3
# Дольше этого форма считается устаревшей — попросим отправить ещё раз
MAX_FILL_SECONDS = 2 * 60 * 60

# Подписываем время открытия формы секретным ключом: бот может прочитать
# это значение, но не может подделать его, не зная SECRET_KEY
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="apply-form")


def make_form_token():
    """Токен со временем открытия формы — кладётся в скрытое поле."""
    return _serializer.dumps(time.time())


def check_form(form):
    """Возвращает "ok", "bot" или "expired"."""
    # Ловушка: поле website скрыто от людей, его заполняют только боты
    if form.get("website"):
        return "bot"

    try:
        opened_at = _serializer.loads(form.get("form_token", ""), max_age=MAX_FILL_SECONDS)
    except SignatureExpired:
        return "expired"
    except BadSignature:
        # Нет токена или подпись не сходится. Так бывает и у людей:
        # например, сервер перезапустили со сменой ключа. Поэтому не «bot»,
        # а просим отправить форму ещё раз
        return "expired"

    if time.time() - opened_at < MIN_FILL_SECONDS:
        return "bot"
    return "ok"
