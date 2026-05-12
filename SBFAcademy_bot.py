import logging
import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from flask import Flask, redirect, url_for, session, jsonify, request
import threading
import hashlib
import asyncio
import random
from dotenv import load_dotenv
import requests

# ─── ЗАГРУЗКА КОНФИГУРАЦИИ ИЗ .env ────────────────────────────────────────────
load_dotenv()

BOT_TOKEN        = os.getenv("BOT_TOKEN", "ЗАМЕНИТЕ_В_.env")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD", "admin123")
MANAGER_CHAT_ID  = int(os.getenv("MANAGER_CHAT_ID", "0"))
LEADS_CHANNEL_ID = int(os.getenv("LEADS_CHANNEL_ID", "-1003582149393"))
ADMIN_IDS        = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()]
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
OPERATOR_IDS = [int(x) for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()]

# ─── ESPOCRM ───────────────────────────────────────────────────────────────────
ESPOCRM_URL     = os.getenv("ESPOCRM_URL")
ESPOCRM_API_KEY = os.getenv("ESPOCRM_API_KEY")

# ─── ССЫЛКИ КОМПАНИИ ───────────────────────────────────────────────────────────
SUPPORT_LINK     = "https://t.me/SBF_Support"
NEWS_CHANNEL     = "https://t.me/SBFEconomics"
NEWS_CHANNEL_ID  = "@SBFEconomics"   # используется для проверки подписки
WEBSITE          = "https://sbfconsult.com"
BRAND_TAGLINE    = "🎓 *SBF Academy* — обучение трейдингу с нуля до результата"

# ─── ФАЙЛЫ ─────────────────────────────────────────────────────────────────────
PERFORMANCE_PDF  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SBF_Performance_2.pdf")

# ─── ДАННЫЕ БРОКЕРОВ ───────────────────────────────────────────────────────────
BROKERS = {
    "avatrade": {
        "name": "AvaTrade",
        "leverage": "1:400",
        "platforms": "MT4, MT5",
        "spread": "от 0.9 пунктов",
        "bonus": "10%–20%",
        "deposit_methods": "Банк. карты, Skrill, Neteller, PerfectMoney",
        "description": "Надёжный международный брокер с широким выбором инструментов. Стабильный доступ к рынкам и высокий уровень сервиса.",
        "url": "https://avatrade.com/?tag=184200&utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
    "daoti": {
        "name": "Daoti",
        "leverage": "1:100",
        "platforms": "MT5",
        "spread": "от 0.7 пунктов",
        "bonus": "до 15% на баланс",
        "deposit_methods": "Банк. карта, крипто-переводы",
        "description": "Современный брокер с низкими спредами и быстрым исполнением. Оптимален для крипты и классических активов.",
        "url": "https://daoti.io/?utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
    "fxpro": {
        "name": "FxPro",
        "leverage": "1:500",
        "platforms": "MT4, MT5, cTrader",
        "spread": "от 1.2 пунктов",
        "bonus": "—",
        "deposit_methods": "Карты, Skrill, Neteller, PayPal, Крипто",
        "description": "Профессиональная среда исполнения сделок. Высокая ликвидность и доступ к инновационным платформам.",
        "url": "https://direct-fxpro.com/en/partner/32TQQFd7H?utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
    "capex": {
        "name": "Capex",
        "leverage": "1:400",
        "platforms": "WebTrader, MT5",
        "spread": "от 1.2 пунктов",
        "bonus": "20%–40%",
        "deposit_methods": "Карта, Skrill, Neteller, Перевод",
        "description": "Лицензированный брокер с уникальным веб-терминалом. Прозрачные условия и качественная аналитика.",
        "url": "https://account.capex.com/en/register?sidc=88EA29D5-46D9-472E-AEB2-C6E5C30E822A&utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
    "instaforex": {
        "name": "Instaforex",
        "leverage": "1:1000",
        "platforms": "MT4, MT5, Tick",
        "spread": "0.0–3.0 пунктов",
        "bonus": "30%, 55%, 100%",
        "deposit_methods": "Карты, Skrill, Neteller, PM, Крипто",
        "description": "Лидер рынка по бонусным программам. Уникальные технологии и ликвидность для любых стратегий.",
        "url": "https://www.instaforex.com/en/fast_open_live_account?x=TTVDG&utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
    "alpari": {
        "name": "Alpari",
        "leverage": "1:3000",
        "platforms": "MT4, MT5",
        "spread": "от 1.0 пунктов",
        "bonus": "—",
        "deposit_methods": "Банк. карта, банк. перевод",
        "description": "Брокер с колоссальным опытом. Самое высокое плечо на рынке — максимальная гибкость управления капиталом.",
        "url": "https://alpari.com/en/?utm_source=tgbot&utm_medium=bot&utm_campaign=sbfacademy",
    },
}

# ─── СОСТОЯНИЯ ОНБОРДИНГА ──────────────────────────────────────────────────────
ONBOARD_Q1, ONBOARD_Q2, ONBOARD_Q3, ONBOARD_DONE = range(4)

# ─── ЛОГИРОВАНИЕ ──────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
app_telegram = None
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "sbf_secret_2024")
os.makedirs("logs", exist_ok=True)
os.makedirs("logs/users", exist_ok=True)

# ─── БАЗА ДАННЫХ ───────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
        preferred_name TEXT, phone_number TEXT, first_seen TEXT, last_active TEXT,
        experience_level TEXT, deposit_range TEXT, already_trading TEXT,
        funnel_stage TEXT DEFAULT 'awareness', broker_interest TEXT,
        section_interest TEXT, onboarding_done INTEGER DEFAULT 0,
        followup_24h_sent INTEGER DEFAULT 0, followup_3d_sent INTEGER DEFAULT 0,
        is_subscribed INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        timestamp TEXT, action_type TEXT, details TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS statistics (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        timestamp TEXT, action_type TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )""")
    # Миграция
    existing = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
    for col, col_type in [
        ("preferred_name","TEXT"), ("experience_level","TEXT"), ("deposit_range","TEXT"),
        ("already_trading","TEXT"), ("funnel_stage","TEXT DEFAULT 'awareness'"),
        ("broker_interest","TEXT"), ("section_interest","TEXT"),
        ("onboarding_done","INTEGER DEFAULT 0"), ("followup_24h_sent","INTEGER DEFAULT 0"),
        ("followup_3d_sent","INTEGER DEFAULT 0"), ("is_subscribed","INTEGER DEFAULT 0"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
    conn.commit()
    conn.close()

def update_user_in_db(user_id, username=None, full_name=None, phone_number=None,
                      preferred_name=None, experience_level=None, deposit_range=None,
                      already_trading=None, funnel_stage=None, broker_interest=None,
                      section_interest=None, onboarding_done=None, is_subscribed=None):
    try:
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT OR IGNORE INTO users (user_id, first_seen, last_active) VALUES (?,?,?)", (user_id, now, now))
        updates = {"last_active": now}
        for k, v in [("username", username), ("full_name", full_name), ("phone_number", phone_number),
                     ("preferred_name", preferred_name), ("experience_level", experience_level),
                     ("deposit_range", deposit_range), ("already_trading", already_trading),
                     ("funnel_stage", funnel_stage), ("broker_interest", broker_interest),
                     ("section_interest", section_interest)]:
            if v is not None: updates[k] = v
        if onboarding_done is not None: updates["onboarding_done"] = onboarding_done
        if is_subscribed is not None:   updates["is_subscribed"] = is_subscribed
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", (*updates.values(), user_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"DB error: {e}")
    finally:
        conn.close()

def log_action_in_db(user_id, action_type, details=""):
    try:
        conn = sqlite3.connect("bot.db")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO actions (user_id,timestamp,action_type,details) VALUES (?,?,?,?)", (user_id, now, action_type, details))
        conn.execute("INSERT INTO statistics (user_id,timestamp,action_type) VALUES (?,?,?)", (user_id, now, action_type))
        conn.commit()
        conn.close()
    except: pass

def get_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_display_name(user_id, tg_first_name=""):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT preferred_name, full_name FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]: return row[0]
    if row and row[1]: return row[1].split()[0]
    return tg_first_name or "трейдер"


# ──────────────────────────────────────────────────────────────────────────────
# ПРОВЕРКА ПОДПИСКИ НА КАНАЛ
# ──────────────────────────────────────────────────────────────────────────────
async def check_subscription(bot, user_id: int) -> bool:
    """
    Возвращает True, если пользователь подписан на NEWS_CHANNEL_ID.
    
    ТРЕБОВАНИЯ:
    - Бот должен быть администратором канала @SBFEconomics
    - Канал должен быть публичным (username начинается с @)
    
    Пробует несколько форматов chat_id для надёжности.
    """
    # Список форматов для попытки
    chat_ids_to_try = [
        NEWS_CHANNEL_ID,          # "@SBFEconomics"
        "SBFEconomics",           # без @
        "https://t.me/SBFEconomics",  # полная ссылка
    ]
    
    for chat_id in chat_ids_to_try:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            status = member.status
            logger.info(f"Subscription check [{chat_id}] user={user_id} status={status}")
            return status in (
                ChatMember.MEMBER,
                ChatMember.ADMINISTRATOR,
                ChatMember.OWNER,
                "member",
                "administrator",
                "creator",
            )
        except Exception as e:
            logger.warning(f"Subscription check failed [{chat_id}] user={user_id}: {e}")
            continue
    
    # Если все попытки провалились — логируем и пропускаем проверку
    logger.error(f"All subscription checks failed for user={user_id}. "
                 f"Make sure the bot is an ADMIN of @SBFEconomics channel!")
    # Возвращаем True чтобы не блокировать пользователей при ошибке API
    return True

def subscription_required_keyboard():
    """Клавиатура для незарегистрированных — предлагает подписаться и проверить."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Подписаться на SBFEconomics", url=NEWS_CHANNEL)],
        [InlineKeyboardButton("✅ Я подписался — проверить",    callback_data="check_sub")],
    ])


# ─── КЛАВИАТУРЫ ────────────────────────────────────────────────────────────────
REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("Меню"), KeyboardButton("Поделиться номером", request_contact=True)]],
    resize_keyboard=True, one_time_keyboard=False
)

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Результаты торговли",  callback_data="performance_hook"),
         InlineKeyboardButton("📚 Образование",          callback_data="edu_materials")],
        [InlineKeyboardButton("🏦 Брокеры",              callback_data="brokers"),
         InlineKeyboardButton("📡 Каналы",               callback_data="channels")],
        [InlineKeyboardButton("📈 MetaTrader 5",         callback_data="mt5"),
         InlineKeyboardButton("🔢 Калькулятор риска",    callback_data="risk_calc")],
        [InlineKeyboardButton("📖 Словарь трейдера",     callback_data="glossary")],
        [InlineKeyboardButton("🏢 О нас",                callback_data="about"),
         InlineKeyboardButton("❓ FAQ",                  callback_data="faq")],
    ])

# ─── ВОПРОСЫ ВИКТОРИНЫ ─────────────────────────────────────────────────────────
quiz_questions = {
    "easy": [
        {"question": "Что такое акция?", "options": ["Облигация", "Доля в компании", "Фьючерс", "Купон"], "correct_option": "Доля в компании"},
        {"question": "Что такое брокер?", "options": ["Аналитик", "Регулятор", "Посредник на рынке", "Эмитент"], "correct_option": "Посредник на рынке"},
        {"question": "Что такое стоп-лосс?", "options": ["Уровень прибыли", "Ограничение убытков", "Комиссия", "Спред"], "correct_option": "Ограничение убытков"},
        {"question": "Что такое лот?", "options": ["Кредитное плечо", "Объем сделки", "Спред", "Валюта"], "correct_option": "Объем сделки"},
        {"question": "Что такое спред?", "options": ["Комиссия брокера", "Разница цен покупки и продажи", "Маржа", "Налог"], "correct_option": "Разница цен покупки и продажи"},
        {"question": "Что такое депозит?", "options": ["Процент по кредиту", "Сумма на счете", "Спред", "Дивиденд"], "correct_option": "Сумма на счете"},
        {"question": "Что такое терминал MT5?", "options": ["Финансовый отчёт", "Платформа для торговли", "Стратегия", "Брокер"], "correct_option": "Платформа для торговли"},
        {"question": "Что такое диверсификация?", "options": ["Увеличение позиции", "Распределение рисков", "Фиксация прибыли", "Опционы"], "correct_option": "Распределение рисков"},
        {"question": "Что делает трейдер?", "options": ["Выдаёт кредиты", "Покупает и продает активы", "Регулирует рынок", "Страхует сделки"], "correct_option": "Покупает и продает активы"},
        {"question": "Что такое график цены?", "options": ["Размер комиссии", "Движение стоимости", "Налоговую ставку", "Объём активов"], "correct_option": "Движение стоимости"},
    ],
    "normal": [
        {"question": "Что такое кредитное плечо?", "options": ["Комиссия брокера", "Увеличение позиции за счёт заемных средств", "Тип ордера", "Спред"], "correct_option": "Увеличение позиции за счёт заемных средств"},
        {"question": "Что такое маржа?", "options": ["Прибыль сделки", "Залог для открытия сделки", "Налог", "Дивиденд"], "correct_option": "Залог для открытия сделки"},
        {"question": "Что такое фьючерс?", "options": ["Акция", "Контракт на поставку в будущем", "Облигация", "Опцион"], "correct_option": "Контракт на поставку в будущем"},
        {"question": "Что такое свечной график?", "options": ["Вид индикатора", "Форма отображения цен", "Таймфрейм", "Брокерская лицензия"], "correct_option": "Форма отображения цен"},
        {"question": "Что такое тейк-профит?", "options": ["Ограничение убытков", "Уровень фиксации прибыли", "Комиссия", "Размер лота"], "correct_option": "Уровень фиксации прибыли"},
        {"question": "Что такое волатильность?", "options": ["Объём сделки", "Изменчивость цены", "Налог", "Кредит"], "correct_option": "Изменчивость цены"},
        {"question": "Что такое технический анализ?", "options": ["Налоговый учёт", "Анализ графиков и индикаторов", "Юридическая проверка", "Страхование"], "correct_option": "Анализ графиков и индикаторов"},
        {"question": "Что такое фундаментальный анализ?", "options": ["Технические индикаторы", "Анализ новостей и данных компании", "Брокерская комиссия", "Лот"], "correct_option": "Анализ новостей и данных компании"},
        {"question": "Что такое ордер?", "options": ["Комиссия", "Заявка на сделку", "Маржа", "Регулирующий орган"], "correct_option": "Заявка на сделку"},
        {"question": "Что такое ликвидность?", "options": ["Уровень налога", "Способность быстро продать актив", "Размер комиссии", "Ставка по кредиту"], "correct_option": "Способность быстро продать актив"},
    ],
    "hard": [
        {"question": "Что такое корреляция активов?", "options": ["Комиссия брокера", "Зависимость цен друг от друга", "Прибыльность сделки", "Налог"], "correct_option": "Зависимость цен друг от друга"},
        {"question": "Что такое своп?", "options": ["Тип ордера", "Перенос позиции на следующий день", "Дивиденд", "Налог"], "correct_option": "Перенос позиции на следующий день"},
        {"question": "Что такое скальпинг?", "options": ["Долгосрочные инвестиции", "Краткосрочная торговля внутри дня", "Фондовая лицензия", "Налоговое соглашение"], "correct_option": "Краткосрочная торговля внутри дня"},
        {"question": "Что такое гэп?", "options": ["Налог на прибыль", "Разрыв цен на графике", "Дивиденд", "Комиссия"], "correct_option": "Разрыв цен на графике"},
        {"question": "Что такое плечо 1:100?", "options": ["Размер комиссии", "Увеличение позиции в 100 раз", "Купон", "Налог"], "correct_option": "Увеличение позиции в 100 раз"},
        {"question": "Что такое Margin Call?", "options": ["Прибыль трейдера", "Требование пополнить счет", "Комиссия", "Дивиденд"], "correct_option": "Требование пополнить счет"},
        {"question": "Что такое хеджирование?", "options": ["Размер комиссии", "Страховка от убытков", "Купон облигации", "Налог"], "correct_option": "Страховка от убытков"},
        {"question": "Что такое медвежий рынок?", "options": ["Рост цен", "Падение цен", "Флэт", "Дивиденд"], "correct_option": "Падение цен"},
        {"question": "Что такое алготрейдинг?", "options": ["Регистрация брокера", "Торговля по алгоритму", "Финансовый отчёт", "Налоговая ставка"], "correct_option": "Торговля по алгоритму"},
        {"question": "Что такое стакан цен?", "options": ["Купон облигации", "Книга заявок на бирже", "Финансовый отчёт", "Комиссия"], "correct_option": "Книга заявок на бирже"},
    ],
    "titan": [
        {"question": "Что такое дюрация облигации?", "options": ["Процентная ставка", "Средний срок погашения с учетом выплат", "Купонный доход", "Объем сделки"], "correct_option": "Средний срок погашения с учетом выплат"},
        {"question": "Что такое волатильная улыбка?", "options": ["Купон облигации", "Зависимость волатильности от страйка опциона", "Налоговая льгота", "Процент по кредиту"], "correct_option": "Зависимость волатильности от страйка опциона"},
        {"question": "Что такое квантиль VaR?", "options": ["Комиссия брокера", "Оценка максимального убытка при заданной вероятности", "Маржа", "Дивиденд"], "correct_option": "Оценка максимального убытка при заданной вероятности"},
        {"question": "Что такое gamma в опционах?", "options": ["Процентная ставка", "Чувствительность дельты к цене актива", "Маржа", "Налог"], "correct_option": "Чувствительность дельты к цене актива"},
        {"question": "Что такое модель Black-Scholes?", "options": ["График цены", "Модель оценки цены опциона", "Финансовый отчёт", "Комиссия"], "correct_option": "Модель оценки цены опциона"},
        {"question": "Что такое кривая доходности?", "options": ["Объём сделки", "График доходности облигаций разного срока", "Маржа", "Налоговая льгота"], "correct_option": "График доходности облигаций разного срока"},
        {"question": "Что такое implied volatility?", "options": ["Купон облигации", "Ожидаемая волатильность в цене опциона", "Маржа", "Налог"], "correct_option": "Ожидаемая волатильность в цене опциона"},
        {"question": "Что такое arbitrage pricing theory?", "options": ["Спред", "Модель оценки стоимости актива без арбитража", "Дивиденд", "Налог"], "correct_option": "Модель оценки стоимости актива без арбитража"},
        {"question": "Что такое CDS?", "options": ["Дивиденд", "Кредитный дефолтный своп", "Лот", "Маржа"], "correct_option": "Кредитный дефолтный своп"},
        {"question": "Что такое contango?", "options": ["Спред", "Форма фьючерсной кривой с ростом цен вперёд", "Купон облигации", "Налог"], "correct_option": "Форма фьючерсной кривой с ростом цен вперёд"},
    ],
}

# ─── ГЛОССАРИЙ ────────────────────────────────────────────────────────────────
GLOSSARY = {
    "акция": "📌 *Акция* — ценная бумага, дающая право на долю в компании и участие в её прибыли (дивиденды).",
    "облигация": "📌 *Облигация* — долговая ценная бумага: вы даёте деньги в долг эмитенту под фиксированный процент.",
    "брокер": "📌 *Брокер* — посредник между трейдером и биржей. Обеспечивает доступ к рынкам и исполнение сделок.",
    "спред": "📌 *Спред* — разница между ценой покупки (Ask) и продажи (Bid). Это доход брокера с каждой сделки.",
    "стоп-лосс": "📌 *Стоп-лосс (SL)* — ордер, автоматически закрывающий сделку при достижении заданного убытка.",
    "тейк-профит": "📌 *Тейк-профит (TP)* — ордер, автоматически закрывающий сделку при достижении нужной прибыли.",
    "лот": "📌 *Лот* — стандартная единица объёма сделки. 1 стандартный лот = 100 000 единиц базовой валюты.",
    "маржа": "📌 *Маржа* — залог, блокируемый брокером для открытия сделки с кредитным плечом.",
    "плечо": "📌 *Кредитное плечо* — увеличение торгового объёма за счёт заёмных средств брокера (напр., 1:100).",
    "кредитное плечо": "📌 *Кредитное плечо* — увеличение торгового объёма за счёт заёмных средств брокера (напр., 1:100).",
    "своп": "📌 *Своп* — комиссия за перенос открытой позиции через ночь. Может быть положительным или отрицательным.",
    "волатильность": "📌 *Волатильность* — степень изменчивости цены актива за определённый период.",
    "фьючерс": "📌 *Фьючерс* — контракт на покупку/продажу актива в будущем по заранее оговорённой цене.",
    "опцион": "📌 *Опцион* — право (не обязательство) купить/продать актив по заранее оговорённой цене до истечения срока.",
    "ликвидность": "📌 *Ликвидность* — способность быстро купить/продать актив без существенного изменения его цены.",
    "диверсификация": "📌 *Диверсификация* — распределение капитала по разным активам для снижения общего риска.",
    "хеджирование": "📌 *Хеджирование* — страховка от убытков путём открытия противоположных позиций.",
    "скальпинг": "📌 *Скальпинг* — стратегия множества быстрых сделок внутри дня с небольшой прибылью на каждой.",
    "гэп": "📌 *Гэп* — разрыв на графике между ценой закрытия одного периода и открытия следующего.",
    "margin call": "📌 *Margin Call* — требование брокера пополнить счёт, когда убытки превышают допустимый порог.",
    "свеча": "📌 *Японская свеча* — элемент графика, показывающий цены открытия, закрытия, максимум и минимум за период.",
    "тренд": "📌 *Тренд* — направленное движение цены вверх (бычий), вниз (медвежий) или боком (флет).",
    "индикатор": "📌 *Индикатор* — математический инструмент для анализа цены (RSI, MACD, скользящие средние и др.).",
    "rsi": "📌 *RSI* — осциллятор от 0 до 100. >70 — перекупленность, <30 — перепроданность.",
    "macd": "📌 *MACD* — индикатор на основе скользящих средних. Показывает силу и направление тренда.",
    "флет": "📌 *Флет (боковик)* — период, когда цена движется в горизонтальном коридоре без чёткого тренда.",
    "алготрейдинг": "📌 *Алготрейдинг* — автоматическая торговля по заранее написанному алгоритму.",
    "депозит": "📌 *Депозит* — сумма средств на вашем торговом счёте, доступная для торговли.",
    "дивиденды": "📌 *Дивиденды* — часть прибыли компании, выплачиваемая акционерам.",
    "mt5": "📌 *MetaTrader 5 (MT5)* — профессиональная торговая платформа с широким набором инструментов.",
    "cds": "📌 *CDS (Credit Default Swap)* — кредитный дефолтный своп, инструмент страховки от дефолта эмитента.",
    "var": "📌 *VaR (Value at Risk)* — статистическая мера максимального убытка за период при заданной вероятности.",
}

# ─── УРОКИ ДНЯ ─────────────────────────────────────────────────────────────────
DAILY_LESSONS = [
    "💡 *Урок дня:* Никогда не рискуйте более 1–2% депозита в одной сделке. Это правило сохранило капитал тысячам трейдеров.",
    "💡 *Урок дня:* Тренд — ваш друг. Торгуйте по тренду, а не против него. «Не лови ножи» — базовый принцип выживания на рынке.",
    "💡 *Урок дня:* Стоп-лосс — это не слабость, а профессионализм. Лучший трейдер умеет управлять потерями.",
    "💡 *Урок дня:* Дневник трейдера — обязательный инструмент. Записывайте каждую сделку: вход, выход, причину, эмоции.",
    "💡 *Урок дня:* Демо-счёт — не пустая трата времени. Отработайте стратегию минимум месяц, прежде чем рисковать реальными деньгами.",
    "💡 *Урок дня:* Жадность убивает депозиты. Зафиксированная прибыль — это настоящая прибыль.",
    "💡 *Урок дня:* EUR/USD и USD/CHF движутся противоположно. Открывать обе в одну сторону — удваивать риск, а не диверсифицировать.",
    "💡 *Урок дня:* Новостные события (NFP, заседания ФРС) вызывают резкие движения. Без опыта торговли на новостях — лучше закройте позиции заранее.",
    "💡 *Урок дня:* Соотношение риск/прибыль должно быть минимум 1:2. На каждый доллар риска — минимум два в прибыли.",
    "💡 *Урок дня:* Психология — 80% успеха в трейдинге. Дисциплина и контроль эмоций важнее любой стратегии.",
    "💡 *Урок дня:* Поддержка и сопротивление — фундамент технического анализа. Цена всегда помнит ключевые уровни.",
    "💡 *Урок дня:* Не торгуйте на все деньги. Держите часть депозита свободной — для новых возможностей.",
    "💡 *Урок дня:* Таймфрейм определяет стиль. M1–M15 для скальпинга, H1–H4 для интрадея, D1+ для свинга.",
    "💡 *Урок дня:* MA50 и MA200 — ориентиры профессионалов по всему миру. Цена выше MA200 — бычий рынок.",
    "💡 *Урок дня:* Диверсификация снижает риск. Не вкладывайте всё в один актив — распределяйте по инструментам.",
    "💡 *Урок дня:* Открывайте сделку только при наличии чёткого торгового плана. Спонтанные решения — прямой путь к потере депозита.",
    "💡 *Урок дня:* Усреднение убыточной позиции чаще всего приводит к маржин-коллу. Признайте ошибку и закройте сделку. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Цена всегда стремится к зонам ликвидности. Стопы розничных трейдеров за локальными экстремумами выступают топливом для крупных игроков.",
    "💡 *Урок дня:* Рынок не знает о вашем существовании. Не пытайтесь ему отомстить после серии убытков — возьмите паузу. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Торгуя пробои уровней, дожидайтесь закрепления свечи за ним. Ложные пробои (свипы) собирают ликвидность и возвращают цену в диапазон.",
    "💡 *Урок дня:* Имбаланс (FVG) на старшем таймфрейме работает как магнит для цены. Рынок всегда стремится перекрыть неэффективное ценообразование. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Переторговка (overtrading) истощает и депозит, и нервы. 2-3 качественные сделки в неделю лучше, чем 20 импульсивных в день.",
    "💡 *Урок дня:* Дивергенция на осцилляторах (RSI, MACD) — отличный ранний сигнал затухания тренда, но не повод для немедленного входа против него. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Смена характера рынка (ChoCh) валидна только после съема ликвидности. В противном случае это просто коррекция внутри структуры.",
    "💡 *Урок дня:* Никогда не передвигайте стоп-лосс в сторону увеличения убытка. Установленный стоп — это броня вашего капитала. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Обращайте внимание на объемы вблизи уровней поддержки и сопротивления. Истинный пробой всегда сопровождается всплеском объема.",
    "💡 *Урок дня:* Индекс доллара (DXY) имеет обратную корреляцию с золотом и евро. Анализ DXY обязателен при торговле мажорами. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Синдром упущенной выгоды (FOMO) заставляет покупать на пиках и продавать на дне. Ушел поезд — ждите следующий сетап.",
    "💡 *Урок дня:* Уровни Фибоначчи лучше всего работают в связке с зонами П/С. Золотое сечение (0.618) — сильный магнит для завершения коррекций. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Ордерблок (OB) валиден только в том случае, если он привел к слому структуры (BOS) и оставил за собой зону имбаланса.",
    "💡 *Урок дня:* В пятницу вечером ликвидность падает, а спреды расширяются. Оставлять сделки на выходные — это всегда риск случайного гэпа. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 Урок дня: Скользящие средние показывают направление тренда, но запаздывают. Используйте их как динамические уровни, а не как первый сигнал на вход.",
    "💡 *Урок дня:* Сессионная ликвидность имеет решающее значение. Азиатский рендж часто выступает пулом ликвидности, который снимается на открытии Лондона. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Не слушайте инсайдеров из интернета. Единственная правда на рынке — это график цены и ваш строгий риск-менеджмент.",
    "💡 *Урок дня:* Пин-бар на графике — это еще не разворот. Подтверждением служит только следующая свеча, закрывшаяся в направлении длинной тени. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Межрыночный анализ помогает предвидеть движения. Рост доходности казначейских облигаций США обычно давит на золото и крипторынок.",
    "💡 *Урок дня:* Успех в трейдинге — это марафон, а не спринт. Сосредоточьтесь на выживании капитала в первый год, а не на сверхприбылях. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Торговля в узкой консолидации (флэте) съедает депозит стопами. Ждите импульсного выхода и торгуйте его ретест.",
    "💡 *Урок дня:* Индикатор профиля рынка (Volume Profile) показывает уровни с наибольшим проторгованным объемом (POC). Цена часто возвращается к ним. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Ваше рабочее место должно быть свободно от отвлекающих факторов. Трейдинг требует абсолютной концентрации и фокуса в моменте.",
    "💡 *Урок дня:* Гэпы на фондовом и валютном рынке в большинстве случаев перекрываются. Эту закономерность можно использовать для краткосрочных позиций. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Накопление по Вайкоффу требует финального подтверждения в виде Spring (ложного пробоя минимума). Только после него начинается фаза агрессивного роста.",
    "💡 *Урок дня:* Идеальных точек входа не существует. Ждать подтверждения на всех таймфреймах сразу — значит пропускать лучшие движения рынка. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Использование мультитаймфреймного анализа обязательно. Смотрите тренд на D1, ищите зону интереса на H1, входите в сделку на M15.",
    "💡 *Урок дня:* Корреляция криптовалют с индексами S&P 500 и Nasdaq часто подсказывает, куда пойдет биткоин. Риск-он настроения на фонде толкают крипту вверх. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Относитесь к трейдингу как к бизнесу, а не как к казино. Стабильность приходит только через системный подход и учет расходов (убытков).",
    "💡 *Урок дня:* Выход сильных макроэкономических данных (CPI, ФРС) часто вызывает «вертолеты» на графике. Безопаснее переждать волатильность вне рынка. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Премиум и Дискаунт зоны помогают оценить, насколько дорого или дешево стоит актив внутри текущего импульса.",
    "💡 *Урок дня:* Если вы не понимаете, что происходит на графике — закройте терминал. Нахождение «вне рынка» — это тоже профессиональная позиция. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Паттерны «Голова и плечи» или «Двойная вершина» работают только на вершине затяжного тренда, а не в случайном месте графика.",
    "💡 *Урок дня:* Защита лимитных ордеров крупным игроком оставляет на графике так называемые «спонсированные свечи». Они служат отличной опорой для входа. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Лосс — это плата за урок от рынка. Не занимайтесь самобичеванием. Проанализируйте ошибку и спокойно двигайтесь дальше.",
    "💡 *Урок дня:* Трейлинг-стоп — инструмент для того, чтобы дать прибыли течь. Подтягивайте стоп за локальные экстремумы по мере развития тренда. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Опционные уровни и открытый интерес (OI) дают понимание того, где маркетмейкеру выгодно экспирировать контракты (точка Max Pain).",
    "💡 *Урок дня:* Не копируйте чужие сделки вслепую. То, что подходит трейдеру с депозитом $100k, легко уничтожит ваш счет из-за разной допустимой просадки. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Входя в сделку, вы должны точно знать, где выйдете. Точка фиксации прибыли (Тейк-профит) определяется строго до открытия ордера.",
    "💡 *Урок дня:* Анализируйте кластерные графики (Footprint), чтобы увидеть рыночные ордера внутри свечи. Это покажет реальную агрессию покупателей или продавцов. Получить книгу по ссылке [https://lp.sbfconsult.com/edu](https://lp.sbfconsult.com/edu)",
    "💡 *Урок дня:* Здоровый сон и физическая активность напрямую влияют на ваш PnL. Уставший мозг принимает катастрофические финансовые решения.",
    "💡 *Урок дня:* Избегайте торговли кросс-курсами без понимания мажоров. Любой кросс — это всегда производная от двух основных пар с долларом. Получить консультацию по ссылке [https://t.me/SBF_Support](https://t.me/SBF_Support)",
    "💡 *Урок дня:* Изучайте механику сведения ордеров (matching engine). Понимание того, как рыночные заявки поглощают лимитные, изменит ваш взгляд на график навсегда."
]


# ──────────────────────────────────────────────────────────────────────────────
# УВЕДОМЛЕНИЕ О ЛИДЕ
# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
# ЛОГИРОВАНИЕ В ФАЙЛ ПО ПОЛЬЗОВАТЕЛЮ
# ──────────────────────────────────────────────────────────────────────────────
def log_user_file(user_id: int, username: str, full_name: str, event: str, details: str = ""):
    """Записывает событие в индивидуальный лог-файл пользователя."""
    safe_name = (full_name or "unknown").replace("/", "_").replace("\\", "_")[:40]
    filename = f"logs/users/{user_id}_{safe_name}.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{event}]"
    if details:
        line += f" {details}"
    line += "\n"
    try:
        with open(filename, "a", encoding="utf-8") as f:
            # Шапка файла при первом создании
            if f.tell() == 0 or not open(filename).read(10):
                pass
            f.write(line)
        # Если файл только что создан — дописываем шапку в начало
        with open(filename, "r", encoding="utf-8") as f:
            existing = f.read()
        if not existing.startswith("═"):
            header = (
                f"═══════════════════════════════════════════════════\n"
                f"  SBF Academy — Лог пользователя\n"
                f"  ID:       {user_id}\n"
                f"  Username: {username or '—'}\n"
                f"  Имя:      {full_name or '—'}\n"
                f"  Файл:     {filename}\n"
                f"═══════════════════════════════════════════════════\n\n"
            )
            with open(filename, "w", encoding="utf-8") as f:
                f.write(header + existing)
    except Exception as e:
        logger.warning(f"log_user_file error for {user_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# ИНТЕГРАЦИЯ ESPOCRM
# ──────────────────────────────────────────────────────────────────────────────
def send_lead_to_espocrm(user_id: int, full_name: str, username: str,
                          phone: str, extra_info: str = "") -> bool:
    """Отправляет лид в EspoCRM через LeadCapture API. Возвращает True при успехе."""
    # Разбиваем имя на части
    parts = (full_name or "").strip().split()
    first_name = parts[0] if parts else "—"
    last_name  = parts[1] if len(parts) > 1 else ""

    description_parts = [f"Telegram: {username or '—'}", f"User ID: {user_id}"]
    if extra_info:
        description_parts.append(extra_info)
    description = " | ".join(description_parts)

    payload = {
        "apiKey": ESPOCRM_API_KEY,
        "payload": {
            "firstName":   first_name,
            "lastName":    last_name,
            "phoneNumber": phone or "",
            "description": description,
            "source":      "Telegram Bot",
        }
    }

    try:
        resp = requests.post(
            ESPOCRM_URL,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        if resp.status_code in (200, 201):
            logger.info(f"EspoCRM lead created for user {user_id}: {resp.status_code}")
            return True
        else:
            logger.error(f"EspoCRM error {resp.status_code}: {resp.text[:300]}")
            return False
    except Exception as e:
        logger.error(f"EspoCRM request failed for user {user_id}: {e}")
        return False


async def notify_lead(context, user_id, full_name, username, phone, extra_info=""):
    """Отправляет уведомление о лиде в Telegram-группу и в EspoCRM."""
    ts  = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = (
        f"🔥 *НОВЫЙ ЛИД*\n\n"
        f"👤 Имя: {full_name}\n"
        f"🆔 Telegram: {username or '—'}\n"
        f"📱 Телефон: {phone or '—'}\n"
        f"🔗 Профиль: tg://user?id={user_id}\n"
    )
    if extra_info:
        msg += f"ℹ️ {extra_info}\n"
    msg += f"\n⏰ {ts}"

    # 1. Отправка в Telegram (группа лидов + менеджер)
    for chat_id in [LEADS_CHANNEL_ID, MANAGER_CHAT_ID]:
        if chat_id:
            try:
                await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
                logger.info(f"Lead notification sent to {chat_id}")
            except Exception as e:
                logger.error(f"Lead notify error ({chat_id}): {e}")

    # 2. Отправка в EspoCRM
    crm_ok = send_lead_to_espocrm(user_id, full_name, username, phone, extra_info)
    crm_status = "✅ EspoCRM OK" if crm_ok else "❌ EspoCRM FAIL"

    # 3. Лог в файл пользователя
    log_user_file(
        user_id, username, full_name,
        "LEAD_CAPTURED",
        f"phone={phone} | {extra_info} | {crm_status}"
    )
    logger.info(f"notify_lead complete: user={user_id} phone={phone} crm={crm_ok}")


# ──────────────────────────────────────────────────────────────────────────────
# ОНБОРДИНГ
# ──────────────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_in_db(user.id, f"@{user.username}" if user.username else None,
                      f"{user.first_name} {user.last_name or ''}".strip())
    log_action_in_db(user.id, "start")
    log_user_file(user.id, f"@{user.username}" if user.username else None,
                  f"{user.first_name} {user.last_name or ''}".strip(),
                  "START", f"first_name={user.first_name}")

    # Проверяем подписку на канал при каждом /start
    is_sub = await check_subscription(context.bot, user.id)
    update_user_in_db(user.id, is_subscribed=1 if is_sub else 0)

    if not is_sub:
        await update.message.reply_text(
            f"👋 Привет, *{user.first_name}*! Добро пожаловать в *SBF Academy*!\n\n"
            "Для использования бота необходимо подписаться на наш канал 📢\n\n"
            "Там мы публикуем торговые идеи, аналитику и новости рынков — это ваш первый шаг к прибыльной торговле.",
            parse_mode="Markdown",
            reply_markup=subscription_required_keyboard()
        )
        return ConversationHandler.END

    row = get_user(user.id)
    col_names = ["user_id","username","full_name","preferred_name","phone_number","first_seen","last_active",
                 "experience_level","deposit_range","already_trading","funnel_stage","broker_interest",
                 "section_interest","onboarding_done","followup_24h_sent","followup_3d_sent","is_subscribed"]
    user_dict = dict(zip(col_names, row)) if row else {}

    if user_dict.get("onboarding_done"):
        name = get_display_name(user.id, user.first_name)
        await update.message.reply_text(
            f"👋 С возвращением, *{name}*!\n\n{BRAND_TAGLINE}",
            reply_markup=main_menu_keyboard(), parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Привет, *{user.first_name}*! Добро пожаловать в *SBF Academy*!\n\n"
        "Мы обучаем трейдингу с нуля до стабильного результата 📈\n\n"
        "Ответьте на 3 быстрых вопроса — подберём лучший путь именно для вас.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Начать",       callback_data="onboard_start")],
            [InlineKeyboardButton("Пропустить →",   callback_data="onboard_skip")],
        ])
    )
    return ONBOARD_Q1

async def onboard_q1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "onboard_skip":
        update_user_in_db(query.from_user.id, onboarding_done=1)
        name = get_display_name(query.from_user.id, query.from_user.first_name)
        await query.message.reply_text(
            f"✅ Добро пожаловать, *{name}*!\n\n{BRAND_TAGLINE}",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    await query.message.reply_text(
        "1️⃣ *Вы уже торгуете на финансовых рынках?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, уже торгую",      callback_data="q1_yes")],
            [InlineKeyboardButton("📖 Нет, хочу научиться", callback_data="q1_no")],
            [InlineKeyboardButton("🤔 Пробовал, бросил",   callback_data="q1_tried")],
        ])
    )
    return ONBOARD_Q2

async def onboard_q2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["already_trading"] = query.data
    await query.message.reply_text(
        "2️⃣ *Как вы оцениваете свой уровень знаний?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🐣 Полный новичок",  callback_data="q2_beginner")],
            [InlineKeyboardButton("📚 Базовые знания",  callback_data="q2_basic")],
            [InlineKeyboardButton("🎯 Средний уровень", callback_data="q2_intermediate")],
            [InlineKeyboardButton("🏆 Профессионал",    callback_data="q2_pro")],
        ])
    )
    return ONBOARD_Q3

async def onboard_q3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["experience_level"] = query.data
    await query.message.reply_text(
        "3️⃣ *Какую сумму вы планируете для старта?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💵 До $500",        callback_data="q3_small")],
            [InlineKeyboardButton("💰 $500–$2000",     callback_data="q3_medium")],
            [InlineKeyboardButton("💎 $2000–$5000",    callback_data="q3_large")],
            [InlineKeyboardButton("🚀 Более $5000",    callback_data="q3_xlarge")],
            [InlineKeyboardButton("🤔 Ещё не решил",  callback_data="q3_undecided")],
        ])
    )
    return ONBOARD_DONE

async def onboard_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    context.user_data["deposit_range"] = query.data

    already = context.user_data.get("already_trading", "")
    exp     = context.user_data.get("experience_level", "")
    deposit = context.user_data.get("deposit_range", "")

    update_user_in_db(user.id, already_trading=already, experience_level=exp,
                      deposit_range=deposit, funnel_stage="interest", onboarding_done=1)

    if exp in ("q2_beginner", "q2_basic") or already == "q1_no":
        route_text = (
            "🎓 Отлично! Для вас — *путь новичка*:\n\n"
            "1. Изучите книги и видеоуроки в разделе «Образование»\n"
            "2. Пройдите тест на знания\n"
            "3. Откройте демо-счёт у брокера\n"
            "4. Свяжитесь с нами для старта обучения"
        )
    else:
        route_text = (
            "🏆 Видно, что вы уже в теме! Для вас:\n\n"
            "1. Ознакомьтесь с нашими брокерами-партнёрами\n"
            "2. Получите доступ к торговым сигналам\n"
            "3. Свяжитесь с менеджером для персональной стратегии"
        )

    name = get_display_name(user.id, user.first_name)
    await query.message.reply_text(
        f"✅ *{name}*, профиль сохранён!\n\n{route_text}\n\n{BRAND_TAGLINE}",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    log_action_in_db(user.id, "onboarding_done", f"exp={exp}, deposit={deposit}")
    log_user_file(user.id, f"@{user.username}" if user.username else None,
                  user.first_name, "ONBOARDING_DONE",
                  f"already_trading={already} | experience={exp} | deposit={deposit}")
    return ConversationHandler.END

async def onboard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Используй /menu для начала работы.")
    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────────────
# КОМАНДЫ
# ──────────────────────────────────────────────────────────────────────────────
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Проверка подписки
    is_sub = await check_subscription(context.bot, user.id)
    update_user_in_db(user.id, is_subscribed=1 if is_sub else 0)
    if not is_sub:
        await update.message.reply_text(
            "⛔ Для доступа к боту необходимо подписаться на канал *SBFEconomics*.",
            parse_mode="Markdown",
            reply_markup=subscription_required_keyboard()
        )
        return

    name = get_display_name(user.id, user.first_name)
    update_user_in_db(user.id, f"@{user.username}" if user.username else None,
                      f"{user.first_name} {user.last_name or ''}".strip())
    log_action_in_db(user.id, "menu")
    await update.message.reply_text(
        f"👋 *{name}*, выберите раздел:\n\n{BRAND_TAGLINE}",
        reply_markup=main_menu_keyboard(), parse_mode="Markdown"
    )

async def checksub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Диагностическая команда для проверки подписки — только для админов."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    target_id = user_id  # проверяем самого себя по умолчанию
    # Если передан аргумент — проверяем другого пользователя
    if context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            pass
    
    results = []
    chat_ids_to_try = [NEWS_CHANNEL_ID, "SBFEconomics"]
    
    for chat_id in chat_ids_to_try:
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=target_id)
            results.append(f"✅ `{chat_id}` → статус: *{member.status}*")
        except Exception as e:
            results.append(f"❌ `{chat_id}` → ошибка: `{e}`")
    
    # Также получим информацию о канале
    try:
        chat = await context.bot.get_chat(NEWS_CHANNEL_ID)
        chat_info = f"📢 Канал: *{chat.title}* (id: `{chat.id}`, тип: `{chat.type}`)"
    except Exception as e:
        chat_info = f"❌ Не удалось получить инфо о канале: `{e}`"
    
    # Проверим права бота в канале
    try:
        bot_member = await context.bot.get_chat_member(chat_id=NEWS_CHANNEL_ID, user_id=context.bot.id)
        bot_status = f"🤖 Статус бота в канале: *{bot_member.status}*"
    except Exception as e:
        bot_status = f"❌ Не удалось проверить права бота: `{e}`"
    
    msg = (
        f"🔍 *Диагностика подписки*\n\n"
        f"{chat_info}\n"
        f"{bot_status}\n\n"
        f"*Проверка user_id={target_id}:*\n" + "\n".join(results)
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM statistics WHERE action_type='start' AND date(timestamp)=?", (today,)); starts = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE phone_number IS NOT NULL"); phones = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed=1"); subs = c.fetchone()[0]
    c.execute("SELECT funnel_stage, COUNT(*) FROM users GROUP BY funnel_stage"); funnel = c.fetchall()
    conn.close()
    funnel_text = "\n".join(f"  {s or 'awareness'}: {n}" for s, n in funnel)
    await update.message.reply_text(
        f"📊 *Статистика*\n\n"
        f"👥 Всего: {total}\n🚀 Сегодня: {starts}\n📱 Лидов: {phones}\n"
        f"📢 Подписаны на канал: {subs}\n\n"
        f"🔽 *Воронка:*\n{funnel_text}\n\n🔗 http://localhost:5002/admin",
        parse_mode="Markdown"
    )
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка всем пользователям. Только для операторов/админов."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    # 🔍 ОПРЕДЕЛЯЕМ МЕДИА
    media_type = None
    file_id = None

    if update.message.photo:
        media_type = "photo"
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        media_type = "document"
        file_id = update.message.document.file_id
    elif update.message.video:
        media_type = "video"
        file_id = update.message.video.file_id
    elif update.message.audio:
        media_type = "audio"
        file_id = update.message.audio.file_id
    elif update.message.voice:
        media_type = "voice"
        file_id = update.message.voice.file_id
    elif update.message.animation:
        media_type = "animation"
        file_id = update.message.animation.file_id

    # Текст: из caption (для медиа) или из аргументов
    msg_text = ""
    if update.message.caption:
        caption = update.message.caption.strip()
        if caption.lower().startswith("/broadcast"):
            msg_text = caption[len("/broadcast"):].strip()
        else:
            msg_text = caption
    elif context.args:
        msg_text = " ".join(context.args)

    if not msg_text and not media_type:
        await update.message.reply_text(
            "📢 *Формат:*\n"
            "• Текст: `/broadcast Привет`\n"
            "• С медиа: прикрепите файл + текст в описании с командой",
            parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect("bot.db")
    user_ids = [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]
    conn.close()

    if not user_ids:
        await update.message.reply_text("⚠️ Нет пользователей.")
        return

    sent, failed = 0, 0
    status_msg = await update.message.reply_text(f"⏳ Отправка {len(user_ids)}...")

    for uid in user_ids:
        try:
            if media_type == "photo":
                await context.bot.send_photo(chat_id=uid, photo=file_id, caption=msg_text, parse_mode="Markdown")
            elif media_type == "document":
                await context.bot.send_document(chat_id=uid, document=file_id, caption=msg_text, parse_mode="Markdown")
            elif media_type == "video":
                await context.bot.send_video(chat_id=uid, video=file_id, caption=msg_text, parse_mode="Markdown")
            elif media_type == "audio":
                await context.bot.send_audio(chat_id=uid, audio=file_id, caption=msg_text, parse_mode="Markdown")
            elif media_type == "voice":
                await context.bot.send_voice(chat_id=uid, voice=file_id, caption=msg_text, parse_mode="Markdown")
            elif media_type == "animation":
                await context.bot.send_animation(chat_id=uid, animation=file_id, caption=msg_text, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=uid, text=msg_text, parse_mode="Markdown")
            sent += 1
            if sent % 30 == 0:
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Broadcast failed to {uid}: {e}")
            failed += 1

    await status_msg.edit_text(
        f"✅ *Завершено*\n📤 {sent} | ❌ {failed} | 👥 {len(user_ids)}",
        parse_mode="Markdown"
    )

# ──────────────────────────────────────────────────────────────────────────────
# ОБРАБОТКА СООБЩЕНИЙ
# ──────────────────────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # ── РЕЖИМ ОПЕРАТОРА: пересылка сообщения клиенту ──────────────────────────
    if user.id in OPERATOR_IDS:
        text = update.message.text or ""

        # Команда: /send 123456789 Ваш текст сообщения
        if text.startswith("/send "):
            parts = text.split(" ", 2)
            if len(parts) == 3:
                try:
                    client_id = int(parts[1])
                    msg_text  = parts[2]
                    await context.bot.send_message(
                        chat_id=client_id,
                        text=f"💬 *Сообщение от менеджера:*\n\n{msg_text}",
                        parse_mode="Markdown"
                    )
                    await update.message.reply_text(f"✅ Сообщение отправлено клиенту `{client_id}`")
                except ValueError:
                    await update.message.reply_text("❌ Формат: `/send 123456789 Текст сообщения`", parse_mode="Markdown")
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка: {e}")
            else:
                await update.message.reply_text("❌ Формат: `/send 123456789 Текст сообщения`", parse_mode="Markdown")
            return
    # ── конец режима оператора ─────────────────────────────────────────────────

    # ... дальше идёт существующий код handle_message
    if update.message.contact:
        ...

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.message.contact:
        phone = update.message.contact.phone_number
        context.user_data["phone_number"] = phone
        update_user_in_db(user.id, phone_number=phone, funnel_stage="intent")
        log_action_in_db(user.id, "share_phone", phone)
        name = get_display_name(user.id, user.first_name)
        log_user_file(user.id, f"@{user.username}" if user.username else None,
                      name, "SHARED_PHONE", f"phone={phone}")
        await update.message.reply_text(
            f"✅ *{name}*, спасибо! Ваш номер сохранён.\n"
            "Наш менеджер свяжется с вами в ближайшее время 🤝",
            reply_markup=REPLY_KEYBOARD, parse_mode="Markdown"
        )
        exp = context.user_data.get("experience_level", "—")
        deposit = context.user_data.get("deposit_range", "—")
        await notify_lead(context, user.id, name,
                          f"@{user.username}" if user.username else None,
                          phone, f"Опыт: {exp} | Депозит: {deposit}")
        return

    if update.message.text == "Меню":
        log_action_in_db(user.id, "menu_button")
        await menu_command(update, context)
        return

    # Режим глоссария
    if context.user_data.get("glossary_mode"):
        word = update.message.text.strip().lower()
        definition = GLOSSARY.get(word)
        if definition:
            await update.message.reply_text(
                definition + f"\n\n{BRAND_TAGLINE}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Найти другое слово", callback_data="glossary")],
                    [InlineKeyboardButton("« Главное меню",        callback_data="main_menu")],
                ])
            )
        else:
            suggestions = [k for k in GLOSSARY if word in k or k in word][:3]
            sugg_text = ", ".join(suggestions) if suggestions else "—"
            await update.message.reply_text(
                f"❌ Термин *«{update.message.text}»* не найден.\nВозможно: _{sugg_text}_\n\nПопробуйте другое слово:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Все термины",  callback_data="glossary_list")],
                    [InlineKeyboardButton("« Главное меню", callback_data="main_menu")],
                ])
            )
        return

    # Режим калькулятора
    calc_step = context.user_data.get("calc_step")
    if calc_step == "deposit":
        try:
            dep = float(update.message.text.replace(",", ".").replace("$", "").strip())
            context.user_data["calc_deposit"] = dep
            context.user_data["calc_step"] = "risk"
            await update.message.reply_text(f"✅ Депозит: *${dep:,.0f}*\n\n2️⃣ Введите *риск на сделку в %* (рекомендуется 1–2%):", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ Введите число, например: *1000*", parse_mode="Markdown")
        return

    if calc_step == "risk":
        try:
            risk = float(update.message.text.replace(",", ".").replace("%", "").strip())
            context.user_data["calc_risk"] = risk
            context.user_data["calc_step"] = "sl"
            await update.message.reply_text(f"✅ Риск: *{risk}%*\n\n3️⃣ Введите *стоп-лосс в пунктах* (например: 20):", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ Введите число, например: *2*", parse_mode="Markdown")
        return

    if calc_step == "sl":
        try:
            sl = float(update.message.text.replace(",", ".").strip())
            dep  = context.user_data.get("calc_deposit", 0)
            risk = context.user_data.get("calc_risk", 1)
            risk_amount = dep * risk / 100
            lot_size = round(risk_amount / (sl * 10), 2)
            context.user_data.pop("calc_step", None)
            log_action_in_db(user.id, "calc_used", f"dep={dep}, risk={risk}, sl={sl}, lot={lot_size}")
            log_user_file(user.id, f"@{user.username}" if user.username else None,
                          user.first_name, "CALC_USED",
                          f"deposit={dep} risk={risk}% sl={sl}pts lot={lot_size}")
            await update.message.reply_text(
                f"📊 *Результат расчёта:*\n\n"
                f"💰 Депозит: ${dep:,.0f}\n"
                f"⚠️ Риск: {risk}% = *${risk_amount:,.2f}*\n"
                f"🛑 Стоп-лосс: {sl} пунктов\n\n"
                f"📦 *Оптимальный размер лота: {lot_size}*\n\n"
                f"_{BRAND_TAGLINE}_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Рассчитать ещё", callback_data="risk_calc")],
                    [InlineKeyboardButton("💬 Консультация",   url=SUPPORT_LINK)],
                    [InlineKeyboardButton("« Главное меню",    callback_data="main_menu")],
                ])
            )
        except ValueError:
            await update.message.reply_text("⚠️ Введите число, например: *20*", parse_mode="Markdown")
        return

    log_action_in_db(user.id, "text_message", (update.message.text or "")[:100])
    await update.message.reply_text("Используй кнопку *Меню* или команду /menu 👇",
                                    reply_markup=REPLY_KEYBOARD, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────────────────
# ВОРОНКА PERFORMANCE (5 экранов)
# ──────────────────────────────────────────────────────────────────────────────
async def send_performance_pdf(bot, chat_id: int) -> bool:
    """Отправляет PDF-презентацию результатов торговли."""
    if not os.path.exists(PERFORMANCE_PDF):
        logger.warning(f"Performance PDF not found: {PERFORMANCE_PDF}")
        return False
    try:
        with open(PERFORMANCE_PDF, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                filename="SBF_Performance_2025-2026.pdf",
                caption=(
                    "📊 *SBF Consult — Результаты торговли 2025–2026*\n\n"
                    "✔️ Win Rate: *92.58%*\n"
                    "✔️ Суммарная прибыль: *$25 861*\n"
                    "✔️ Сделок закрыто: *1 289*\n"
                    "✔️ Два реальных счёта MT5\n\n"
                    "_Все данные верифицированы на реальных счетах._"
                ),
                parse_mode="Markdown"
            )
        return True
    except Exception as e:
        logger.error(f"PDF send error to {chat_id}: {e}")
        return False


async def show_performance_hook(query, user_id):
    """Экран 1 — Hook / Вступление."""
    log_action_in_db(user_id, "performance_view", "screen_1_hook")
    await query.message.reply_text(
        "📊 *Результаты торговли команды SBF*\n\n"
        "Мы показываем реальную статистику торговли на счетах MT5, чтобы вы могли увидеть:\n\n"
        "✔️ прибыльность стратегий\n"
        "✔️ процент прибыльных сделок\n"
        "✔️ торговые инструменты\n"
        "✔️ риск-менеджмент\n\n"
        "За последние месяцы:\n"
        "📈 *1 289 сделок*\n"
        "💰 *$25 861 суммарная прибыль*\n"
        "📊 *Win Rate до 92.58%*\n"
        "📉 *Просадка от 3.95%*\n\n"
        "👇 Получите полный PDF-отчёт или смотрите подробную статистику ниже:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Скачать PDF-отчёт",    callback_data="perf_pdf")],
            [InlineKeyboardButton("➡️ Смотреть статистику",  callback_data="perf_stats")],
            [InlineKeyboardButton("« Главное меню",           callback_data="main_menu")],
        ])
    )

async def show_performance_stats(query, user_id):
    """Экран 2 — Общая статистика."""
    log_action_in_db(user_id, "performance_view", "screen_2_stats")
    await query.message.reply_text(
        "📊 *Общая статистика торговли*\n\n"
        "┌─────────────────────────────\n"
        "│ 🏆 Win Rate:              *92.58%*\n"
        "│ 💰 Общая прибыль:    *$25 861*\n"
        "│ 📋 Количество сделок:  *1 289*\n"
        "│ 📉 Макс. просадка:      *3.95%*\n"
        "└─────────────────────────────\n\n"
        "📈 *Основная прибыль приходит из:*\n\n"
        "🥇 Gold (XAUUSD)\n"
        "🥈 Silver (XAGUSD)\n"
        "⛽️ Natural Gas\n\n"
        "_Это рынки с самой высокой волатильностью — именно здесь наши стратегии показывают лучший результат._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Разбор счетов →",   callback_data="perf_accounts")],
            [InlineKeyboardButton("« Назад",               callback_data="performance_hook")],
        ])
    )

async def show_performance_accounts(query, user_id):
    """Экран 3 — Разбор счетов."""
    log_action_in_db(user_id, "performance_view", "screen_3_accounts")
    await query.message.reply_text(
        "💼 *Пример торговых счетов*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 *Счёт №1*\n"
        "📈 Прибыль:              *$13 041*\n"
        "📊 Win Rate:               *85.7%*\n"
        "📉 Максимальная просадка: *3.95%*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 *Счёт №2*\n"
        "📈 Прибыль:              *$12 808*\n"
        "📊 Win Rate:               *92.58%*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ _Все сделки подтверждены на MetaTrader 5._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤝 Как использовать стратегию →", callback_data="perf_howto")],
            [InlineKeyboardButton("« Назад",                          callback_data="perf_stats")],
        ])
    )

async def show_performance_howto(query, user_id):
    """Экран 4 — Как клиенты используют стратегию."""
    log_action_in_db(user_id, "performance_view", "screen_4_howto")
    await query.message.reply_text(
        "🚀 *Как клиенты используют наши стратегии*\n\n"
        "Сейчас доступно несколько форматов работы:\n\n"
        "1️⃣ *Разбор рынка* — готовые точки входа от аналитика\n"
        "2️⃣ *Копирование сделок* — автоматическое следование за счётом\n"
        "3️⃣ *Доверительное управление* — передаёте счёт, мы торгуем\n"
        "4️⃣ *Обучение трейдингу* — учитесь торговать самостоятельно\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 Минимальный депозит для начала: *$1 000*\n"
        "━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Получить разбор депозита →", callback_data="perf_lead")],
            [InlineKeyboardButton("« Назад",                        callback_data="perf_accounts")],
        ])
    )

async def show_performance_lead(query, user, context):
    """Экран 5 — Захват лида."""
    log_action_in_db(user.id, "performance_view", "screen_5_lead")
    update_user_in_db(user.id, funnel_stage="intent", section_interest="performance")
    name = get_display_name(user.id, user.first_name)
    await query.message.reply_text(
        f"📊 *{name}*, хотите узнать, как можно использовать эту стратегию?\n\n"
        "Наш аналитик может:\n\n"
        "✔️ разобрать ваш депозит\n"
        "✔️ показать текущие точки входа\n"
        "✔️ предложить стратегию роста\n\n"
        "⏱ _Консультация занимает 15–20 минут и проходит онлайн._\n\n"
        "👇 Оставьте заявку — аналитик свяжется с вами в ближайшее время:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Записаться на консультацию", url=SUPPORT_LINK)],
            [InlineKeyboardButton("📩 Задать вопрос аналитику",   url=SUPPORT_LINK)],
            [InlineKeyboardButton("📄 Скачать PDF-отчёт",         callback_data="perf_pdf")],
            [InlineKeyboardButton("📱 Оставить номер телефона",   callback_data="leave_phone")],
            [InlineKeyboardButton("« Главное меню",               callback_data="main_menu")],
        ])
    )

async def prompt_leave_phone(query):
    """Просим поделиться номером прямо из воронки."""
    await query.message.reply_text(
        "📱 Нажмите кнопку ниже, чтобы поделиться номером.\n"
        "Аналитик перезвонит вам в удобное время:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📲 Поделиться номером", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )


# ──────────────────────────────────────────────────────────────────────────────
# КНОПКИ
# ──────────────────────────────────────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()
    log_action_in_db(user.id, "button", data)
    log_user_file(user.id, f"@{user.username}" if user.username else None,
                  f"{user.first_name} {user.last_name or ''}".strip(),
                  "BUTTON", data)
    update_user_in_db(user.id, f"@{user.username}" if user.username else None,
                      f"{user.first_name} {user.last_name or ''}".strip())

    # ── Проверка подписки (кнопка «Я подписался») ──────────────────────────
    if data == "check_sub":
        is_sub = await check_subscription(context.bot, user.id)
        if is_sub:
            update_user_in_db(user.id, is_subscribed=1)
            name = get_display_name(user.id, user.first_name)
            await query.message.reply_text(
                f"✅ Отлично, *{name}*! Подписка подтверждена.\n\n{BRAND_TAGLINE}",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        else:
            await query.message.reply_text(
                "❌ Подписка не найдена. Пожалуйста, подпишитесь на канал и попробуйте снова.",
                reply_markup=subscription_required_keyboard()
            )
        return

    # ── Для всех остальных кнопок — проверяем подписку ─────────────────────
    is_sub = await check_subscription(context.bot, user.id)
    if not is_sub:
        update_user_in_db(user.id, is_subscribed=0)
        await query.message.reply_text(
            "⛔ Для доступа к боту необходимо подписаться на канал *SBFEconomics*.",
            parse_mode="Markdown",
            reply_markup=subscription_required_keyboard()
        )
        return

    update_user_in_db(user.id, is_subscribed=1)
    name = get_display_name(user.id, user.first_name)

    # ── Performance воронка ─────────────────────────────────────────────────
    if data == "performance_hook":
        await show_performance_hook(query, user.id)

    elif data == "perf_pdf":
        log_action_in_db(user.id, "performance_view", "pdf_download")
        log_user_file(user.id, f"@{user.username}" if user.username else None,
                      f"{user.first_name} {user.last_name or ''}".strip(),
                      "PERF_PDF_REQUESTED", "")
        sent = await send_performance_pdf(query.message._bot, query.message.chat_id)
        if not sent:
            await query.message.reply_text(
                "⚠️ PDF-файл временно недоступен. Запросите статистику через менеджера:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Написать менеджеру", url=SUPPORT_LINK)],
                    [InlineKeyboardButton("➡️ Смотреть статистику", callback_data="perf_stats")],
                ])
            )
        else:
            await query.message.reply_text(
                "📊 Полная статистика по счетам:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Смотреть подробнее", callback_data="perf_stats")],
                    [InlineKeyboardButton("📞 Записаться на консультацию", url=SUPPORT_LINK)],
                ])
            )

    elif data == "perf_stats":
        await show_performance_stats(query, user.id)

    elif data == "perf_accounts":
        await show_performance_accounts(query, user.id)

    elif data == "perf_howto":
        await show_performance_howto(query, user.id)

    elif data == "perf_lead":
        await show_performance_lead(query, user, context)

    elif data == "leave_phone":
        await prompt_leave_phone(query)

    # ── Главное меню и общие разделы ────────────────────────────────────────
    elif data == "main_menu":
        await query.message.reply_text(f"👋 *{name}*, выберите раздел:\n\n{BRAND_TAGLINE}",
                                       reply_markup=main_menu_keyboard(), parse_mode="Markdown")

    elif data == "edu_materials":
        update_user_in_db(user.id, funnel_stage="interest", section_interest="education")
        await query.message.reply_text("📚 *Образовательные материалы*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 Книги",            callback_data="books")],
                [InlineKeyboardButton("🎬 Видеоуроки",       callback_data="videos")],
                [InlineKeyboardButton("🧠 Викторина",        callback_data="quiz_menu")],
                [InlineKeyboardButton("📖 Словарь трейдера", callback_data="glossary")],
                [InlineKeyboardButton("« Назад",             callback_data="main_menu")],
            ]))

    elif data == "books":
        await query.message.reply_text(
            "📖 *Рекомендуемые книги:*\n\n"
            "1. «Технический анализ финансовых рынков» — Мерфи\n"
            "2. «Торговля с уровнями ДиНаполи» — ДиНаполи\n"
            "3. «Японские свечи» — Нисон\n"
            "4. «Психология трейдинга» — Элдер\n\n"
            "📥 [Скачать книги](https://drive.google.com/drive/folders/1pFLg_6a1gMQVNAAso8XqRCohpWm3kwWa?usp=sharing)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Обучение с куратором", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад", callback_data="edu_materials")],
            ]))

    elif data == "videos":
        await query.message.reply_text(
            "🎬 *Рекомендуемые видеоуроки:*\n\n"
            "1. [AvaTrade YouTube](https://www.youtube.com/channel/UCiNPZypgxZkKu-U2C5qfCpg)\n"
            "2. [Биржевик](https://www.youtube.com/watch?v=TZYznFM9mF4)\n"
            "3. [ИнвестДруг](https://www.youtube.com/watch?v=19IDvcJhEn4)\n"
            "4. [Деньги не спят](https://www.youtube.com/watch?v=bPmmgKhvTEA)\n"
            "5. [United Traders](https://www.youtube.com/@theunitedtraders/videos)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Живой урок", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад", callback_data="edu_materials")],
            ]))

    elif data == "brokers":
        update_user_in_db(user.id, funnel_stage="consideration", section_interest="brokers")
        await query.message.reply_text(
            "🏦 *Наши брокеры-партнёры*\n\nВсе проверены командой SBF Academy:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("AvaTrade",           callback_data="broker_avatrade")],
                [InlineKeyboardButton("Daoti",              callback_data="broker_daoti")],
                [InlineKeyboardButton("FxPro",              callback_data="broker_fxpro")],
                [InlineKeyboardButton("Capex",              callback_data="broker_capex")],
                [InlineKeyboardButton("Instaforex",         callback_data="broker_instaforex")],
                [InlineKeyboardButton("Alpari",             callback_data="broker_alpari")],
                [InlineKeyboardButton("⚖️ Сравнить всех",  callback_data="brokers_compare")],
                [InlineKeyboardButton("« Назад",            callback_data="main_menu")],
            ]))

    elif data.startswith("broker_"):
        key = data.replace("broker_", "")
        b = BROKERS.get(key)
        if not b:
            await query.message.reply_text("Брокер не найден.")
            return
        update_user_in_db(user.id, funnel_stage="consideration", broker_interest=b["name"])
        log_action_in_db(user.id, "broker_view", b["name"])
        await query.message.reply_text(
            f"🏦 *{b['name']}*\n\n"
            f"⚡️ Плечо: {b['leverage']}\n"
            f"💻 Платформы: {b['platforms']}\n"
            f"📊 Спред: {b['spread']}\n"
            f"🎁 Бонус: {b['bonus']}\n"
            f"💳 Пополнение: {b['deposit_methods']}\n\n"
            f"_{b['description']}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🚀 Открыть счёт в {b['name']}", url=b["url"])],
                [InlineKeyboardButton("💬 Бесплатная консультация",     url=SUPPORT_LINK)],
                [InlineKeyboardButton("📢 Канал SBFEconomics",          url=NEWS_CHANNEL)],
                [InlineKeyboardButton("« К списку брокеров",            callback_data="brokers")],
            ]))

    elif data == "brokers_compare":
        rows = []
        for b in BROKERS.values():
            rows.append(f"*{b['name']}* — плечо {b['leverage']} | спред {b['spread']} | бонус {b['bonus']}")
        await query.message.reply_text(
            "⚖️ *Сравнение брокеров:*\n\n" + "\n".join(rows),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Помочь с выбором", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",             callback_data="brokers")],
            ]))

    elif data == "channels":
        update_user_in_db(user.id, funnel_stage="interest", section_interest="channels")
        await query.message.reply_text("📡 *Наши каналы:*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📰 SBFEconomics (новости)", url=NEWS_CHANNEL)],
                [InlineKeyboardButton("📈 Разбор рынка",       callback_data="signals")],
                [InlineKeyboardButton("« Назад",                   callback_data="main_menu")],
            ]))

    elif data == "signals":
        update_user_in_db(user.id, funnel_stage="intent")
        await query.message.reply_text(
            "📈 *Разбор рынка SBF Academy*\n\n"
            "Для доступа пополните счёт у брокера от *$1500* и передайте менеджеру:\n"
            "имя, телефон, email.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Написать менеджеру", url=SUPPORT_LINK)],
                [InlineKeyboardButton("🏦 Выбрать брокера",    callback_data="brokers")],
                [InlineKeyboardButton("« Назад",               callback_data="channels")],
            ]))

    elif data == "mt5":
        update_user_in_db(user.id, funnel_stage="consideration", section_interest="mt5")
        await query.message.reply_text("📈 *MetaTrader 5*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🖥 Открыть MT5",              callback_data="open_mt5")],
                [InlineKeyboardButton("📋 Инструкция по установке",  callback_data="install_mt5")],
                [InlineKeyboardButton("📡 Разбор рынка",         callback_data="mt5_signals")],
                [InlineKeyboardButton("« Назад",                     callback_data="main_menu")],
            ]))

    elif data == "open_mt5":
        await query.message.reply_text("Выберите брокера для открытия MT5:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("AvaTrade MT5", url="https://www.avatrade.com/trading-platforms/metatrader-5/")],
                [InlineKeyboardButton("Alpari MT5",   url="https://alpari.com/en/trading_platforms/metatrader5/")],
                [InlineKeyboardButton("FxPro MT5",    url="https://www.fxpro.com/trading-platforms/mt5")],
                [InlineKeyboardButton("Daoti MT5",    url="https://daoti.io/")],
                [InlineKeyboardButton("« Назад",      callback_data="mt5")],
            ]))

    elif data == "install_mt5":
        await query.message.reply_text(
            "📋 *Как начать работу в MT5:*\n\n"
            "1. Зарегистрируйтесь у брокера (раздел «Брокеры»)\n"
            "2. Скачайте MT5 с [официального сайта](https://www.metatrader5.com/en/download)\n"
            "3. Введите данные счёта для входа\n"
            "4. Настройте графики и индикаторы",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Помощь с настройкой", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",                callback_data="mt5")],
            ]))

    elif data == "mt5_signals":
        update_user_in_db(user.id, funnel_stage="intent")
        await query.message.reply_text(
            "📡 *Сигналы для MT5*\n\nПополните счёт от *$1500* и получите доступ.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Написать менеджеру", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",               callback_data="mt5")],
            ]))

    elif data == "risk_calc":
        context.user_data["calc_step"] = "deposit"
        context.user_data.pop("glossary_mode", None)
        log_action_in_db(user.id, "calc_start")
        await query.message.reply_text(
            "🔢 *Калькулятор размера позиции*\n\n"
            "Рассчитает правильный лот, чтобы не превысить допустимый риск.\n\n"
            "1️⃣ Введите ваш *депозит в $*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]]))

    elif data == "glossary":
        context.user_data["glossary_mode"] = True
        context.user_data.pop("calc_step", None)
        log_action_in_db(user.id, "glossary_open")
        await query.message.reply_text(
            "📖 *Словарь трейдера*\n\n"
            "Введите термин — получите определение.\n"
            "Например: _своп_, _маржа_, _RSI_, _скальпинг_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Все термины", callback_data="glossary_list")],
                [InlineKeyboardButton("« Назад",        callback_data="main_menu")],
            ]))

    elif data == "glossary_list":
        terms_text = " | ".join(f"`{t}`" for t in sorted(GLOSSARY.keys()))
        await query.message.reply_text(
            f"📋 *Доступные термины:*\n\n{terms_text}\n\nВведите любой из них:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="glossary")]]))

    elif data == "about":
        await query.message.reply_text(
            "🏢 *О компании SBF Academy*\n\n"
            "Команда профессиональных трейдеров и аналитиков, помогающих людям "
            "освоить финансовые рынки и зарабатывать системно.\n\n"
            "🎓 *Что мы предлагаем:*\n"
            "• Обучение с нуля до профессионального уровня\n"
            "• Разбор рынка от экспертов\n"
            "• Помощь в выборе и настройке брокера\n"
            "• Персональное сопровождение\n\n"
            f"🌐 [sbfconsult.com]({WEBSITE}) | 📢 [SBFEconomics]({NEWS_CHANNEL})",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Наш сайт",              url=WEBSITE)],
                [InlineKeyboardButton("💬 Написать менеджеру",    url=SUPPORT_LINK)],
                [InlineKeyboardButton("📢 Новостной канал",       url=NEWS_CHANNEL)],
                [InlineKeyboardButton("« Назад",                  callback_data="main_menu")],
            ]))

    elif data == "faq":
        await query.message.reply_text("❓ *Часто задаваемые вопросы:*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 Сколько стоит обучение?",         callback_data="faq_price")],
                [InlineKeyboardButton("🐣 Можно ли без опыта?",             callback_data="faq_noexp")],
                [InlineKeyboardButton("⏱ Когда начну зарабатывать?",       callback_data="faq_timing")],
                [InlineKeyboardButton("🔒 Безопасны ли ваши брокеры?",     callback_data="faq_safety")],
                [InlineKeyboardButton("💰 Минимальная сумма для старта?",   callback_data="faq_minsum")],
                [InlineKeyboardButton("📡 Что такое разбор рынка?",     callback_data="faq_signals")],
                [InlineKeyboardButton("« Назад",                            callback_data="main_menu")],
            ]))

    elif data == "faq_price":
        await query.message.reply_text(
            "💸 *Сколько стоит обучение?*\n\n"
            "Мы предлагаем форматы — от бесплатных материалов до персонального менторства.\n\n"
            "Точные условия зависят от пакета. Свяжитесь с менеджером для индивидуального предложения.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Узнать стоимость", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",             callback_data="faq")],
            ]))

    elif data == "faq_noexp":
        await query.message.reply_text(
            "🐣 *Можно ли без опыта?*\n\n"
            "Да! Большинство наших учеников начинали с нуля.\n\n"
            "Программа построена от базовых понятий до реальных сделок.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Начать обучение",  callback_data="edu_materials")],
                [InlineKeyboardButton("💬 Записаться",       url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",             callback_data="faq")],
            ]))

    elif data == "faq_timing":
        await query.message.reply_text(
            "⏱ *Когда начну зарабатывать?*\n\n"
            "Трейдинг — навык, а не лотерея.\n\n"
            "При системном подходе первые стабильные результаты — через *2–4 месяца*.\n\n"
            "Без знаний = потеря денег. С нами = структурированный путь.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Поговорить с менеджером", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",                    callback_data="faq")],
            ]))

    elif data == "faq_safety":
        await query.message.reply_text(
            "🔒 *Безопасны ли ваши брокеры?*\n\n"
            "Да. Работаем только с лицензированными:\n\n"
            "• *AvaTrade* — CySEC, ASIC, FSCA\n"
            "• *FxPro* — FCA, CySEC, FSCA\n"
            "• *Capex* — CySEC\n"
            "• *Alpari* — FSC Mauritius\n\n"
            "Все прошли проверку командой SBF Academy.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏦 Подробнее о брокерах", callback_data="brokers")],
                [InlineKeyboardButton("« Назад",                  callback_data="faq")],
            ]))

    elif data == "faq_minsum":
        await query.message.reply_text(
            "💰 *Минимальная сумма для старта:*\n\n"
            "• Daoti, AvaTrade, FxPro, Capex, Alpari — от $100\n"
            "• Instaforex — от $1\n\n"
            "Для доступа к сигналам SBF Academy — от *$1500*.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Калькулятор риска", callback_data="risk_calc")],
                [InlineKeyboardButton("🏦 Брокеры",           callback_data="brokers")],
                [InlineKeyboardButton("« Назад",               callback_data="faq")],
            ]))

    elif data == "faq_signals":
        await query.message.reply_text(
            "📡 *Что такое разбор рынка?*\n\n"
            "Готовая рекомендация от нашего аналитика:\n"
            "• Какой актив торговать\n"
            "• Точка входа\n"
            "• Стоп-лосс и тейк-профит\n\n"
            "Доступ — при пополнении счёта от *$1500*.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Получить доступ", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Назад",             callback_data="faq")],
            ]))

    elif data == "quiz_menu":
        context.user_data.pop("quiz_level", None)
        context.user_data.pop("quiz_index", None)
        context.user_data.pop("quiz_score", None)
        await query.message.reply_text("🧠 *Проверьте знания! Выберите уровень:*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Лёгкий",    callback_data="quiz_easy")],
                [InlineKeyboardButton("🟡 Средний",   callback_data="quiz_normal")],
                [InlineKeyboardButton("🔴 Сложный",   callback_data="quiz_hard")],
                [InlineKeyboardButton("💀 Экспертный", callback_data="quiz_titan")],
                [InlineKeyboardButton("« Назад",      callback_data="edu_materials")],
            ]))

    elif data == "restart_quiz":
        context.user_data["quiz_index"] = 0
        context.user_data["quiz_score"] = 0
        context.user_data.pop("correct_option_index", None)
        await ask_quiz_question(update, context)

    else:
        await query.message.reply_text("Используй меню:", reply_markup=main_menu_keyboard())


# ──────────────────────────────────────────────────────────────────────────────
# ВИКТОРИНА
# ──────────────────────────────────────────────────────────────────────────────
async def quiz_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.split("_")[1]
    context.user_data["quiz_level"] = level
    context.user_data["quiz_index"] = 0
    context.user_data["quiz_score"] = 0
    context.user_data.pop("correct_option_index", None)
    log_action_in_db(query.from_user.id, "quiz_start", level)
    log_user_file(query.from_user.id, f"@{query.from_user.username}" if query.from_user.username else None,
                  query.from_user.first_name, "QUIZ_START", f"level={level}")
    await ask_quiz_question(update, context)

async def ask_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    level = context.user_data.get("quiz_level")
    index = context.user_data.get("quiz_index", 0)
    questions = quiz_questions.get(level, [])

    if index >= len(questions):
        score = context.user_data.get("quiz_score", 0)
        total = len(questions)
        pct   = round(score / total * 100) if total else 0
        verdict = ("🏆 Отличный результат!" if pct >= 80
                   else "📚 Неплохо! Есть над чем поработать." if pct >= 50
                   else "📖 Рекомендуем изучить материалы академии.")
        await query.message.reply_text(
            f"✅ *Викторина завершена!*\n\nРезультат: *{score}/{total}* ({pct}%)\n\n{verdict}\n\n{BRAND_TAGLINE}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Пройти снова",     callback_data="restart_quiz")],
                [InlineKeyboardButton("📚 Образование",      callback_data="edu_materials")],
                [InlineKeyboardButton("💬 Записаться к нам", url=SUPPORT_LINK)],
                [InlineKeyboardButton("« Главное меню",      callback_data="main_menu")],
            ]))
        return

    q = questions[index]
    opts = q["options"].copy()
    random.seed(f"{level}_{index}")
    random.shuffle(opts)
    correct_idx = opts.index(q["correct_option"])
    context.user_data["correct_option_index"] = correct_idx

    await query.message.reply_text(
        f"❓ *Вопрос {index+1}/{len(questions)}*\n\n{q['question']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"answer_{i}")] for i, opt in enumerate(opts)])
    )

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    option_index = int(query.data.split("_")[1])
    correct_idx  = context.user_data.get("correct_option_index")
    level  = context.user_data.get("quiz_level")
    index  = context.user_data.get("quiz_index", 0)
    if correct_idx is None or not level:
        await query.message.reply_text("Ошибка сессии.", reply_markup=main_menu_keyboard())
        return
    q = quiz_questions[level][index]
    if option_index == correct_idx:
        context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
        resp = "✅ *Верно!*"
    else:
        resp = f"❌ *Неверно.* Правильный ответ: _{q['correct_option']}_"
    await query.message.reply_text(resp, parse_mode="Markdown")
    context.user_data["quiz_index"] = index + 1
    context.user_data.pop("correct_option_index", None)
    await ask_quiz_question(update, context)


# ──────────────────────────────────────────────────────────────────────────────
# FOLLOW-UP / УРОК ДНЯ
# ──────────────────────────────────────────────────────────────────────────────
async def send_daily_lesson(context):
    conn = sqlite3.connect("bot.db")
    ids = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE is_subscribed=1").fetchall()]
    conn.close()
    lesson = random.choice(DAILY_LESSONS)
    for uid in ids:
        try:
            await context.bot.send_message(uid,
                f"{lesson}\n\n📖 Словарь трейдера: /menu → Словарь\n_{BRAND_TAGLINE}_",
                parse_mode="Markdown")
        except: pass

async def send_followup_24h(context):
    threshold = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("bot.db")
    rows = conn.execute(
        "SELECT user_id, preferred_name, full_name FROM users WHERE first_seen<=? AND followup_24h_sent=0 AND is_subscribed=1",
        (threshold,)).fetchall()
    conn.close()
    for uid, pname, fname in rows:
        name = pname or (fname.split()[0] if fname else "трейдер")
        try:
            await context.bot.send_message(uid,
                f"👋 *{name}*, успели посмотреть брокеров?\n\n"
                "Открытие счёта — 5 минут. Менеджер поможет выбрать лучший вариант.\n\n"
                f"_{BRAND_TAGLINE}_", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏦 Смотреть брокеров", callback_data="brokers")],
                    [InlineKeyboardButton("💬 Задать вопрос",     url=SUPPORT_LINK)],
                ]))
            sqlite3.connect("bot.db").execute(
                "UPDATE users SET followup_24h_sent=1 WHERE user_id=?", (uid,)).connection.commit()
        except: pass

async def send_followup_3d(context):
    threshold = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("bot.db")
    rows = conn.execute(
        "SELECT user_id, preferred_name, full_name FROM users WHERE first_seen<=? AND followup_3d_sent=0 AND is_subscribed=1",
        (threshold,)).fetchall()
    conn.close()
    for uid, pname, fname in rows:
        name = pname or (fname.split()[0] if fname else "трейдер")
        try:
            await context.bot.send_message(uid,
                f"🎯 *{name}*, пройдите тест на знания — 2 минуты!\n\n"
                "По результатам подберём персональный план обучения.\n\n"
                f"_{BRAND_TAGLINE}_", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🧠 Пройти тест",      callback_data="quiz_menu")],
                    [InlineKeyboardButton("💬 Поговорить с нами", url=SUPPORT_LINK)],
                ]))
            sqlite3.connect("bot.db").execute(
                "UPDATE users SET followup_3d_sent=1 WHERE user_id=?", (uid,)).connection.commit()
        except: pass


# ──────────────────────────────────────────────────────────────────────────────
# FLASK ADMIN
# ──────────────────────────────────────────────────────────────────────────────
NAV = """<div class="nav"><a href="/admin/dashboard">📊 Дашборд</a>
<a href="/admin/users">👥 Пользователи</a><a href="/admin/broadcast">📢 Рассылка</a>
<a href="/admin/logout">Выйти</a></div>"""
STYLE = """<style>body{font-family:Arial;margin:20px;background:#f5f5f5;}
.nav{background:#1976D2;padding:12px 20px;border-radius:8px;margin-bottom:20px;}
.nav a{color:#fff;text-decoration:none;margin-right:20px;font-weight:bold;}
.card{background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,.1);
display:inline-block;min-width:160px;margin:0 15px 15px 0;text-align:center;}
.card h2{margin:0;font-size:36px;color:#1976D2;}.card p{color:#666;margin:5px 0 0;}
table{background:#fff;border-collapse:collapse;width:100%;border-radius:8px;overflow:hidden;
box-shadow:0 2px 5px rgba(0,0,0,.1);}
th{background:#1976D2;color:#fff;padding:10px;text-align:left;}
td{padding:10px;border-bottom:1px solid #eee;font-size:13px;}
textarea{width:500px;height:120px;padding:10px;border:1px solid #ddd;border-radius:4px;}
select,button{padding:10px 20px;margin:5px 0;border-radius:4px;}
button{background:#1976D2;color:#fff;border:none;cursor:pointer;font-size:15px;}
input[type=password]{width:100%;padding:10px;margin:10px 0;box-sizing:border-box;
border:1px solid #ddd;border-radius:4px;}</style>"""

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if "logged_in" in session: return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        error = "<p style='color:red'>Неверный пароль</p>"
    else:
        error = ""
    return f"""<html><head><title>SBF Admin</title>{STYLE}
    <style>.login{{max-width:320px;margin:100px auto;background:#fff;padding:30px;
    border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);}}</style></head>
    <body><div class="login"><h2>🎓 SBF Academy</h2>{error}
    <form method="POST"><input type="password" name="password" placeholder="Пароль администратора" required>
    <button type="submit" style="width:100%">Войти</button></form></div></body></html>"""

@app.route("/admin/dashboard")
def admin_dashboard():
    if "logged_in" not in session: return redirect(url_for("admin_login"))
    conn = sqlite3.connect("bot.db")
    total  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    today  = datetime.now().strftime("%Y-%m-%d")
    starts = conn.execute("SELECT COUNT(*) FROM statistics WHERE action_type='start' AND date(timestamp)=?", (today,)).fetchone()[0]
    phones = conn.execute("SELECT COUNT(*) FROM users WHERE phone_number IS NOT NULL").fetchone()[0]
    subs   = conn.execute("SELECT COUNT(*) FROM users WHERE is_subscribed=1").fetchone()[0]
    perf_views = conn.execute("SELECT COUNT(*) FROM actions WHERE action_type='performance_view'").fetchone()[0]
    perf_leads = conn.execute("SELECT COUNT(*) FROM actions WHERE action_type='performance_view' AND details='screen_5_lead'").fetchone()[0]
    funnel = conn.execute("SELECT funnel_stage, COUNT(*) FROM users GROUP BY funnel_stage").fetchall()
    top_br = conn.execute("SELECT broker_interest, COUNT(*) FROM users WHERE broker_interest IS NOT NULL GROUP BY broker_interest ORDER BY COUNT(*) DESC LIMIT 5").fetchall()
    conn.close()
    f_rows = "".join(f"<tr><td>{s or 'awareness'}</td><td>{n}</td></tr>" for s,n in funnel)
    b_rows = "".join(f"<tr><td>{b}</td><td>{n}</td></tr>" for b,n in top_br)
    return f"""<html><head><title>SBF Admin</title>{STYLE}</head><body>
    {NAV}<h2>📊 Дашборд</h2>
    <div class="card"><h2>{total}</h2><p>Пользователей</p></div>
    <div class="card"><h2>{starts}</h2><p>Запусков сегодня</p></div>
    <div class="card"><h2>{phones}</h2><p>Лидов с телефоном</p></div>
    <div class="card"><h2>{subs}</h2><p>Подписаны на канал</p></div>
    <div class="card"><h2>{perf_views}</h2><p>Просмотров Performance</p></div>
    <div class="card"><h2>{perf_leads}</h2><p>Заявок из Performance</p></div>
    <h3 style="margin-top:20px">🔽 Воронка продаж</h3>
    <table><tr><th>Этап</th><th>Пользователей</th></tr>{f_rows}</table>
    <h3 style="margin-top:20px">🏦 Интерес к брокерам</h3>
    <table><tr><th>Брокер</th><th>Просмотров</th></tr>{b_rows}</table>
    </body></html>"""

@app.route("/admin/users")
def admin_users():
    if "logged_in" not in session: return redirect(url_for("admin_login"))
    conn = sqlite3.connect("bot.db")
    users = conn.execute("""SELECT user_id, username, full_name, phone_number,
        funnel_stage, broker_interest, experience_level, is_subscribed, first_seen, last_active
        FROM users ORDER BY last_active DESC""").fetchall()
    conn.close()
    rows = "".join(
        f"<tr><td>{u[0]}</td><td>{u[1] or '—'}</td><td>{u[2] or '—'}</td>"
        f"<td>{u[3] or '—'}</td><td>{u[4] or '—'}</td><td>{u[5] or '—'}</td>"
        f"<td>{u[6] or '—'}</td><td>{'✅' if u[7] else '❌'}</td><td>{u[8]}</td><td>{u[9]}</td></tr>"
        for u in users)
    return f"""<html><head><title>Пользователи</title>{STYLE}</head><body>
    {NAV}<h2>👥 Пользователи ({len(users)})</h2>
    <table><tr><th>ID</th><th>Username</th><th>Имя</th><th>Телефон</th>
    <th>Воронка</th><th>Брокер</th><th>Опыт</th><th>Подписан</th><th>Первый вход</th><th>Активность</th></tr>
    {rows}</table></body></html>"""

@app.route("/admin/broadcast", methods=["GET", "POST"])
def admin_broadcast():
    if "logged_in" not in session: return redirect(url_for("admin_login"))
    if request.method == "POST":
        msg  = request.form.get("message", "")
        seg  = request.form.get("segment", "all")
        if msg:
            conn = sqlite3.connect("bot.db")
            if   seg == "with_phone":   ids = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE phone_number IS NOT NULL").fetchall()]
            elif seg == "no_phone":     ids = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE phone_number IS NULL").fetchall()]
            elif seg == "subscribed":   ids = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE is_subscribed=1").fetchall()]
            elif seg == "unsubscribed": ids = [r[0] for r in conn.execute("SELECT user_id FROM users WHERE is_subscribed=0").fetchall()]
            else:                       ids = [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]
            conn.close()
            sent = 0
            for uid in ids:
                try:
                    coro = app_telegram.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
                    asyncio.run_coroutine_threadsafe(coro, app_telegram.loop).result(timeout=5)
                    sent += 1
                except: pass
            return jsonify({"status": "success", "sent": sent, "total": len(ids)})
        return jsonify({"status": "error", "message": "Пустое сообщение"})
    return f"""<html><head><title>Рассылка</title>{STYLE}
    <script>function send(){{const m=document.getElementById('msg').value;
    const s=document.getElementById('seg').value;
    fetch('/admin/broadcast',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'message='+encodeURIComponent(m)+'&segment='+s}})
    .then(r=>r.json()).then(d=>alert('✅ Отправлено: '+d.sent+' из '+d.total+' пользователей'));}}</script>
    </head><body>{NAV}<h2>📢 Рассылка</h2><p>Поддерживается Markdown (*жирный*, _курсив_)</p>
    <select id="seg">
      <option value="all">Все пользователи</option>
      <option value="with_phone">Только лиды (с телефоном)</option>
      <option value="no_phone">Без телефона</option>
      <option value="subscribed">Подписаны на канал</option>
      <option value="unsubscribed">Не подписаны на канал</option>
    </select><br><br>
    <textarea id="msg" placeholder="Текст сообщения..."></textarea><br>
    <button onclick="send()">Отправить рассылку</button></body></html>"""

@app.route("/admin/logout")
def admin_logout():
    session.pop("logged_in", None)
    return redirect(url_for("admin_login"))


# ──────────────────────────────────────────────────────────────────────────────
# ЗАПУСК
# ──────────────────────────────────────────────────────────────────────────────
def run_flask():
    logger.info("🔧 Flask admin starting on port 5002...")
    app.run(host="0.0.0.0", port=5002, debug=False)

async def broadcast_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для /broadcast в подписи к медиафайлам."""
    caption = update.message.caption or ""
    if not caption.strip().lower().startswith("/broadcast"):
        return
    parts = caption.split(maxsplit=1)
    context.args = parts[1].split() if len(parts) > 1 else []
    await broadcast_command(update, context)

def main():
    global app_telegram
    init_db()

    app_telegram = Application.builder().token(BOT_TOKEN).build()

    onboard_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ONBOARD_Q1:   [CallbackQueryHandler(onboard_q1,     pattern="^onboard_")],
            ONBOARD_Q2:   [CallbackQueryHandler(onboard_q2,     pattern="^q1_")],
            ONBOARD_Q3:   [CallbackQueryHandler(onboard_q3,     pattern="^q2_")],
            ONBOARD_DONE: [CallbackQueryHandler(onboard_finish, pattern="^q3_")],
        },
        fallbacks=[CommandHandler("cancel", onboard_cancel)],
        allow_reentry=True,
    )

    app_telegram.add_handler(onboard_handler)
    app_telegram.add_handler(CommandHandler("menu",     menu_command))
    app_telegram.add_handler(CommandHandler("stats",    stats_command))
    app_telegram.add_handler(CommandHandler("checksub", checksub_command))
    app_telegram.add_handler(CallbackQueryHandler(answer_handler, pattern="^answer_"))
    app_telegram.add_handler(CallbackQueryHandler(quiz_button,    pattern="^quiz_(easy|normal|hard|titan)$"))
    app_telegram.add_handler(CommandHandler("broadcast", broadcast_command))
    app_telegram.add_handler(MessageHandler(
    filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.ANIMATION,
    broadcast_media_handler
    ))
    app_telegram.add_handler(CallbackQueryHandler(button))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND | filters.CONTACT, handle_message))

    jq = app_telegram.job_queue
    from datetime import time as dtime
    jq.run_daily(send_daily_lesson,  time=dtime(9, 0))
    jq.run_repeating(send_followup_24h, interval=3600, first=60)
    jq.run_repeating(send_followup_3d,  interval=3600, first=120)

    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("🚀 SBF Academy Bot v2.1 запущен")
    app_telegram.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()