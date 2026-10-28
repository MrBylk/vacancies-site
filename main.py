import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.sessions import SessionMiddleware

import admin
import antispam
import config
import db
import notifications
from schemas import ERROR_MESSAGES, ApplicationForm
from templating import collect_errors, templates

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код до yield выполняется один раз при запуске сервера
    db.init_db()
    yield


app = FastAPI(title="Сайт вакансий", lifespan=lifespan)

# Сессии: после входа в админку браузер получает cookie, подписанную ключом
# из config.py. Подделать её без ключа нельзя
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=60 * 60 * 24 * 7,  # неделя
)

# Папка static — для CSS, картинок
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(admin.router)
app.include_router(admin.protected)


def get_vacancy_or_404(vacancy_id: int):
    vacancy = db.get_active_vacancy(vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")
    return vacancy


@app.get("/")
def index(request: Request):
    # Берём из базы только активные вакансии и отдаём их в шаблон
    vacancies = db.get_active_vacancies()
    return templates.TemplateResponse(request, "index.html", {"vacancies": vacancies})


def render_apply_form(request, vacancy, values, errors, status_code=200, expired=False):
    # Каждый показ формы — со свежим антиспам-токеном (время открытия формы)
    return templates.TemplateResponse(
        request,
        "apply.html",
        {
            "vacancy": vacancy,
            "values": values,
            "errors": errors,
            "expired": expired,
            "form_token": antispam.make_form_token(),
        },
        status_code=status_code,
    )


@app.get("/vacancy/{vacancy_id}/apply")
def apply_form(request: Request, vacancy_id: int):
    # Пустая форма заявки
    vacancy = get_vacancy_or_404(vacancy_id)
    return render_apply_form(request, vacancy, {}, {})


@app.post("/vacancy/{vacancy_id}/apply")
async def apply_submit(request: Request, vacancy_id: int, background_tasks: BackgroundTasks):
    vacancy = get_vacancy_or_404(vacancy_id)
    values = dict(await request.form())

    spam_check = antispam.check_form(values)
    if spam_check == "bot":
        # Боту делаем вид, что всё прошло успешно: если показать ошибку,
        # автор бота поймёт, что его поймали, и начнёт подстраиваться
        logger.info("Антиспам: отклонена заявка от бота на вакансию %s", vacancy_id)
        return RedirectResponse(f"/vacancy/{vacancy_id}/thanks", status_code=303)
    if spam_check == "expired":
        return render_apply_form(request, vacancy, values, {}, status_code=422, expired=True)

    try:
        application = ApplicationForm(**values)
    except ValidationError as e:
        # Собираем ошибки по полям и показываем форму снова —
        # с уже введёнными значениями, чтобы человеку не набирать всё заново
        errors = collect_errors(e, ERROR_MESSAGES)
        return render_apply_form(request, vacancy, values, errors, status_code=422)

    data = application.model_dump()
    db.add_application(vacancy_id, data)
    # Письмо отправится уже после того, как кандидат получит ответ,
    # — ему не придётся ждать почтовый сервер
    background_tasks.add_task(notifications.notify_new_application, vacancy, data)
    # После успешной отправки перенаправляем на другую страницу (паттерн
    # Post/Redirect/Get), чтобы F5 не отправил заявку второй раз
    return RedirectResponse(f"/vacancy/{vacancy_id}/thanks", status_code=303)


@app.get("/vacancy/{vacancy_id}/thanks")
def apply_thanks(request: Request, vacancy_id: int):
    vacancy = get_vacancy_or_404(vacancy_id)
    return templates.TemplateResponse(request, "thanks.html", {"vacancy": vacancy})


# ---------- Юридические документы (152-ФЗ) ----------

@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "legal/privacy.html")


@app.get("/consent")
def consent(request: Request):
    return templates.TemplateResponse(request, "legal/consent.html")
