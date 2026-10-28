from pathlib import Path

from fastapi.templating import Jinja2Templates

# Общий объект шаблонов: им пользуются и main.py, и admin.py
templates = Jinja2Templates(directory="templates")


def static_url(filename):
    # Добавляем к адресу время изменения файла: style.css?v=1761667451.
    # Файл поменялся → адрес поменялся → браузер не возьмёт старую копию из кэша
    version = int((Path("static") / filename).stat().st_mtime)
    return f"/static/{filename}?v={version}"


# Делаем функцию доступной во всех шаблонах: {{ static_url("style.css") }}
templates.env.globals["static_url"] = static_url


def collect_errors(validation_error, messages):
    """Ошибки Pydantic → словарь {поле: понятное сообщение на русском}."""
    return {err["loc"][0]: messages[err["loc"][0]] for err in validation_error.errors()}
