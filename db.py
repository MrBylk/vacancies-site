import sqlite3
from pathlib import Path

# Файл базы лежит рядом с этим скриптом, откуда бы ни запускали сервер
DB_PATH = Path(__file__).parent / "vacancies.db"

# Стартовые вакансии: попадут в базу только при первом запуске, когда она пустая.
# id не указываем — база назначит его сама (AUTOINCREMENT).
SEED_VACANCIES = [
    {
        "title": "Водитель категории C",
        "salary": "от 80 000 ₽",
        "description": "Развоз продукции по городу. График 5/2, официальное оформление.",
        "needs_license": True,
    },
    {
        "title": "Кладовщик",
        "salary": "от 55 000 ₽",
        "description": "Приёмка и отгрузка товара, работа со сканером. Обучение на месте.",
        "needs_license": False,
    },
    {
        "title": "Менеджер по продажам",
        "salary": "от 60 000 ₽ + %",
        "description": "Работа с входящими заявками и постоянными клиентами.",
        "needs_license": False,
    },
    {
        "title": "Менеджер по работе с клиентами",
        "salary": "от 40 000 ₽",
        "description": "Работа на входящих звонках и чатах",
        "needs_license": False,
    },
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    # Строки будут вести себя как словари: row["title"] вместо row[1]
    conn.row_factory = sqlite3.Row
    # В SQLite проверка внешних ключей по умолчанию выключена — включаем
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Создаёт таблицу, если её ещё нет, и заполняет стартовыми вакансиями."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vacancies (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT    NOT NULL,
                salary        TEXT    NOT NULL DEFAULT '',
                description   TEXT    NOT NULL DEFAULT '',
                needs_license INTEGER NOT NULL DEFAULT 0,  -- 0 = нет, 1 = да
                is_active     INTEGER NOT NULL DEFAULT 1,  -- 0 = скрыта с сайта
                created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Заявки соискателей. vacancy_id ссылается на вакансию (внешний ключ)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                vacancy_id  INTEGER NOT NULL REFERENCES vacancies(id),
                full_name   TEXT    NOT NULL,
                phone       TEXT    NOT NULL,
                specialty   TEXT    NOT NULL,
                experience  TEXT    NOT NULL DEFAULT '',
                age         INTEGER NOT NULL,
                has_license INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Миграция: колонка появилась позже, чем таблица. CREATE TABLE IF NOT EXISTS
        # её не добавит в уже созданную таблицу — добавляем сами, если её нет.
        # consent_at — когда кандидат дал согласие (доказательство для 152-ФЗ)
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(applications)")]
        if "consent_at" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN consent_at TEXT")

        count = conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]
        if count == 0:
            # Знаки ? — параметры запроса. Значения подставляет sqlite3,
            # а не мы через f-строку: так защищаемся от SQL-инъекций.
            conn.executemany(
                "INSERT INTO vacancies (title, salary, description, needs_license) "
                "VALUES (?, ?, ?, ?)",
                [
                    (v["title"], v["salary"], v["description"], v["needs_license"])
                    for v in SEED_VACANCIES
                ],
            )


def get_active_vacancies():
    """Вакансии, которые видны на сайте: сначала самые новые."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM vacancies WHERE is_active = 1 ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_vacancy(vacancy_id):
    """Одна активная вакансия по id или None, если её нет или она скрыта."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM vacancies WHERE id = ? AND is_active = 1", (vacancy_id,)
        ).fetchone()
    return dict(row) if row else None


def add_application(vacancy_id, data):
    """Сохраняет заявку. data — словарь с уже проверенными полями формы."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO applications "
            "(vacancy_id, full_name, phone, specialty, experience, age, has_license, consent_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                vacancy_id,
                data["full_name"],
                data["phone"],
                data["specialty"],
                data["experience"],
                data["age"],
                data["has_license"],
            ),
        )


# ---------- Функции для админки ----------

def get_all_vacancies():
    """Все вакансии, включая скрытые, с количеством заявок по каждой."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT v.*, COUNT(a.id) AS applications_count
            FROM vacancies v
            LEFT JOIN applications a ON a.vacancy_id = v.id
            GROUP BY v.id
            ORDER BY v.is_active DESC, v.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_vacancy(vacancy_id):
    """Вакансия по id, даже скрытая. None, если такой нет."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)
        ).fetchone()
    return dict(row) if row else None


def create_vacancy(data):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vacancies (title, salary, description, needs_license) "
            "VALUES (?, ?, ?, ?)",
            (data["title"], data["salary"], data["description"], data["needs_license"]),
        )


def update_vacancy(vacancy_id, data):
    with get_connection() as conn:
        conn.execute(
            "UPDATE vacancies SET title = ?, salary = ?, description = ?, needs_license = ? "
            "WHERE id = ?",
            (
                data["title"],
                data["salary"],
                data["description"],
                data["needs_license"],
                vacancy_id,
            ),
        )


def toggle_vacancy(vacancy_id):
    """Скрыть активную вакансию или снова показать скрытую."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE vacancies SET is_active = 1 - is_active WHERE id = ?",
            (vacancy_id,),
        )


def get_applications():
    """Все заявки с названием вакансии, сначала новые."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.*, v.title AS vacancy_title
            FROM applications a
            JOIN vacancies v ON v.id = a.vacancy_id
            ORDER BY a.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]
