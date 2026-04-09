# HR System (Django)

Веб‑система HR‑аналитики на Django:
- Дашборд
- Индивидуальный анализ
- Массовый мониторинг
- Роли HR / HR_ADMIN, админка
- Датасеты каждого HR сохраняются как профили

## Файлы моделей (обязательно)

Положите в `assets/` (или рядом с проектом):
- `burnout_model.cbm`
- `catboost_model.pkl`

CSV `Employee.csv` и `test.csv` больше не обязательны: каждый HR загружает свои CSV в разделе **Датасеты**.

## Установка

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Запуск

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Откройте `http://127.0.0.1:8000/`.

## Доступы (HR / Admin)

### Что значит `is_staff` и `is_superuser`
- `is_staff` — позволяет войти в `/admin/`, но действия зависят от permissions.
- `is_superuser` — полный доступ ко всему (permissions игнорируются).

### Рекомендуемая схема
- Группа `HR` — доступ к страницам приложения.
- Группа `HR_ADMIN` + `is_staff=True` — доступ в `/admin/` (кастомная админка) и управление системой.
- `superuser` — только для владельца/главного админа.

### Создание пользователей

HR пользователь (доступ в приложение):
```powershell
.\.venv\Scripts\python.exe manage.py create_hr_user hr hr12345
```

Админ пользователь (ограниченный, доступ в админку; опционально также дать доступ в приложение):
```powershell
.\.venv\Scripts\python.exe manage.py create_admin_user admin admin12345 --also-hr
```

Суперпользователь (полный доступ):
```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Админка: `http://127.0.0.1:8000/admin/`
