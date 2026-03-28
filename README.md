Вот финальная, аккуратная версия `README.md`:

```markdown
# Дипломный проект: Backend-приложение для автоматизации закупок

## Описание
Сервис позволяет покупателям заказывать товары от разных поставщиков через REST API.  
Поставщики могут загружать прайс-листы в формате YAML, управлять приёмом заказов и просматривать свои заказы.

## Технологии
- Python 3.10+
- Django 5.0 / Django REST Framework
- Celery + Redis (асинхронные задачи)
- PostgreSQL
- Docker / Docker Compose

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

**Примечания:**
- Для эндпоинтов, требующих авторизации, передавайте заголовок: `Authorization: Token <ваш_токен>`.
- Контакты имеют тип `'phone'` или `'address'`. У пользователя может быть **только один телефон** и **не более пяти адресов**.
---

## Админка
Админ-панель доступна по адресу: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)  
В админке можно:
- Управлять пользователями, магазинами, категориями, товарами, параметрами.
- Просматривать и редактировать заказы (изменять статус – покупателю отправляется email).
- Запускать импорт прайс-листа для магазина (действие «Импортировать прайс-лист (асинхронно)»).

---

## Celery задачи
- `send_email_task` – асинхронная отправка email (HTML-письма).
- `do_import_task` – асинхронный импорт прайс-листа из YAML.

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

> **Для Mail.ru:** требуется пароль приложения. Создайте его в настройках безопасности почтового ящика.

---

## 📌Ссылки
- **Главная страница API:** [http://127.0.0.1:8000/api/v1/](http://127.0.0.1:8000/api/v1/)
- **Список товаров:** [http://127.0.0.1:8000/api/v1/products](http://127.0.0.1:8000/api/v1/products)
- **Категории:** [http://127.0.0.1:8000/api/v1/categories](http://127.0.0.1:8000/api/v1/categories)
- **Магазины:** [http://127.0.0.1:8000/api/v1/shops](http://127.0.0.1:8000/api/v1/shops)

```
