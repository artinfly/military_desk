# military_desk — «Военно-учётный стол»

Веб-версия АС «Военно-учётный стол» на Django + PostgreSQL: учётные карточки
работников, воинский учёт, справочники и отчёты. Проект в разработке.

В репозитории только код. Данные — вымышленные; реальные персональные данные
в репозиторий не попадают.

## Что нужно заранее

- Python 3.14
- PostgreSQL (16 и новее)
- git

## Установка с нуля

Команды выполняются в терминале из папки проекта (Windows).

1. Скачать проект:

   ```bash
   git clone https://github.com/artinfly/military_desk.git
   cd military_desk
   ```

2. Создать виртуальное окружение и поставить библиотеки.
   У проекта свой Python в папке `.venv`, чтобы его библиотеки не мешали другим проектам.

   ```bash
   py -3.14 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Создать файл настроек `.env`: скопировать `.env.example` в `.env` и заполнить.
   `.env` хранит секреты этой машины и в git не попадает.
   - `SECRET_KEY` — получить командой ниже и вставить результат:

     ```bash
     .venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
     ```

   - `DB_USER`, `DB_PASSWORD`, `DB_HOST` — пользователь, пароль и адрес PostgreSQL.
   - `DB_NAME` — имя базы (по умолчанию `military_desk_test`).

4. Создать пустую базу с именем из `DB_NAME` (например, в DBeaver:
   правой кнопкой по «Базы данных» → «Создать новую базу данных»).
   Django создаёт таблицы, но не саму базу.

5. Создать таблицы в базе:

   ```bash
   .venv\Scripts\python.exe manage.py migrate
   ```

6. Создать администратора (пароль вводится в терминале и не отображается):

   ```bash
   .venv\Scripts\python.exe manage.py createsuperuser
   ```

7. Запустить сервер разработки и открыть http://127.0.0.1:8000/
   (админка — http://127.0.0.1:8000/admin/). Остановить — Ctrl+C.

   ```bash
   .venv\Scripts\python.exe manage.py runserver
   ```

## После обновления кода

```bash
git pull
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
```

`pip install` ставит новые библиотеки, если они появились, `migrate` применяет
новые изменения базы.

## Структура проекта

```
config/            настройки проекта (settings.py) и адреса сайта (urls.py)
core/              приложение: модели (таблицы), страницы, админка, миграции
manage.py          команды проекта: runserver, migrate, createsuperuser и др.
requirements.txt   библиотеки с точными версиями
.env.example       образец настроек для .env
```
