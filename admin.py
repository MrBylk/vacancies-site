import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

import db
from schemas import VACANCY_ERROR_MESSAGES, VacancyForm
from templating import collect_errors, templates

# Пароль берём из переменной окружения, а не храним в коде:
# код попадёт на GitHub, а пароль туда попадать не должен
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
if ADMIN_PASSWORD == "admin":
    print("ВНИМАНИЕ: пароль админки по умолчанию 'admin'. "
          "Перед выкладкой задайте переменную окружения ADMIN_PASSWORD.")


def require_admin(request: Request):
    """Зависимость: пускает дальше только вошедшего админа, остальных — на вход."""
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


# Все маршруты этого роутера начинаются с /admin
router = APIRouter(prefix="/admin")
# А этот — тоже /admin, но каждый маршрут в нём требует входа
protected = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


# ---------- Вход и выход ----------

@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    password = form.get("password", "")
    # compare_digest сравнивает за одинаковое время — так пароль нельзя
    # подобрать по тому, насколько быстро сервер отвечает «неверно»
    if secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode()):
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": "Неверный пароль"}, status_code=401
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


# ---------- Вакансии ----------

@protected.get("")
def vacancies_list(request: Request):
    return templates.TemplateResponse(
        request, "admin/vacancies.html", {"vacancies": db.get_all_vacancies()}
    )


def get_vacancy_or_404(vacancy_id: int):
    vacancy = db.get_vacancy(vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Вакансия не найдена")
    return vacancy


def render_vacancy_form(request, vacancy, values, errors, status_code=200):
    # Одна и та же форма для «создать» (vacancy=None) и «изменить»
    return templates.TemplateResponse(
        request,
        "admin/vacancy_form.html",
        {"vacancy": vacancy, "values": values, "errors": errors},
        status_code=status_code,
    )


@protected.get("/vacancies/new")
def vacancy_new_form(request: Request):
    return render_vacancy_form(request, None, {}, {})


@protected.post("/vacancies/new")
async def vacancy_new_submit(request: Request):
    values = dict(await request.form())
    try:
        vacancy_data = VacancyForm(**values)
    except ValidationError as e:
        errors = collect_errors(e, VACANCY_ERROR_MESSAGES)
        return render_vacancy_form(request, None, values, errors, status_code=422)
    db.create_vacancy(vacancy_data.model_dump())
    return RedirectResponse("/admin", status_code=303)


@protected.get("/vacancies/{vacancy_id}/edit")
def vacancy_edit_form(request: Request, vacancy_id: int):
    vacancy = get_vacancy_or_404(vacancy_id)
    # Заполняем форму текущими значениями вакансии
    return render_vacancy_form(request, vacancy, vacancy, {})


@protected.post("/vacancies/{vacancy_id}/edit")
async def vacancy_edit_submit(request: Request, vacancy_id: int):
    vacancy = get_vacancy_or_404(vacancy_id)
    values = dict(await request.form())
    try:
        vacancy_data = VacancyForm(**values)
    except ValidationError as e:
        errors = collect_errors(e, VACANCY_ERROR_MESSAGES)
        return render_vacancy_form(request, vacancy, values, errors, status_code=422)
    db.update_vacancy(vacancy_id, vacancy_data.model_dump())
    return RedirectResponse("/admin", status_code=303)


@protected.post("/vacancies/{vacancy_id}/toggle")
def vacancy_toggle(vacancy_id: int):
    get_vacancy_or_404(vacancy_id)
    db.toggle_vacancy(vacancy_id)
    return RedirectResponse("/admin", status_code=303)


# ---------- Заявки ----------

@protected.get("/applications")
def applications_list(request: Request):
    return templates.TemplateResponse(
        request, "admin/applications.html", {"applications": db.get_applications()}
    )
