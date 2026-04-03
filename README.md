
```markdown
# Backend-приложение для автоматизации закупок

## Описание
Сервис позволяет покупателям заказывать товары от разных поставщиков через REST API.  
Поставщики могут загружать прайс-листы в формате YAML, управлять приёмом заказов и просматривать свои заказы.

### Продвинутые возможности
- Асинхронные задачи (Celery + Redis): импорт прайс-листов, отправка писем, ресайз изображений.
- Загрузка аватаров пользователей и изображений товаров с автоматическим созданием миниатюр (thumbnail, medium, large).
- Социальная аутентификация через Google и GitHub (allauth + ручные эндпоинты).
- Кэширование запросов к БД (django-cachalot + Redis).
- Профилирование запросов (django-silk).
- Мониторинг ошибок (Rollbar).
- Автоматическая генерация OpenAPI-документации (drf-spectacular) с интерфейсами Swagger UI и ReDoc.
- Throttling (ограничение частоты запросов).
- Docker-контейнеризация (Django, PostgreSQL, Redis, Celery worker/beat).

## Технологии
- Python 3.10+
- Django 5.0 / Django REST Framework
- Celery + Redis (асинхронные задачи)
- PostgreSQL (или SQLite для разработки)
- Docker / Docker Compose
- django-allauth (социальная авторизация)
- Pillow (обработка изображений)
- django-cachalot (кэширование запросов)
- django-silk (профилирование)
- Rollbar (мониторинг ошибок)
- drf-spectacular (документация API)

## Требования
- Установленные **Docker** и **Docker Compose** (для запуска в контейнерах)
- (Опционально) Python 3.10 для локального запуска без Docker

---

## Запуск проекта

### 🐳 С использованием Docker (рекомендуется)

1. **Клонируйте репозиторий** и перейдите в папку проекта:
   ```bash
   git clone <url-репозитория>
   cd <папка-проекта>
   ```

2. **Создайте файл `.env`** (см. раздел «Переменные окружения»).  
   Минимальный пример:
   ```ini
   DEBUG=1
   DATABASE_URL=postgres://diplom_user:password@db:5432/diplom_db
   REDIS_URL=redis://redis:6379/0
   EMAIL_HOST=smtp.mail.ru
   EMAIL_HOST_USER=your_email@mail.ru
   EMAIL_HOST_PASSWORD=your_app_password
   ADMIN_EMAIL=admin@example.com
   # Rollbar (опционально)
   ROLLBAR_ACCESS_TOKEN=ваш_токен
   ```

3. **Запустите контейнеры**:
   ```bash
   docker-compose up -d --build
   ```
   Сервисы будут доступны:
   - Django: `http://localhost:8000`
   - PostgreSQL: порт `5432` (user: `diplom_user`, password: `password`, db: `diplom_db`)
   - Redis: порт `6379`

4. **Примените миграции** и создайте суперпользователя:
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

5. **Остановка контейнеров**:
   ```bash
   docker-compose down
   ```

---

### 💻 Локальный запуск (без Docker)

1. **Перейдите в папку проекта** и активируйте виртуальное окружение:
   ```bash
   cd /путь/к/проекту
   source .venv/bin/activate          # Linux/macOS
   .venv\Scripts\activate             # Windows
   ```

2. **Установите зависимости**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Настройте базу данных** в файле `.env`:
   - Для PostgreSQL:
     ```ini
     DATABASE_URL=postgres://user:password@localhost:5432/diplom_db
     ```
   - Для SQLite (для тестирования) – не указывайте `DATABASE_URL` или укажите `sqlite:///db.sqlite3`.

4. **Примените миграции** и создайте суперпользователя:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Запустите сервер разработки**:
   ```bash
   python manage.py runserver
   ```
   Приложение будет доступно: [http://127.0.0.1:8000](http://127.0.0.1:8000)

6. **Запустите Celery** (для асинхронных задач):
   - Убедитесь, что Redis запущен:
     ```bash
     docker run -d --name redis_local -p 6379:6379 redis:7
     ```
   - Запустите воркер (в отдельном окне терминала):
     ```bash
     celery -A config worker --loglevel=info --pool=solo
     ```
     > **Примечание:** на Windows используйте `--pool=solo` (однопоточный режим). На Linux/macOS параметр можно опустить.
   - При необходимости запустите бит (для периодических задач):
     ```bash
     celery -A config beat --loglevel=info
     ```

---

## 👥 Создание пользователей и магазинов

### Суперпользователь (администратор)
```bash
python manage.py createsuperuser
```

### Пользователь-магазин
```bash
python manage.py shell
```
```python
from backend.models import User
user = User.objects.create_user(
    email='shop@example.com',
    password='shop123',
    type='shop',
    is_active=True
)
exit()
```

### Получение токена для магазина
```bash
python manage.py shell
```
```python
from backend.models import User
from rest_framework.authtoken.models import Token
user = User.objects.get(email='shop@example.com')
token, _ = Token.objects.get_or_create(user=user)
print(token.key)
exit()
```

### Создание магазина (связывание с пользователем)
- Через админку: `http://127.0.0.1:8000/admin/backend/shop/add/`
- Или через shell:
  ```python
  from backend.models import Shop, User
  user = User.objects.get(email='shop@example.com')
  shop = Shop.objects.create(name='Связной', user=user, state=True)
  ```

---

## 📦 Импорт товаров

1. **Подготовьте YAML-файл** (пример `shop1.yaml` лежит в папке `data/`).
2. **Запустите временный HTTP-сервер** (если файл не доступен по внешней ссылке):
   ```bash
   cd data
   python -m http.server 8001
   ```
   Файл будет доступен по адресу `http://localhost:8001/shop1.yaml`.
3. **Отправьте запрос от имени магазина**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/partner/update \
     -H "Authorization: Token <ваш_токен>" \
     -H "Content-Type: application/json" \
     -d '{"url": "http://localhost:8001/shop1.yaml"}'
   ```

После успешного импорта товары появятся в админке и будут доступны через API.

---

## 🧪 Основные API эндпоинты

| Метод            | URL                                      | Описание                                             | Пример тела запроса |
|------------------|------------------------------------------|------------------------------------------------------|---------------------|
| POST             | `/api/v1/user/register`                  | Регистрация покупателя                               | `{"first_name": "Иван", "last_name": "Петров", "email": "user@example.com", "password": "Test123!", "company": "", "position": ""}` |
| POST             | `/api/v1/user/register/confirm`          | Подтверждение email                                  | `{"email": "user@example.com", "token": "<token>"}` |
| POST             | `/api/v1/user/login`                     | Авторизация (получение токена)                       | `{"email": "user@example.com", "password": "Test123!"}` |
| GET              | `/api/v1/categories`                     | Список категорий                                     | — |
| GET              | `/api/v1/shops`                          | Список активных магазинов                            | — |
| GET              | `/api/v1/products`                       | Список товаров (фильтры: `?shop_id=1&category_id=2&search=iPhone`) | — |
| GET              | `/api/v1/product/<id>`                   | Детальная информация о товаре                        | — |
| GET / POST / PUT / DELETE | `/api/v1/basket`                | Работа с корзиной (просмотр, добавление, обновление, удаление) | `POST: {"items": "[{\"product_info\": 1, \"quantity\": 2}]"}` |
| GET / POST / PATCH | `/api/v1/order`                        | Просмотр / создание / отмена заказа                  | `POST: {"id": 1, "contact": 1}` |
| POST             | `/api/v1/partner/update`                 | Загрузка прайс-листа (только для магазинов)          | `{"url": "http://localhost:8001/shop1.yaml"}` |
| GET / POST       | `/api/v1/partner/state`                  | Получение / изменение статуса приёма заказов         | `POST: {"state": true}` |
| GET / POST / PUT / DELETE | `/api/v1/user/contact`          | Управление контактами доставки                       | `POST: {"type": "address", "city": "Пермь", "street": "Монастырская", "house": "1", "phone": "+79991234555"}` |
| GET / POST       | `/api/v1/user/details`                   | Просмотр / изменение данных пользователя             | `POST: {"first_name": "Новое имя"}` |
| POST             | `/user/avatar/`                          | Загрузка аватара пользователя (multipart/form-data)  | `-F "image=@avatar.jpg"` |
| POST             | `/api/v1/auth/google/`                   | Социальная авторизация через Google                  | `{"token": "google_access_token"}` |
| POST             | `/api/v1/auth/github/`                   | Социальная авторизация через GitHub                  | `{"token": "github_access_token"}` |
| GET              | `/api/v1/test-rollbar/`                  | Тестовый эндпоинт для проверки Rollbar               | — |

**Примечания:**
- Для эндпоинтов, требующих авторизации, передавайте заголовок: `Authorization: Token <ваш_токен>`.
- Контакты имеют тип `'phone'` или `'address'`. У пользователя может быть **только один телефон** и **не более пяти адресов**.
- Аватар загружается через `POST /user/avatar/` с `Content-Type: multipart/form-data`. Изображение автоматически обрабатывается в фоне (создаются три пресета: thumbnail, medium, large).

---

## 📚 Документация API

После запуска сервера документация доступна по адресам:
- **Swagger UI:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **ReDoc:** [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
- **Схема OpenAPI (JSON):** [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

---

## 🛠 Профилирование запросов (Silk)

Интерфейс Silk доступен по адресу: [http://127.0.0.1:8000/silk/](http://127.0.0.1:8000/silk/).  
Здесь можно посмотреть все выполненные запросы, их время, дублирующиеся SQL-запросы и т.д.

---

## 📊 Мониторинг ошибок (Rollbar)

Если в `.env` указан `ROLLBAR_ACCESS_TOKEN`, то все необработанные исключения будут автоматически отправляться в панель Rollbar.  
Тестовый эндпоинт: `GET /api/v1/test-rollbar/` – вызывает исключение для проверки интеграции.

---

## 🗄 Кэширование запросов

Проект использует **django-cachalot** для автоматического кэширования результатов ORM-запросов. Кэш хранится в Redis (база 1). При изменении данных соответствующие кэши инвалидируются автоматически.

---

## 🧪 Запуск тестов

```bash
pytest --cov=backend --cov-report=term-missing
```
Покрытие кода составляет **93%** (113 тестов проходят, 1 осознанно пропущен).

---

## Админка
Админ-панель доступна по адресу: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)  
В админке можно:
- Управлять пользователями, магазинами, категориями, товарами, параметрами.
- Просматривать и редактировать заказы (изменять статус – покупателю отправляется email).
- Запускать импорт прайс-листа для магазина (действие «Импортировать прайс-лист (асинхронно)»).
- Просматривать загруженные изображения и аватары.

---

## Celery задачи
- `send_email_task` – асинхронная отправка email (HTML-письма).
- `do_import_task` – асинхронный импорт прайс-листа из YAML.
- `process_image` – асинхронное создание миниатюр изображений.

---

## Переменные окружения
Файл `.env` (создаётся в корне проекта) должен содержать:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `SECRET_KEY` | Секретный ключ Django | `your-secret-key-here` |
| `DEBUG` | Режим отладки (`1` – включён, `0` – выключен) | `1` |
| `DATABASE_URL` | URL подключения к базе данных | `postgres://user:pass@db:5432/diplom_db` |
| `REDIS_URL` | URL подключения к Redis | `redis://redis:6379/0` |
| `EMAIL_HOST` | SMTP-сервер | `smtp.mail.ru` |
| `EMAIL_HOST_USER` | Email для отправки писем | `your_email@mail.ru` |
| `EMAIL_HOST_PASSWORD` | Пароль (или пароль приложения) | `******` |
| `EMAIL_PORT` | Порт SMTP | `465` |
| `EMAIL_USE_SSL` | Использовать SSL | `True` |
| `ADMIN_EMAIL` | Email администратора (для накладных) | `admin@example.com` |
| `ROLLBAR_ACCESS_TOKEN` | Токен доступа Rollbar (опционально) | `36ceb1c94eef41baaecd305b43baa217` |
| `ROLLBAR_ENVIRONMENT` | Окружение для Rollbar | `development` или `production` |

> **Для Mail.ru:** требуется пароль приложения. Создайте его в настройках безопасности почтового ящика.

---

## 📌 Полезные ссылки
- **Главная страница API:** [http://127.0.0.1:8000/api/v1/](http://127.0.0.1:8000/api/v1/)
- **Список товаров:** [http://127.0.0.1:8000/api/v1/products](http://127.0.0.1:8000/api/v1/products)
- **Категории:** [http://127.0.0.1:8000/api/v1/categories](http://127.0.0.1:8000/api/v1/categories)
- **Магазины:** [http://127.0.0.1:8000/api/v1/shops](http://127.0.0.1:8000/api/v1/shops)
- **Swagger документация:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **Silk профилирование:** [http://127.0.0.1:8000/silk/](http://127.0.0.1:8000/silk/)
```

