# Telegram бот для записи к мастеру маникюра

## Что реализовано
- `/start`: красивое приветствие на украинском → сразу отправляются прайсы → затем кнопка **«Записатися на прийом»**
- Запись: услуга → мастер → день недели → время → имя/телефон → комментарий → подтверждение
- Слоты хранятся в `SQLite` (`bot.sqlite3`) и защищены от двойной записи
- При указании `BOT_ADMIN_CHAT_ID` бот уведомляет администратора о новой заявке

## Настройка
1. Открой папку `bot/`
2. Создай файл `bot/.env` (копируй `bot/.env.example`) и заполни:
   - `BOT_TOKEN`
   - `BOT_ADMIN_CHAT_ID` (если нужно уведомление админа)
   - `MODE` (`polling` для теста локально или `webhook` для прод)
3. Отредактируй `bot/data/content.json`:
   - `greeting`, `prices_message`
   - `master_name`
   - `services` (список услуг и цен)
   - `booking.work_start`, `booking.work_end`, `booking.slot_minutes`

## Запуск (polling)
Из папки `bot/`:
```powershell
py main.py
```

## Webhook
Код поддерживает webhook, но для реального запуска нужно:
- `MODE=webhook`
- настроенный доступный извне URL с HTTPS для `WEBHOOK_BASE_URL + WEBHOOK_PATH`

Если хочешь, подскажу конкретные настройки под твой хостинг (Render/Railway/VPS и т.п.).

