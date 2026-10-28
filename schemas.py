import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationForm(BaseModel):
    """Правила проверки формы заявки. Pydantic сам приведёт типы: "25" → 25."""

    # Убираем пробелы по краям у всех строк: "  Иван " → "Иван"
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=100)
    phone: str
    specialty: str = Field(min_length=2, max_length=100)
    experience: str = Field(default="", max_length=1000)
    age: int = Field(ge=16, le=80)
    # Галочка в HTML-форме: если отмечена, браузер присылает "on", если нет — ничего
    has_license: bool = False
    # Согласие на обработку персональных данных (152-ФЗ) — без него заявку не принимаем.
    # validate_default=True обязателен: снятую галочку браузер не присылает вовсе,
    # подставляется False, а без этого флага Pydantic не запускает валидатор для значения по умолчанию
    consent: bool = Field(default=False, validate_default=True)

    @field_validator("consent")
    @classmethod
    def check_consent(cls, value):
        if not value:
            raise ValueError("no consent")
        return value

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        digits = re.sub(r"\D", "", value)  # оставляем только цифры
        if len(digits) == 11 and digits[0] in "78":
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("bad phone")
        # Храним в одном формате, как бы человек ни ввёл: +7 (999) 123-45-67
        return f"+7 ({digits[:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:]}"


# Понятные сообщения для людей вместо английских текстов Pydantic
ERROR_MESSAGES = {
    "full_name": "Укажите имя и фамилию",
    "phone": "Укажите телефон в формате +7 999 123-45-67",
    "specialty": "Укажите специальность",
    "experience": "Слишком длинный текст — сократите, пожалуйста",
    "age": "Укажите возраст числом от 16 до 80",
    "consent": "Без согласия на обработку персональных данных мы не можем принять заявку",
}


class VacancyForm(BaseModel):
    """Форма вакансии в админке."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=100)
    salary: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=2000)
    needs_license: bool = False


VACANCY_ERROR_MESSAGES = {
    "title": "Укажите название вакансии (от 2 до 100 символов)",
    "salary": "Слишком длинно — до 50 символов",
    "description": "Слишком длинное описание — до 2000 символов",
}
