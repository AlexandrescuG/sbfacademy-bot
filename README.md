# SBFAcademy Bot

Telegram-бот академии SBF для захвата лидов, двухшагового онбординга и коммуникации с клиентами. Включает Flask-панель для операторов.

## Stack

- **Python 3.11+** — основной язык
- **python-telegram-bot** — Telegram Bot API
- **Flask** — веб-панель для операторов
- **SQLite** — локальное хранилище лидов и диалогов
- **EspoCRM** (опционально) — CRM-интеграция через REST API

## Features

- Двухшаговый IVR-онбординг: сбор контактных данных → подтверждение интереса
- Выбор брокера (AvaTrade, Daoti) с реферальными ссылками
- Проверка подписки на новостной канал перед выдачей материалов
- PDF-презентация SBF Performance для квалифицированных лидов
- Telegram-уведомление менеджеру при каждом новом лиде
- Flask-панель: операторы видят список лидов и могут писать им напрямую
- Интеграция с EspoCRM: автосоздание контакта при согласии

## Project Structure

```
SBFAcademy_bot/
├── SBFAcademy_bot.py      # Основной бот + Flask приложение
├── templates/             # HTML-шаблоны Flask панели
├── .env.example           # Пример переменных окружения
└── Flask.env.example      # Пример конфига Flask-операторов
```

## Setup

```bash
# 1. Установить зависимости
pip install python-telegram-bot flask python-dotenv requests

# 2. Настроить переменные окружения
cp .env.example .env
cp Flask.env.example Flask.env
# Заполнить .env и Flask.env реальными значениями

# 3. Запустить бота
python3 SBFAcademy_bot.py
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Telegram Bot Token от @BotFather |
| `ADMIN_IDS` | Telegram ID администраторов (через запятую) |
| `ADMIN_PASSWORD` | Пароль для доступа к Flask-панели |
| `MANAGER_CHAT_ID` | Telegram ID менеджера для уведомлений |
| `LEADS_CHANNEL_ID` | ID канала куда пишутся лиды |
| `OPERATOR_IDS` | Telegram ID операторов (для Flask) |
| `FLASK_SECRET_KEY` | Секрет Flask-сессий (рандомный hex) |
| `ESPOCRM_URL` | URL EspoCRM инстанса (опционально) |
| `ESPOCRM_API_KEY` | API-ключ EspoCRM (опционально) |

## Status

Production — используется для лидогенерации SBF Academy
