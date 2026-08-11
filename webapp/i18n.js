"use strict";

// ── SBF Academy Mini App — client-side i18n ──────────────────────────────────
// Единый словарь для всей веб-части (app.js, patterns.html, google-callback.html).
// Русский — язык по умолчанию/фолбэк (нет 'en'), румынский — второй язык.
//
// Определение языка (в порядке приоритета):
//   1) localStorage['sbf_lang'] — ручной выбор через переключатель в Профиле,
//      побеждает всегда, если это 'ru' или 'ro' (в т.ч. вне Telegram, для тестов).
//   2) window.Telegram.WebApp.initDataUnsafe.user.language_code — синхронно
//      доступно сразу после инициализации telegram-web-app.js (без сетевых
//      запросов, в отличие от market_intel, где словарь довозится fetch'ем).
//      Код вида "ro-RO"/"ro" -> 'ro', иначе (в т.ч. отсутствие Telegram) -> 'ru'.
//
// Важно: этот файл должен грузиться (и window.sbfI18n должен существовать)
// ДО app.js — см. порядок <script> в index.html. defer-скрипты выполняются
// в порядке следования в документе, поэтому здесь ничего дополнительно
// ждать не нужно, если тег i18n.js стоит после telegram-web-app.js и до app.js.

var STRINGS = {
  ru: {
    // ── nav ──
    "nav.today": "Сегодня",
    "nav.grafik": "График",
    "nav.edu": "Обучение",
    "nav.tools": "Инструменты",
    "nav.profile": "Профиль",

    // ── auth / login ──
    "auth.password_placeholder": "Пароль",
    "auth.forgot_password": "Забыли пароль?",
    "auth.login_btn": "Войти",
    "auth.no_account": "Нет аккаунта?",
    "auth.register_link": "Зарегистрироваться",
    "auth.has_account": "Уже есть аккаунт?",
    "auth.otp_intro": "Пришлём одноразовый код на почту — пароль для входа не нужен.",
    "auth.otp_send_btn": "Отправить код",
    "auth.otp_resend_btn": "Отправить код ещё раз",
    "auth.otp_code_placeholder": "Код из письма",
    "auth.otp_login_btn": "Войти по коду",
    "auth.back_to_password": "← Назад к паролю",
    "auth.or": "или",
    "auth.telegram_hint": "Вход через Telegram — в самом приложении Telegram",
    "auth.otp_send_error": "Не удалось отправить код",
    "auth.otp_invalid_code": "Неверный код",
    "auth.telegram_login_error": "Не удалось войти через Telegram",
    "auth.google_login_error": "Не удалось войти через Google",
    "auth.login_error": "Не удалось выполнить вход",

    // ── common ──
    "common.save_btn": "Сохранить",
    "common.close_btn": "Закрыть",
    "common.load_error": "Ошибка загрузки",

    // ── today ──
    "today.title": "Обзор рынка",
    "today.history_title": "История обзоров",
    "today.no_history": "Пока нет истории",
    "today.archive_not_found": "Обзор не найден",

    // ── tools list (name/desc) ──
    "tool.journal.name": "Дневник трейдера",
    "tool.journal.desc": "Сделки, аналитика, зеркало поведения",
    "tool.cheatsheets.name": "Шпаргалки",
    "tool.cheatsheets.desc": "Индикаторы, паттерны, события — офлайн",
    "tool.checklist.name": "Чек-лист перед сделкой",
    "tool.checklist.desc": "Дисциплина входа: 4 вопроса",
    "tool.calendar.name": "Эконом-календарь",
    "tool.calendar.desc": "FOMC, CPI, NFP и другие ключевые события",
    "tool.patterns.name": "Риск-калькулятор",
    "tool.patterns.desc": "Позиция, ожидание системы, просадка",
    "tool.sessions.name": "Сессии рынка",
    "tool.sessions.desc": "Какие сессии открыты прямо сейчас",
    "tool.glossary.name": "Глоссарий",
    "tool.glossary.desc": "Термины трейдера от A до Я",

    // ── journal ──
    "journal.stat_trades": "Сделок",
    "journal.stat_winrate": "Винрейт",
    "journal.stat_expectancy": "Ожидание",
    "journal.no_trades": "Сделок пока нет",
    "journal.add_trade_btn": "+ Записать сделку",
    "journal.hide_form_btn": "— Скрыть форму",
    "journal.load_error": "Ошибка загрузки дневника",
    "journal.instrument_placeholder": "Инструмент (SPY, BTC…)",
    "journal.direction_placeholder": "Направление",
    "journal.setup_placeholder": "Сетап",
    "journal.emotion_placeholder": "Эмоция",
    "journal.entry_price_placeholder": "Цена входа",
    "journal.exit_price_placeholder": "Цена выхода",
    "journal.size_placeholder": "Размер",
    "journal.risk_placeholder": "Риск ($)",
    "journal.pnl_placeholder": "PnL (прибыль/убыток в $)",
    "journal.notes_placeholder": "Заметки (необязательно)",
    "journal.saving": "Сохраняем…",
    "journal.trade_saved": "✓ Сделка сохранена",
    "journal.error_prefix": "Ошибка: ",

    // ── cheatsheets ──
    "cheatsheets.cat_indicator": "Индикаторы",
    "cheatsheets.cat_chart_pattern": "Граф. паттерны",
    "cheatsheets.cat_candle_pattern": "Свечные",
    "cheatsheets.cat_event": "События рынка",
    "cheatsheets.cat_risk": "Риск",
    "cheatsheets.search_placeholder": "Поиск: RSI, молот, NFP…",
    "cheatsheets.all_btn": "× Все",
    "cheatsheets.no_results": "Ничего не найдено",
    "cheatsheets.learn_deeper": "📚 Учить глубже",
    "cheatsheets.chapter_word": "Глава",
    "cheatsheets.show_on_chart": "📈 Показать на графике",
    "cheatsheets.related_label": "Связанные:",

    // ── checklist ──
    "checklist.confirm_btn": "Подтвердить и продолжить",
    "checklist.not_all_checked": "⚠️ Не все пункты отмечены. Убедись, что готов.",
    "checklist.passed": "✓ Чек-лист пройден. Можно входить.",
    "checklist.save_error": "Ошибка сохранения.",

    // ── calendar ──
    "calendar.no_high_impact": "Сегодня нет высокоимпактных событий 🟢",
    "calendar.finnhub_note": "Данные появятся после подключения FINNHUB_API_KEY",
    "calendar.impact_high": "Высокий impact",
    "calendar.impact_medium": "Средний",
    "calendar.impact_all": "Все",
    "calendar.actual_label": "Факт: ",
    "calendar.forecast_label": "Прогноз: ",
    "calendar.previous_label": "Пред.: ",
    "calendar.more_link": "Подробнее →",
    "calendar.no_events": "Нет событий",

    // ── sessions ──
    "sessions.sydney": "Сидней",
    "sessions.tokyo": "Токио",
    "sessions.london": "Лондон",
    "sessions.newyork": "Нью-Йорк",
    "sessions.open_label": "Открыта",
    "sessions.closed_label": "Закрыта",
    "sessions.widget_title": "Сессии",
    "sessions.now_at": "сейчас",
    "sessions.disclaimer": "Форекс — 24/5. Биржи (NYSE, Nasdaq) — 09:30–16:00 ET (Нью-Йорк).",

    // ── glossary / etymology popup ──
    "glossary.etymology_label": "Этимология",

    // ── streak popup ──
    "streak.title_word": "Серия",
    "streak.description": "Столько дней подряд вы открываете обзор рынка. Пропустите день — счётчик обнулится и начнётся заново.",
    "streak.day_one": "день",
    "streak.day_few": "дня",
    "streak.day_many": "дней",

    // ── profile ──
    "profile.unlink_btn": "Отвязать",
    "profile.link_btn": "Привязать",
    "profile.login_methods_title": "Способы входа",
    "profile.review_time_label": "Время обзора",
    "profile.review_time_hint": "Во сколько пришлёт push-уведомление в Telegram. Бейдж «06:00» внутри самого отчёта — это время его генерации, к уведомлению отношения не имеет",
    "profile.timezone_label": "Часовой пояс",
    "profile.timezone_hint": "Время обзора выше считается по этому часовому поясу",
    "profile.accompaniment_label": "Сопровождение счёта",
    "profile.accompaniment_hint": "Сохраняет заинтересованность в персональном сопровождении счёта и открывает контакт менеджера ниже — чтобы вам ответили, напишите ему в Telegram напрямую",
    "profile.contact_manager_btn": "Написать менеджеру в Telegram",
    "profile.logout_btn": "Выйти",
    "profile.load_error": "Ошибка загрузки профиля",
    "profile.link_email_title": "Привязать email",
    "profile.link_password_placeholder": "Пароль (мин. 8 символов)",
    "profile.link_telegram_title": "Привязать Telegram",
    "profile.link_telegram_desc": "Открыв это приложение через Telegram, вы уже входите под своим Telegram-аккаунтом. Привязать отдельный Telegram-аккаунт можно на <a href=\"https://lp.sbfconsult.com/login.html\" target=\"_blank\">lp.sbfconsult.com</a>.",
    "profile.link_google_title": "Привязать Google",
    "profile.google_opening_browser": "Открываем Google в браузере телефона…",
    "profile.link_email_error": "Не удалось привязать email",
    "profile.link_google_error": "Не удалось привязать Google",
    "profile.google_start_error": "Не удалось начать вход через Google",
    "profile.google_browser_instructions": "Завершите вход в открывшемся браузере, затем вернитесь в Telegram — эта вкладка обновится сама.",
    "profile.unlink_confirm": "Отвязать этот способ входа?",
    "profile.unlink_error": "Не удалось отвязать",
    "profile.language_label": "Язык интерфейса",

    // ── patterns.html (риск-калькулятор, справочник) ──
    "patterns.page_title": "SBF — Риск-калькулятор",
    "patterns.eyebrow": "SBF Academy · справочник",
    "patterns.sub": "Считает риск на сделку, размер позиции, R-мультипликатор, ожидание системы и просадку. Образец, не сигналы. Свечные и графические паттерны — во вкладке «График».",
    "patterns.section_sub": "Считается вживую. Меняй любое поле.",
    "patterns.panel1_title": "Позиция и риск",
    "patterns.panel1_sub": "Размер сделки от принятого риска",
    "patterns.label_capital": "Капитал ($)",
    "patterns.label_risk_pct": "Риск на сделку (%)",
    "patterns.label_entry": "Вход",
    "patterns.label_stop": "Стоп-лосс",
    "patterns.label_target": "Тейк-профит (опционально)",
    "patterns.panel2_title": "Ожидание системы",
    "patterns.panel2_sub": "Средний результат на сделку, в R",
    "patterns.label_winrate": "Винрейт (%)",
    "patterns.label_avg_win": "Средний выигрыш (R)",
    "patterns.label_avg_loss": "Средний проигрыш (R)",
    "patterns.panel3_title": "Просадка",
    "patterns.panel3_sub": "Снижение капитала и возврат",
    "patterns.tab_current": "Текущая",
    "patterns.tab_streak": "Серия убытков",
    "patterns.label_peak": "Пик капитала",
    "patterns.label_current_cap": "Текущий",
    "patterns.label_dd_risk": "Риск/сделку (%)",
    "patterns.label_dd_n": "Убытков подряд",
    "patterns.footer": "Схемы и калькуляторы — образовательные: показывают, как читать фигуры и считать риск. Не являются торговой рекомендацией. SBF Company SRL.",
    "patterns.out_risk": "Риск на сделку",
    "patterns.out_position_size": "Размер позиции",
    "patterns.unit_suffix": " ед.",
    "patterns.out_position_value": "Стоимость позиции",
    "patterns.out_rr": "R-мультипликатор (R:R)",
    "patterns.out_potential_profit": "Потенц. прибыль",
    "patterns.out_expectancy": "Ожидание",
    "patterns.per_trade_suffix": " R / сделку",
    "patterns.out_per_100": "На 100 сделок",
    "patterns.r_suffix": " R",
    "patterns.verdict_positive": "Положительное ожидание: система в плюсе на дистанции при дисциплине.",
    "patterns.verdict_zero": "Нулевое ожидание: система в ноль до издержек.",
    "patterns.verdict_negative": "Отрицательное ожидание: на дистанции теряет. Пересмотри R или винрейт.",
    "patterns.out_dd_from_peak": "Просадка от пика",
    "patterns.out_need_recover": "Нужно для возврата",
    "patterns.out_capital_left": "Осталось капитала",
    "patterns.out_dd_size": "Размер просадки",

    // ── google-callback.html ──
    "callback.page_title": "SBF Academy — вход через Google",
    "callback.connecting": "Завершаем вход через Google…",
    "callback.google_cancelled": "Google отменил вход: ",
    "callback.missing_data": "Не удалось получить данные от Google. Попробуйте ещё раз из профиля в Telegram.",
    "callback.link_error": "Ошибка привязки",
    "callback.success": "Google привязан. Вернитесь в Telegram и откройте профиль заново — вкладка сама обновится.",
    "callback.generic_fail": "Не удалось завершить привязку. Попробуйте ещё раз из профиля в Telegram.",
  },

  ro: {
    // ── nav ──
    "nav.today": "Astăzi",
    "nav.grafik": "Grafic",
    "nav.edu": "Cursuri",
    "nav.tools": "Instrumente",
    "nav.profile": "Profil",

    // ── auth / login ──
    "auth.password_placeholder": "Parolă",
    "auth.forgot_password": "Ai uitat parola?",
    "auth.login_btn": "Autentificare",
    "auth.no_account": "Nu ai cont?",
    "auth.register_link": "Înregistrează-te",
    "auth.has_account": "Ai deja cont?",
    "auth.otp_intro": "Îți trimitem un cod unic pe email — nu ai nevoie de parolă.",
    "auth.otp_send_btn": "Trimite codul",
    "auth.otp_resend_btn": "Trimite codul din nou",
    "auth.otp_code_placeholder": "Codul din email",
    "auth.otp_login_btn": "Autentificare cu cod",
    "auth.back_to_password": "← Înapoi la parolă",
    "auth.or": "sau",
    "auth.telegram_hint": "Autentificare prin Telegram — direct în aplicația Telegram",
    "auth.otp_send_error": "Nu am putut trimite codul",
    "auth.otp_invalid_code": "Cod incorect",
    "auth.telegram_login_error": "Nu am reușit autentificarea prin Telegram",
    "auth.google_login_error": "Nu am reușit autentificarea prin Google",
    "auth.login_error": "Nu am reușit să te autentificăm",

    // ── common ──
    "common.save_btn": "Salvează",
    "common.close_btn": "Închide",
    "common.load_error": "Eroare la încărcare",

    // ── today ──
    "today.title": "Analiza pieței",
    "today.history_title": "Istoricul analizelor",
    "today.no_history": "Încă nu există istoric",
    "today.archive_not_found": "Analiza nu a fost găsită",

    // ── tools list (name/desc) ──
    "tool.journal.name": "Jurnalul traderului",
    "tool.journal.desc": "Tranzacții, analiză, oglinda comportamentului",
    "tool.cheatsheets.name": "Fișe rapide",
    "tool.cheatsheets.desc": "Indicatori, tipare, evenimente — offline",
    "tool.checklist.name": "Checklist înainte de tranzacție",
    "tool.checklist.desc": "Disciplina intrării: 4 întrebări",
    "tool.calendar.name": "Calendar economic",
    "tool.calendar.desc": "FOMC, CPI, NFP și alte evenimente-cheie",
    "tool.patterns.name": "Calculator de risc",
    "tool.patterns.desc": "Poziție, așteptarea sistemului, drawdown",
    "tool.sessions.name": "Sesiuni de piață",
    "tool.sessions.desc": "Ce sesiuni sunt deschise chiar acum",
    "tool.glossary.name": "Glosar",
    "tool.glossary.desc": "Termeni de trading de la A la Z",

    // ── journal ──
    "journal.stat_trades": "Tranzacții",
    "journal.stat_winrate": "Winrate",
    "journal.stat_expectancy": "Așteptare",
    "journal.no_trades": "Încă nu există tranzacții",
    "journal.add_trade_btn": "+ Adaugă tranzacție",
    "journal.hide_form_btn": "— Ascunde formularul",
    "journal.load_error": "Eroare la încărcarea jurnalului",
    "journal.instrument_placeholder": "Instrument (SPY, BTC…)",
    "journal.direction_placeholder": "Direcție",
    "journal.setup_placeholder": "Setup",
    "journal.emotion_placeholder": "Emoție",
    "journal.entry_price_placeholder": "Preț de intrare",
    "journal.exit_price_placeholder": "Preț de ieșire",
    "journal.size_placeholder": "Mărime",
    "journal.risk_placeholder": "Risc ($)",
    "journal.pnl_placeholder": "PnL (profit/pierdere în $)",
    "journal.notes_placeholder": "Notițe (opțional)",
    "journal.saving": "Se salvează…",
    "journal.trade_saved": "✓ Tranzacție salvată",
    "journal.error_prefix": "Eroare: ",

    // ── cheatsheets ──
    "cheatsheets.cat_indicator": "Indicatori",
    "cheatsheets.cat_chart_pattern": "Tipare grafice",
    "cheatsheets.cat_candle_pattern": "Tipare pe lumânări",
    "cheatsheets.cat_event": "Evenimente de piață",
    "cheatsheets.cat_risk": "Risc",
    "cheatsheets.search_placeholder": "Căutare: RSI, hammer, NFP…",
    "cheatsheets.all_btn": "× Toate",
    "cheatsheets.no_results": "Nu am găsit nimic",
    "cheatsheets.learn_deeper": "📚 Aprofundează",
    "cheatsheets.chapter_word": "Capitolul",
    "cheatsheets.show_on_chart": "📈 Arată pe grafic",
    "cheatsheets.related_label": "Similare:",

    // ── checklist ──
    "checklist.confirm_btn": "Confirmă și continuă",
    "checklist.not_all_checked": "⚠️ Nu toate punctele sunt bifate. Asigură-te că ești pregătit.",
    "checklist.passed": "✓ Checklist finalizat. Poți intra în piață.",
    "checklist.save_error": "Eroare la salvare.",

    // ── calendar ──
    "calendar.no_high_impact": "Astăzi nu sunt evenimente cu impact ridicat 🟢",
    "calendar.finnhub_note": "Datele vor apărea după conectarea FINNHUB_API_KEY",
    "calendar.impact_high": "Impact ridicat",
    "calendar.impact_medium": "Mediu",
    "calendar.impact_all": "Toate",
    "calendar.actual_label": "Real: ",
    "calendar.forecast_label": "Prognoză: ",
    "calendar.previous_label": "Anterior: ",
    "calendar.more_link": "Detalii →",
    "calendar.no_events": "Niciun eveniment",

    // ── sessions ──
    "sessions.sydney": "Sydney",
    "sessions.tokyo": "Tokyo",
    "sessions.london": "Londra",
    "sessions.newyork": "New York",
    "sessions.open_label": "Deschisă",
    "sessions.closed_label": "Închisă",
    "sessions.widget_title": "Sesiuni",
    "sessions.now_at": "acum",
    "sessions.disclaimer": "Forex — 24/5. Bursele (NYSE, Nasdaq) — 09:30–16:00 ET (New York).",

    // ── glossary / etymology popup ──
    "glossary.etymology_label": "Etimologie",

    // ── streak popup ──
    "streak.title_word": "Serie",
    "streak.description": "Atâtea zile la rând ai deschis analiza pieței. Sari o zi — contorul se resetează și reîncepe.",
    "streak.day_one": "zi",
    "streak.day_few": "zile",
    "streak.day_many": "zile",

    // ── profile ──
    "profile.unlink_btn": "Deconectează",
    "profile.link_btn": "Conectează",
    "profile.login_methods_title": "Metode de autentificare",
    "profile.review_time_label": "Ora analizei",
    "profile.review_time_hint": "La ce oră vine notificarea push în Telegram. Eticheta „06:00” din interiorul raportului este ora generării lui și nu are legătură cu notificarea",
    "profile.timezone_label": "Fus orar",
    "profile.timezone_hint": "Ora analizei de mai sus este calculată după acest fus orar",
    "profile.accompaniment_label": "Asistență cont",
    "profile.accompaniment_hint": "Salvează interesul pentru asistență personalizată a contului și afișează contactul managerului mai jos — pentru un răspuns, scrie-i direct pe Telegram",
    "profile.contact_manager_btn": "Scrie managerului pe Telegram",
    "profile.logout_btn": "Ieșire",
    "profile.load_error": "Eroare la încărcarea profilului",
    "profile.link_email_title": "Conectează email",
    "profile.link_password_placeholder": "Parolă (min. 8 caractere)",
    "profile.link_telegram_title": "Conectează Telegram",
    "profile.link_telegram_desc": "Ai deschis această aplicație prin Telegram, deci ești deja autentificat cu contul tău Telegram. Poți conecta un cont Telegram separat pe <a href=\"https://lp.sbfconsult.com/login.html\" target=\"_blank\">lp.sbfconsult.com</a>.",
    "profile.link_google_title": "Conectează Google",
    "profile.google_opening_browser": "Deschidem Google în browserul telefonului…",
    "profile.link_email_error": "Nu am putut conecta emailul",
    "profile.link_google_error": "Nu am putut conecta Google",
    "profile.google_start_error": "Nu am putut începe autentificarea prin Google",
    "profile.google_browser_instructions": "Finalizează autentificarea în browserul deschis, apoi revino în Telegram — această filă se va actualiza singură.",
    "profile.unlink_confirm": "Deconectezi această metodă de autentificare?",
    "profile.unlink_error": "Nu am putut deconecta",
    "profile.language_label": "Limba interfeței",

    // ── patterns.html (risk-calculator, ghid) ──
    "patterns.page_title": "SBF — Calculator de risc",
    "patterns.eyebrow": "SBF Academy · ghid",
    "patterns.sub": "Calculează riscul pe tranzacție, mărimea poziției, R-multiplul, așteptarea sistemului și drawdown-ul. Exemplu educațional, nu semnale. Tiparele pe lumânări și grafice — în tab-ul „Grafic”.",
    "patterns.section_sub": "Se calculează live. Modifică orice câmp.",
    "patterns.panel1_title": "Poziție și risc",
    "patterns.panel1_sub": "Mărimea tranzacției pornind de la riscul asumat",
    "patterns.label_capital": "Capital ($)",
    "patterns.label_risk_pct": "Risc pe tranzacție (%)",
    "patterns.label_entry": "Intrare",
    "patterns.label_stop": "Stop-Loss",
    "patterns.label_target": "Take-Profit (opțional)",
    "patterns.panel2_title": "Așteptarea sistemului",
    "patterns.panel2_sub": "Rezultatul mediu pe tranzacție, în R",
    "patterns.label_winrate": "Winrate (%)",
    "patterns.label_avg_win": "Câștig mediu (R)",
    "patterns.label_avg_loss": "Pierdere medie (R)",
    "patterns.panel3_title": "Drawdown",
    "patterns.panel3_sub": "Reducerea capitalului și revenirea",
    "patterns.tab_current": "Curentă",
    "patterns.tab_streak": "Serie de pierderi",
    "patterns.label_peak": "Vârful capitalului",
    "patterns.label_current_cap": "Curent",
    "patterns.label_dd_risk": "Risc/tranzacție (%)",
    "patterns.label_dd_n": "Pierderi la rând",
    "patterns.footer": "Schemele și calculatoarele sunt educaționale: arată cum se citesc tiparele și cum se calculează riscul. Nu reprezintă o recomandare de tranzacționare. SBF Company SRL.",
    "patterns.out_risk": "Risc pe tranzacție",
    "patterns.out_position_size": "Mărimea poziției",
    "patterns.unit_suffix": " unități",
    "patterns.out_position_value": "Valoarea poziției",
    "patterns.out_rr": "R-multiplu (R:R)",
    "patterns.out_potential_profit": "Profit potențial",
    "patterns.out_expectancy": "Așteptare",
    "patterns.per_trade_suffix": " R / tranzacție",
    "patterns.out_per_100": "La 100 de tranzacții",
    "patterns.r_suffix": " R",
    "patterns.verdict_positive": "Așteptare pozitivă: sistemul este pe plus pe termen lung, cu disciplină.",
    "patterns.verdict_zero": "Așteptare zero: sistemul e pe zero, înainte de costuri.",
    "patterns.verdict_negative": "Așteptare negativă: pe termen lung sistemul pierde. Revizuiește R sau winrate-ul.",
    "patterns.out_dd_from_peak": "Drawdown de la vârf",
    "patterns.out_need_recover": "Necesar pentru revenire",
    "patterns.out_capital_left": "Capital rămas",
    "patterns.out_dd_size": "Mărimea drawdown-ului",

    // ── google-callback.html ──
    "callback.page_title": "SBF Academy — autentificare prin Google",
    "callback.connecting": "Finalizăm autentificarea prin Google…",
    "callback.google_cancelled": "Google a anulat autentificarea: ",
    "callback.missing_data": "Nu am putut obține datele de la Google. Încearcă din nou din profilul din Telegram.",
    "callback.link_error": "Eroare la conectare",
    "callback.success": "Google conectat. Revino în Telegram și deschide din nou profilul — fila se va actualiza singură.",
    "callback.generic_fail": "Nu am reușit să finalizăm conectarea. Încearcă din nou din profilul din Telegram.",
  },

  en: {
    // ── nav ──
    "nav.today": "Today",
    "nav.grafik": "Chart",
    "nav.edu": "Learn",
    "nav.tools": "Tools",
    "nav.profile": "Profile",

    // ── auth / login ──
    "auth.password_placeholder": "Password",
    "auth.forgot_password": "Forgot password?",
    "auth.login_btn": "Log in",
    "auth.no_account": "No account?",
    "auth.register_link": "Sign up",
    "auth.has_account": "Already have an account?",
    "auth.otp_intro": "We'll send a one-time code to your email — no password needed.",
    "auth.otp_send_btn": "Send code",
    "auth.otp_resend_btn": "Resend code",
    "auth.otp_code_placeholder": "Code from the email",
    "auth.otp_login_btn": "Log in with code",
    "auth.back_to_password": "← Back to password",
    "auth.or": "or",
    "auth.telegram_hint": "Telegram login — available right inside the Telegram app",
    "auth.otp_send_error": "Couldn't send the code",
    "auth.otp_invalid_code": "Invalid code",
    "auth.telegram_login_error": "Couldn't log in via Telegram",
    "auth.google_login_error": "Couldn't log in via Google",
    "auth.login_error": "Couldn't log in",

    // ── common ──
    "common.save_btn": "Save",
    "common.close_btn": "Close",
    "common.load_error": "Failed to load",

    // ── today ──
    "today.title": "Market overview",
    "today.history_title": "Overview history",
    "today.no_history": "No history yet",
    "today.archive_not_found": "Overview not found",

    // ── tools list (name/desc) ──
    "tool.journal.name": "Trading journal",
    "tool.journal.desc": "Trades, analytics, a mirror of your behavior",
    "tool.cheatsheets.name": "Cheat sheets",
    "tool.cheatsheets.desc": "Indicators, patterns, events — offline",
    "tool.checklist.name": "Pre-trade checklist",
    "tool.checklist.desc": "Entry discipline: 4 questions",
    "tool.calendar.name": "Economic calendar",
    "tool.calendar.desc": "FOMC, CPI, NFP and other key events",
    "tool.patterns.name": "Risk calculator",
    "tool.patterns.desc": "Position size, system expectancy, drawdown",
    "tool.sessions.name": "Market sessions",
    "tool.sessions.desc": "Which sessions are open right now",
    "tool.glossary.name": "Glossary",
    "tool.glossary.desc": "Trading terms from A to Z",

    // ── journal ──
    "journal.stat_trades": "Trades",
    "journal.stat_winrate": "Win rate",
    "journal.stat_expectancy": "Expectancy",
    "journal.no_trades": "No trades yet",
    "journal.add_trade_btn": "+ Log a trade",
    "journal.hide_form_btn": "— Hide form",
    "journal.load_error": "Failed to load the journal",
    "journal.instrument_placeholder": "Instrument (SPY, BTC…)",
    "journal.direction_placeholder": "Direction",
    "journal.setup_placeholder": "Setup",
    "journal.emotion_placeholder": "Emotion",
    "journal.entry_price_placeholder": "Entry price",
    "journal.exit_price_placeholder": "Exit price",
    "journal.size_placeholder": "Size",
    "journal.risk_placeholder": "Risk ($)",
    "journal.pnl_placeholder": "PnL (profit/loss in $)",
    "journal.notes_placeholder": "Notes (optional)",
    "journal.saving": "Saving…",
    "journal.trade_saved": "✓ Trade saved",
    "journal.error_prefix": "Error: ",

    // ── cheatsheets ──
    "cheatsheets.cat_indicator": "Indicators",
    "cheatsheets.cat_chart_pattern": "Chart patterns",
    "cheatsheets.cat_candle_pattern": "Candlestick",
    "cheatsheets.cat_event": "Market events",
    "cheatsheets.cat_risk": "Risk",
    "cheatsheets.search_placeholder": "Search: RSI, hammer, NFP…",
    "cheatsheets.all_btn": "× All",
    "cheatsheets.no_results": "Nothing found",
    "cheatsheets.learn_deeper": "📚 Learn more",
    "cheatsheets.chapter_word": "Chapter",
    "cheatsheets.show_on_chart": "📈 Show on chart",
    "cheatsheets.related_label": "Related:",

    // ── checklist ──
    "checklist.confirm_btn": "Confirm and continue",
    "checklist.not_all_checked": "⚠️ Not all items are checked. Make sure you're ready.",
    "checklist.passed": "✓ Checklist passed. You're clear to enter.",
    "checklist.save_error": "Failed to save.",

    // ── calendar ──
    "calendar.no_high_impact": "No high-impact events today 🟢",
    "calendar.finnhub_note": "Data will appear once FINNHUB_API_KEY is connected",
    "calendar.impact_high": "High impact",
    "calendar.impact_medium": "Medium",
    "calendar.impact_all": "All",
    "calendar.actual_label": "Actual: ",
    "calendar.forecast_label": "Forecast: ",
    "calendar.previous_label": "Previous: ",
    "calendar.more_link": "More →",
    "calendar.no_events": "No events",

    // ── sessions ──
    "sessions.sydney": "Sydney",
    "sessions.tokyo": "Tokyo",
    "sessions.london": "London",
    "sessions.newyork": "New York",
    "sessions.open_label": "Open",
    "sessions.closed_label": "Closed",
    "sessions.widget_title": "Sessions",
    "sessions.now_at": "now",
    "sessions.disclaimer": "Forex — 24/5. Exchanges (NYSE, Nasdaq) — 09:30–16:00 ET (New York).",

    // ── glossary / etymology popup ──
    "glossary.etymology_label": "Etymology",

    // ── streak popup ──
    "streak.title_word": "Streak",
    "streak.description": "This is how many days in a row you've opened the market overview. Miss a day and the counter resets from zero.",
    "streak.day_one": "day",
    "streak.day_few": "days",
    "streak.day_many": "days",

    // ── profile ──
    "profile.unlink_btn": "Unlink",
    "profile.link_btn": "Link",
    "profile.login_methods_title": "Login methods",
    "profile.review_time_label": "Overview time",
    "profile.review_time_hint": "What time the push notification arrives in Telegram. The “06:00” badge inside the report itself is its generation time and is unrelated to the notification",
    "profile.timezone_label": "Time zone",
    "profile.timezone_hint": "The overview time above is calculated using this time zone",
    "profile.accompaniment_label": "Account support",
    "profile.accompaniment_hint": "Registers your interest in personal account support and reveals the manager's contact below — to get a reply, message them directly on Telegram",
    "profile.contact_manager_btn": "Message the manager on Telegram",
    "profile.logout_btn": "Log out",
    "profile.load_error": "Failed to load profile",
    "profile.link_email_title": "Link email",
    "profile.link_password_placeholder": "Password (min. 8 characters)",
    "profile.link_telegram_title": "Link Telegram",
    "profile.link_telegram_desc": "By opening this app through Telegram, you're already logged in with your Telegram account. You can link a separate Telegram account at <a href=\"https://lp.sbfconsult.com/login.html\" target=\"_blank\">lp.sbfconsult.com</a>.",
    "profile.link_google_title": "Link Google",
    "profile.google_opening_browser": "Opening Google in your phone's browser…",
    "profile.link_email_error": "Couldn't link email",
    "profile.link_google_error": "Couldn't link Google",
    "profile.google_start_error": "Couldn't start Google login",
    "profile.google_browser_instructions": "Finish logging in in the browser that opened, then return to Telegram — this tab will refresh itself.",
    "profile.unlink_confirm": "Unlink this login method?",
    "profile.unlink_error": "Couldn't unlink",
    "profile.language_label": "Interface language",

    // ── patterns.html (risk-calculator, reference guide) ──
    "patterns.page_title": "SBF — Risk Calculator",
    "patterns.eyebrow": "SBF Academy · reference guide",
    "patterns.sub": "Calculates risk per trade, position size, R-multiple, system expectancy, and drawdown. An educational sample, not signals. Candlestick and chart patterns are in the “Chart” tab.",
    "patterns.section_sub": "Calculated live. Change any field.",
    "patterns.panel1_title": "Position & risk",
    "patterns.panel1_sub": "Trade size from accepted risk",
    "patterns.label_capital": "Capital ($)",
    "patterns.label_risk_pct": "Risk per trade (%)",
    "patterns.label_entry": "Entry",
    "patterns.label_stop": "Stop-loss",
    "patterns.label_target": "Take-profit (optional)",
    "patterns.panel2_title": "System expectancy",
    "patterns.panel2_sub": "Average result per trade, in R",
    "patterns.label_winrate": "Win rate (%)",
    "patterns.label_avg_win": "Average win (R)",
    "patterns.label_avg_loss": "Average loss (R)",
    "patterns.panel3_title": "Drawdown",
    "patterns.panel3_sub": "Capital decline and recovery",
    "patterns.tab_current": "Current",
    "patterns.tab_streak": "Losing streak",
    "patterns.label_peak": "Capital peak",
    "patterns.label_current_cap": "Current",
    "patterns.label_dd_risk": "Risk/trade (%)",
    "patterns.label_dd_n": "Losses in a row",
    "patterns.footer": "The diagrams and calculators are educational: they show how to read patterns and calculate risk. Not trading advice. SBF Company SRL.",
    "patterns.out_risk": "Risk per trade",
    "patterns.out_position_size": "Position size",
    "patterns.unit_suffix": " units",
    "patterns.out_position_value": "Position value",
    "patterns.out_rr": "R-multiple (R:R)",
    "patterns.out_potential_profit": "Potential profit",
    "patterns.out_expectancy": "Expectancy",
    "patterns.per_trade_suffix": " R / trade",
    "patterns.out_per_100": "Per 100 trades",
    "patterns.r_suffix": " R",
    "patterns.verdict_positive": "Positive expectancy: the system is profitable over time with discipline.",
    "patterns.verdict_zero": "Zero expectancy: the system breaks even before costs.",
    "patterns.verdict_negative": "Negative expectancy: the system loses over time. Reconsider your R or win rate.",
    "patterns.out_dd_from_peak": "Drawdown from peak",
    "patterns.out_need_recover": "Needed to recover",
    "patterns.out_capital_left": "Capital remaining",
    "patterns.out_dd_size": "Drawdown size",

    // ── google-callback.html ──
    "callback.page_title": "SBF Academy — Google login",
    "callback.connecting": "Finishing Google login…",
    "callback.google_cancelled": "Google cancelled the login: ",
    "callback.missing_data": "Couldn't get data from Google. Please try again from your profile in Telegram.",
    "callback.link_error": "Linking error",
    "callback.success": "Google linked. Return to Telegram and reopen your profile — the tab will update itself.",
    "callback.generic_fail": "Couldn't complete linking. Please try again from your profile in Telegram.",
  },
};

// ── Language detection ────────────────────────────────────────────────────
function _detectLang() {
  try {
    var stored = window.localStorage && localStorage.getItem("sbf_lang");
    if (stored === "ru" || stored === "ro") return stored;
  } catch (e) { /* localStorage недоступен (приватный режим и т.п.) — игнорируем */ }

  try {
    var tg = window.Telegram && window.Telegram.WebApp;
    var code = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code;
    if (code && String(code).toLowerCase().indexOf("ro") === 0) return "ro";
  } catch (e) { /* window.Telegram отсутствует (вне Telegram) — используем дефолт */ }

  return "ru";
}

var _lang = _detectLang();
var _missingLogged = {};

function t(key, fallback) {
  var dict = STRINGS[_lang] || STRINGS.ru;
  var val = dict[key];
  if (val === undefined && _lang !== "ru") val = STRINGS.ru[key];
  if (val === undefined) {
    if (fallback !== undefined) val = fallback;
    else {
      val = key;
      if (!_missingLogged[key]) {
        _missingLogged[key] = true;
        console.warn("i18n: ключ отсутствует нигде — " + key);
      }
    }
  }
  return val;
}

function setLang(lang) {
  if (lang !== "ru" && lang !== "ro") return;
  try { localStorage.setItem("sbf_lang", lang); } catch (e) { /* ignore */ }
  location.reload();
}

window.sbfI18n = { lang: _lang, t: t, setLang: setLang };

// ── <html lang> ───────────────────────────────────────────────────────────
try { document.documentElement.lang = _lang; } catch (e) { /* ignore */ }

// ── Static-HTML pages (patterns.html, google-callback.html): declarative
// data-i18n attributes so plain markup (no client-side rendering like app.js)
// can still be translated. Fallback text stays as the literal RU content
// already in the HTML, so it degrades gracefully if this pass fails.
function _applySbfI18nDom() {
  try {
    var els = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      el.textContent = t(el.getAttribute("data-i18n"), el.textContent);
    }
    var phEls = document.querySelectorAll("[data-i18n-placeholder]");
    for (var j = 0; j < phEls.length; j++) {
      var pel = phEls[j];
      pel.setAttribute("placeholder", t(pel.getAttribute("data-i18n-placeholder"), pel.getAttribute("placeholder") || ""));
    }
    var titleEls = document.querySelectorAll("[data-i18n-title]");
    for (var k = 0; k < titleEls.length; k++) {
      var tel = titleEls[k];
      tel.setAttribute("title", t(tel.getAttribute("data-i18n-title"), tel.getAttribute("title") || ""));
    }
  } catch (e) { /* ignore — не блокируем страницу из-за i18n */ }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", _applySbfI18nDom);
} else {
  _applySbfI18nDom();
}
