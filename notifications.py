import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("uvicorn.error")  # пишем в ту же консоль, что и сервер

# Все настройки — через переменные окружения, пароль в коде не храним.
#   EMAIL_MODE=console — письмо печатается в консоль (по умолчанию, для разработки)
#   EMAIL_MODE=smtp    — письмо реально отправляется через почтовый сервер
EMAIL_MODE = os.environ.get("EMAIL_MODE", "console")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER or "site@example.ru")
# Кому слать уведомления; можно несколько через запятую
EMAIL_TO = [a.strip() for a in os.environ.get("EMAIL_TO", "hr@example.ru").split(",") if a.strip()]
# Адрес сайта — чтобы в письме была рабочая ссылка на админку
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def build_application_email(vacancy, application):
    msg = EmailMessage()
    msg["Subject"] = f"Новая заявка: {vacancy['title']}"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg.set_content(
        f"Новая заявка на вакансию «{vacancy['title']}»\n"
        f"\n"
        f"Имя:            {application['full_name']}\n"
        f"Телефон:        {application['phone']}\n"
        f"Специальность:  {application['specialty']}\n"
        f"Возраст:        {application['age']}\n"
        f"Права:          {'да' if application['has_license'] else 'нет'}\n"
        f"Опыт:           {application['experience'] or '—'}\n"
        f"\n"
        f"Все заявки: {SITE_URL}/admin/applications\n"
    )
    return msg


def send_email(msg):
    if EMAIL_MODE == "console":
        # Режим разработки: показываем письмо вместо отправки
        print("\n" + "=" * 60)
        print("ПИСЬМО (EMAIL_MODE=console, реально не отправлено)")
        print(f"Кому: {msg['To']}")
        print(f"Тема: {msg['Subject']}")
        print("-" * 60)
        print(msg.get_content())
        print("=" * 60 + "\n", flush=True)
        return

    # SMTP_SSL — шифрованное соединение с почтовым сервером (порт 465)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def notify_new_application(vacancy, application):
    """Запускается в фоне после сохранения заявки."""
    try:
        send_email(build_application_email(vacancy, application))
    except Exception:
        # Заявка уже сохранена в базе — из-за сбоя почты её не теряем,
        # просто записываем ошибку в лог, чтобы разобраться
        logger.exception("Не удалось отправить уведомление о заявке")
