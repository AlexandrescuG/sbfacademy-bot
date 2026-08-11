"use strict";


// В Telegram Mini App и на web.sbfconsult.com webapp/ отдаётся тем же
// origin, что и API — относительный путь работает как есть. В нативной
// Capacitor-обёртке (Android/iOS) страница грузится из capacitor://localhost,
// поэтому нужен абсолютный адрес публичного бэкенда.
const API_BASE    = (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())
  ? "https://web.sbfconsult.com"
  : "";
// Не секрет — спокойно живёт в клиентском JS.
const GOOGLE_CLIENT_ID = "334099177351-19nnlv6jkp4biuf3og105377kpuikk01.apps.googleusercontent.com";
const TOKEN_KEY   = "sbfa_at";
const REFRESH_KEY = "sbfa_rt";
const STREAK_KEY  = "sbfa_streak";

// i18n.js гарантированно грузится раньше (см. порядок <script> в index.html),
// поэтому window.sbfI18n тут уже готов. Алиас называется T (не t!) — в этом
// файле переменная `t` сплошь используется как параметр map()-колбэков
// (тема брифинга, сделка дневника, элемент тулбара — см. buildTools,
// renderJournal, renderBriefing) и локально шэдовила бы функцию перевода.
const T = window.sbfI18n.t;
const _dateLocale = window.sbfI18n.lang === "ro" ? "ro-RO" : "ru-RU";

// ── Concept cross-links ───────────────────────────────────────────────────────
const _CM_BY_CHEAT = {
  risk_rr:          {chapter:3},
  risk_position_size:{chapter:3},
  risk_drawdown:    {chapter:3},
  event_cpi:        {chapter:6},
  event_nfp:        {chapter:6},
  event_fomc:       {chapter:6},
  event_pce:        {chapter:6},
  ind_rsi:          {chapter:9,  grafik:{cat:'ind',   key:'rsi'}},
  ind_macd:         {chapter:9,  grafik:{cat:'ind',   key:'macd'}},
  chart_double_top: {chapter:10, grafik:{cat:'chart', key:'dtop'}},
  chart_wedge:      {chapter:10, grafik:{cat:'chart', key:'wedge'}},
  chart_flag:       {chapter:10, grafik:{cat:'chart', key:'flag'}},
};
const _CM_KEYWORDS = {
  "PCE":"event_pce","CPI":"event_cpi","NFP":"event_nfp","FOMC":"event_fomc","ФРС":"event_fomc",
  "RSI":"ind_rsi","MACD":"ind_macd",
};

// Единый проход по тексту: экономические концепты (_CM_KEYWORDS) ведут к шпаргалке,
// термины глоссария — к всплывающему окну с этимологией. Важно делать это ОДНИМ
// проходом: часть слов (PCE, FOMC, NFP) есть в обоих словарях, и два независимых
// regex-прохода задвоили бы обёртку (span в span, двойной клик-хэндлер).
function _linkConcepts(text) {
  if (!text) return "";
  let result = esc(text);
  const entries = Object.entries(_CM_KEYWORDS).map(([kw, id]) => [kw, `openCheatsheet('${id}')`]);
  _GLOSSARY.forEach((g, idx) => {
    if (!_CM_KEYWORDS[g.term]) entries.push([g.term, `showEtymology(${idx})`]);
  });
  entries.sort((a, b) => b[0].length - a[0].length);
  // \b в JS-regex понимает только ASCII \w — для кириллицы границы слов ломаются.
  // Считаем границей начало строки или любой не-буквенно-цифровой символ (Latin+Cyrillic).
  const WORD = "a-zA-Zа-яА-ЯёЁ0-9";
  for (const [kw, action] of entries) {
    const safe = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(^|[^${WORD}])(${safe})(?![${WORD}])`, "g");
    result = result.replace(re, (_, pre, word) =>
      `${pre}<span class="concept-chip" onclick="${action}">${word}</span>`);
  }
  return result;
}

// ── Telegram Mini App ─────────────────────────────────────────────────────────
const TG = window.Telegram?.WebApp;

// Вызываем ready() с ретраями — на случай если WebApp инжектится позже
function tgReady() {
  var t = window.Telegram && window.Telegram.WebApp;
  if (t) { try { t.ready(); t.expand(); } catch(e) {} return true; }
  return false;
}
if (!tgReady()) {
  var _tgRetry = 0;
  var _tgIv = setInterval(function(){
    if (tgReady() || ++_tgRetry > 20) clearInterval(_tgIv);
  }, 100);
}

function isTMA() { return !!(TG && TG.initData); }

// ── Auth tokens ───────────────────────────────────────────────────────────────
const tok = {
  get:     () => localStorage.getItem(TOKEN_KEY),
  getRef:  () => localStorage.getItem(REFRESH_KEY),
  save:    (a, r) => { localStorage.setItem(TOKEN_KEY, a); if (r) localStorage.setItem(REFRESH_KEY, r); },
  clear:   () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_KEY); },
};

// ── Fetch helper ──────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const hdrs = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (tok.get())      hdrs["Authorization"] = "Bearer " + tok.get();
  else if (isTMA())   hdrs["Authorization"] = "tma " + TG.initData;

  let r = await fetch(API_BASE + path, { ...opts, headers: hdrs });

  if (r.status === 401) {
    tok.clear();
    if (isTMA()) {
      try {
        const tr = await fetch(API_BASE + "/api/auth/tma", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ init_data: TG.initData }),
        });
        if (tr.ok) { const d = await tr.json(); tok.save(d.access_token, d.refresh_token || null); }
      } catch { /* ignore */ }
    } else if (tok.getRef()) {
      // Web: попробовать обновить токен через refresh
      try {
        const rr = await fetch(API_BASE + "/api/auth/refresh", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: tok.getRef() }),
        });
        if (rr.ok) { const d = await rr.json(); tok.save(d.access_token, null); }
        else tok.clear();
      } catch { tok.clear(); }
    }
    if (tok.get()) {
      hdrs["Authorization"] = "Bearer " + tok.get();
      r = await fetch(API_BASE + path, { ...opts, headers: hdrs });
    }
    // Ни один способ восстановить сессию не сработал (протухший токен без
    // refresh_token — например, TMA-токен, занесённый в тот же localStorage
    // обычным браузером, или сам refresh не удался) — раньше это оставляло
    // экран (Профиль и т.п.) в состоянии "Ошибка загрузки" навсегда, хотя
    // единственный реальный выход — залогиниться заново. Делаем это автоматом.
    if (r.status === 401) _forceRelogin();
  }
  return r;
}

// ── Reading streak ────────────────────────────────────────────────────────────
function updateStreak() {
  const today = new Date().toISOString().slice(0, 10);
  let data = JSON.parse(localStorage.getItem(STREAK_KEY) || '{"last":"","count":0}');
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  if (data.last === today) return data.count;
  data.count = (data.last === yesterday) ? data.count + 1 : 1;
  data.last = today;
  localStorage.setItem(STREAK_KEY, JSON.stringify(data));
  return data.count;
}

// ── Router ────────────────────────────────────────────────────────────────────
const _screens = {};
function showScreen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  if (!_screens[name]) {
    const el = document.createElement("div");
    el.id = "screen-" + name; el.className = "screen";
    _screens[name] = el;
    document.getElementById("app").insertBefore(el, document.querySelector(".nav-bar"));
    buildScreen(name, el);
  }
  _screens[name].classList.add("active");
  document.querySelectorAll(".nav-item").forEach(n =>
    n.classList.toggle("active", n.dataset.tab === name));
}

function buildScreen(name, el) {
  switch (name) {
    case "today":   buildToday(el);   break;
    case "grafik":  buildGrafik(el);  break;
    case "edu":     buildEdu(el);     break;
    case "tools":   buildTools(el);   break;
    case "profile": buildProfile(el); break;
  }
}

// Откатывает приложение к экрану входа при неисправимо протухшей сессии —
// см. вызов в api() на финальном необработанном 401.
function _forceRelogin() {
  tok.clear();
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.querySelector(".nav-bar")?.remove();
  showLogin();
  document.getElementById("screen-splash").classList.add("active");
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function boot() {
  const ok = await ensureAuth();
  if (ok || isTMA()) { afterAuth(); return; }
  // Standalone (Android/iOS APK, вне Telegram) без валидного токена — экран входа
  showLogin();
}

function afterAuth() {
  buildNav(); showScreen("today");
  // URL param from edu → app redirect (sbfNavigate fallback)
  const _p = new URLSearchParams(location.search);
  const _tool = _p.get("sbf_tool");
  if (_tool) setTimeout(() => openTool(_tool), 200);
  // postMessage from edu iframe
  window.addEventListener("message", function(e) {
    if (e.origin !== "https://lp.sbfconsult.com") return;
    if (!e.data) return;
    if (e.data.type === "sbfNavigate") openTool(e.data.tool);
    if (e.data.type === "sbf-grafik") openGrafik(e.data.cat, e.data.key);
    if (e.data.type === "sbf-resize") {
      const f = document.querySelector(".today-frame");
      if (f && f.contentWindow === e.source) f.style.height = e.data.height + "px";
    }
  });
}

async function ensureAuth() {
  // В Telegram initData всегда под рукой — переобмениваем его на свежий токен
  // ПРОАКТИВНО при каждом старте, а не только когда сохранённый токен уже
  // протух. Раньше тут стояло `if (tok.get()) return true`, из-за чего
  // старый (например, оставшийся с прошлого перезапуска сервера — там
  // секрет для подписи JWT мог обновиться) токен использовался вслепую;
  // ошибка обнаруживалась только реактивно, при первом же 401 от любого
  // защищённого эндпоинта (см. историю обзоров).
  if (TG && TG.initData) {
    try {
      const r = await fetch(API_BASE + "/api/auth/tma", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ init_data: TG.initData }),
      });
      if (r.ok) { const d = await r.json(); tok.save(d.access_token, d.refresh_token || null); return true; }
    } catch { /* сеть недоступна — используем то, что уже сохранено */ }
  }
  if (tok.get()) return true;
  // Web: попробовать тихий refresh если refresh_token есть
  if (tok.getRef()) {
    try {
      const r = await fetch(API_BASE + "/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tok.getRef() }),
      });
      if (r.ok) { const d = await r.json(); tok.save(d.access_token, null); return true; }
    } catch { /* ignore */ }
    tok.clear();
  }
  return false;
}

// ── Standalone login (Android/iOS APK, email+password) ────────────────────────
let _authMode = "login";

function showLogin() {
  const el = document.getElementById("screen-splash");
  el.innerHTML = `
    <div class="splash-logo">
      <div class="logo-mark">SBF</div>
      <div class="logo-sub">ACADEMY</div>
    </div>
    <form id="login-form" style="width:100%;max-width:320px;padding:0 24px;box-sizing:border-box" onsubmit="return handleLoginSubmit(event)">
      <input type="email" id="login-email" placeholder="Email" required autocomplete="email"
        style="width:100%;padding:13px;margin-bottom:10px;border:1px solid #E7DFCF;border-radius:8px;font-size:15px;box-sizing:border-box">
      <input type="password" id="login-password" placeholder="${T('auth.password_placeholder','Пароль')}" required minlength="8" autocomplete="current-password"
        style="width:100%;padding:13px;margin-bottom:6px;border:1px solid #E7DFCF;border-radius:8px;font-size:15px;box-sizing:border-box">
      <div style="text-align:right;margin-bottom:10px">
        <a href="#" onclick="showForgotPassword();return false" style="font-size:12px;color:var(--text2)">${T('auth.forgot_password','Забыли пароль?')}</a>
      </div>
      <div id="login-error" style="color:#C0392B;font-size:13px;margin-bottom:10px;display:none"></div>
      <button type="submit" class="btn" id="login-submit">${T('auth.login_btn','Войти')}</button>
      <div style="text-align:center;margin-top:14px;font-size:13px;color:var(--text2)">
        <span id="login-toggle-text">${T('auth.no_account','Нет аккаунта?')}</span>
        <a href="#" onclick="toggleAuthMode();return false" id="login-toggle-link">${T('auth.register_link','Зарегистрироваться')}</a>
      </div>
    </form>
    <div id="otp-section" class="hidden" style="width:100%;max-width:320px;padding:0 24px;box-sizing:border-box">
      <div style="font-size:13px;color:var(--text2);margin-bottom:10px">${T('auth.otp_intro','Пришлём одноразовый код на почту — пароль для входа не нужен.')}</div>
      <input type="email" id="otp-email" placeholder="Email" required autocomplete="email"
        style="width:100%;padding:13px;margin-bottom:10px;border:1px solid #E7DFCF;border-radius:8px;font-size:15px;box-sizing:border-box">
      <button type="button" class="btn" id="otp-request-btn" onclick="requestOtpCode()">${T('auth.otp_send_btn','Отправить код')}</button>
      <div id="otp-code-row" class="hidden" style="margin-top:10px">
        <input type="text" id="otp-code" placeholder="${T('auth.otp_code_placeholder','Код из письма')}" inputmode="numeric" autocomplete="one-time-code"
          style="width:100%;padding:13px;margin-bottom:10px;border:1px solid #E7DFCF;border-radius:8px;font-size:15px;box-sizing:border-box">
        <button type="button" class="btn" onclick="verifyOtpCode()">${T('auth.otp_login_btn','Войти по коду')}</button>
      </div>
      <div id="otp-error" style="color:#C0392B;font-size:13px;margin-top:8px;display:none"></div>
      <div style="text-align:center;margin-top:14px">
        <a href="#" onclick="hideForgotPassword();return false" style="font-size:12px;color:var(--text2)">${T('auth.back_to_password','← Назад к паролю')}</a>
      </div>
    </div>
    <div class="login-divider" id="login-divider"><span>${T('auth.or','или')}</span></div>
    <div id="login-providers" style="width:100%;max-width:320px;padding:0 24px;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;gap:10px">
      <div id="google-login-btn"></div>
    </div>
    <div style="text-align:center;font-size:12px;color:var(--text2);margin-top:10px">${T('auth.telegram_hint','Вход через Telegram — в самом приложении Telegram')}</div>`;
  // Telegram Login Widget здесь больше не рендерим: BotFather позволяет привязать
  // виджет только к ОДНОМУ домену разом, и он теперь закреплён за
  // lp.sbfconsult.com (см. web/login.html) — там, где нужен именно "вход
  // на сайте", а не Mini App. Сама Mini App (внутри Telegram) этим не
  // затронута — initData отдельный механизм, доменом не ограничен.
  _renderGoogleButton(document.getElementById("google-login-btn"), "onGoogleCredential");
}

function showForgotPassword() {
  document.getElementById("login-form").classList.add("hidden");
  document.getElementById("otp-section").classList.remove("hidden");
  const email = document.getElementById("login-email")?.value.trim();
  if (email) document.getElementById("otp-email").value = email;
}

function hideForgotPassword() {
  document.getElementById("otp-section").classList.add("hidden");
  document.getElementById("login-form").classList.remove("hidden");
}

async function requestOtpCode() {
  const email = document.getElementById("otp-email").value.trim();
  const errEl = document.getElementById("otp-error");
  errEl.style.display = "none";
  if (!email) return;
  const btn = document.getElementById("otp-request-btn");
  btn.disabled = true;
  try {
    const r = await fetch(API_BASE + "/api/auth/request-code", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('auth.otp_send_error','Не удалось отправить код'));
    document.getElementById("otp-code-row").classList.remove("hidden");
    btn.textContent = T('auth.otp_resend_btn','Отправить код ещё раз');
  } catch (err) {
    errEl.textContent = err.message || T('auth.otp_send_error','Не удалось отправить код');
    errEl.style.display = "block";
  } finally {
    btn.disabled = false;
  }
}

async function verifyOtpCode() {
  const email = document.getElementById("otp-email").value.trim();
  const code = document.getElementById("otp-code").value.trim();
  const errEl = document.getElementById("otp-error");
  errEl.style.display = "none";
  try {
    const r = await fetch(API_BASE + "/api/auth/verify", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('auth.otp_invalid_code','Неверный код'));
    tok.save(d.access_token, d.refresh_token || null);
    afterAuth();
  } catch (err) {
    errEl.textContent = err.message || T('auth.otp_invalid_code','Неверный код');
    errEl.style.display = "block";
  }
}

// ── Google Sign-In — общий рендерер ─────────────────────────────────────────
// Используется и на экране входа (login/onGoogleCredential), и в профиле для
// привязки способа входа к уже залогиненному аккаунту (link/onGoogleLinkCredential)
// — разница только в callback-имени. Telegram Login Widget здесь больше не
// рендерим (см. showLogin()/linkProvider('telegram') — BotFather держит домен
// виджета один на бота, сейчас это lp.sbfconsult.com, не web.sbfconsult.com).
function _renderGoogleButton(host, callbackName, tries) {
  if (!host || !GOOGLE_CLIENT_ID) return;
  if (window.google && window.google.accounts && window.google.accounts.id) {
    host.innerHTML = "";
    google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: window[callbackName] });
    google.accounts.id.renderButton(host, { theme: "outline", size: "large", width: 272 });
  } else if ((tries || 0) < 25) {
    setTimeout(() => _renderGoogleButton(host, callbackName, (tries || 0) + 1), 200);
  }
}

function _showLoginError(message) {
  const errEl = document.getElementById("login-error");
  if (errEl) { errEl.textContent = message; errEl.style.display = "block"; }
}

async function onTelegramAuth(user) {
  try {
    const r = await fetch(API_BASE + "/api/auth/telegram", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(user),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('auth.telegram_login_error','Не удалось войти через Telegram'));
    tok.save(d.access_token, d.refresh_token || null);
    afterAuth();
  } catch (err) {
    _showLoginError(err.message || T('auth.telegram_login_error','Не удалось войти через Telegram'));
  }
}
window.onTelegramAuth = onTelegramAuth;

async function onGoogleCredential(response) {
  try {
    const r = await fetch(API_BASE + "/api/auth/google", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('auth.google_login_error','Не удалось войти через Google'));
    tok.save(d.access_token, d.refresh_token || null);
    afterAuth();
  } catch (err) {
    _showLoginError(err.message || T('auth.google_login_error','Не удалось войти через Google'));
  }
}
window.onGoogleCredential = onGoogleCredential;

function toggleAuthMode() {
  _authMode = _authMode === "login" ? "register" : "login";
  document.getElementById("login-submit").textContent =
    _authMode === "login" ? T('auth.login_btn','Войти') : T('auth.register_link','Зарегистрироваться');
  document.getElementById("login-toggle-text").textContent =
    _authMode === "login" ? T('auth.no_account','Нет аккаунта?') : T('auth.has_account','Уже есть аккаунт?');
  document.getElementById("login-toggle-link").textContent =
    _authMode === "login" ? T('auth.register_link','Зарегистрироваться') : T('auth.login_btn','Войти');
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  const btn = document.getElementById("login-submit");
  errEl.style.display = "none";
  btn.disabled = true;
  try {
    const r = await fetch(API_BASE + "/api/auth/" + _authMode, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('auth.login_error','Не удалось выполнить вход'));
    tok.save(d.access_token, d.refresh_token || null);
    afterAuth();
  } catch (err) {
    errEl.textContent = err.message || T('auth.login_error','Не удалось выполнить вход');
    errEl.style.display = "block";
  } finally {
    btn.disabled = false;
  }
  return false;
}

// ── Nav ───────────────────────────────────────────────────────────────────────
function buildNav() {
  if (document.querySelector(".nav-bar")) return;
  const nav = document.createElement("div");
  nav.className = "nav-bar";
  nav.innerHTML = `
    <div class="nav-item active" data-tab="today"   onclick="showScreen('today')">   <span class="ni">📊</span><span>${T('nav.today','Сегодня')}</span></div>
    <div class="nav-item"        data-tab="grafik"  onclick="showScreen('grafik')">  <span class="ni">📈</span><span>${T('nav.grafik','График')}</span></div>
    <div class="nav-item"        data-tab="edu"     onclick="showScreen('edu')">     <span class="ni">📚</span><span>${T('nav.edu','Обучение')}</span></div>
    <div class="nav-item"        data-tab="tools"   onclick="showScreen('tools')">   <span class="ni">🛠</span><span>${T('nav.tools','Инструменты')}</span></div>
    <div class="nav-item"        data-tab="profile" onclick="showScreen('profile')"> <span class="ni">👤</span><span>${T('nav.profile','Профиль')}</span></div>`;
  document.getElementById("app").appendChild(nav);
}

// ── TODAY ─────────────────────────────────────────────────────────────────────
function buildToday(el) {
  const streak = updateStreak();
  const dStr = new Date().toLocaleDateString(_dateLocale, { day:"numeric", month:"long" });
  el.innerHTML = `
    <div class="today-header">
      <div>
        <h2>${T('today.title','Обзор рынка')}</h2>
        <div class="today-date">${dStr}</div>
      </div>
      <div class="header-right">
        ${streak > 1 ? `<div class="streak-badge" onclick="showStreakInfo(${streak})">🔥 ${streak}</div>` : ""}
        <button class="icon-btn" onclick="openHistory(this)" title="${T('today.history_title','История обзоров')}">🕐</button>
      </div>
    </div>
    <div id="mindset-bar" class="mindset-bar"><div class="spinner" style="width:16px;height:16px;border-width:2px"></div></div>
    <div id="history-panel" class="history-panel hidden"></div>
    <div id="today-content"><iframe class="today-frame" src="https://lp.sbfconsult.com/?embed=1&autoheight=1" loading="lazy"></iframe></div>`;
  loadMindset(el);
  _bindMindsetAutoHide(el);
}

// Цитата дня приклеена к верху (position:sticky), но занимает место над
// отчётом — прячем при скролле вниз и возвращаем при скролле вверх,
// чтобы не мешала чтению отчёта, но оставалась доступна одним свайпом.
function _bindMindsetAutoHide(el) {
  const bar = el.querySelector("#mindset-bar");
  if (!bar) return;
  let lastY = el.scrollTop;
  el.addEventListener("scroll", () => {
    const y = el.scrollTop;
    const delta = y - lastY;
    if (Math.abs(delta) < 4) return;
    if (delta > 0 && y > bar.offsetHeight) bar.classList.add("mindset-hidden");
    else bar.classList.remove("mindset-hidden");
    lastY = y;
  }, { passive: true });
}

async function loadMindset(el) {
  const bar = el.querySelector("#mindset-bar");
  if (!bar) return;
  try {
    const r = await fetch("/api/mindset");
    if (r.ok) {
      const d = await r.json();
      bar.textContent = `💡 ${d.prompt}`;
    } else { bar.remove(); }
  } catch { bar.remove(); }
}

function renderBriefing(d) {
  // Раньше headline рендерился отдельной жирной строкой НАД темами — но headline
  // это и есть первый буллет первой темы ("Краткое содержание"), так что текст
  // буквально дублировался. Убрали строку, оставили только сами темы.
  const themes = (d.themes || []).map((t, i) => `
    <div class="theme-block${i === 0 ? " open" : ""}">
      <button class="theme-hd" onclick="this.parentElement.classList.toggle('open')">
        <span class="theme-title">${_linkConcepts(t.title)}</span>
        <span class="theme-arrow">▾</span>
      </button>
      <div class="theme-body">${_linkConcepts(t.body)}</div>
    </div>`).join("");
  return `
    <div class="briefing-card">
      <div class="themes-list">${themes}</div>
      <div class="disclaimer">${esc(d.disclaimer || "")}</div>
    </div>`;
}

async function openHistory(btn) {
  const panel = document.getElementById("history-panel");
  if (!panel.classList.contains("hidden")) { panel.classList.add("hidden"); return; }
  panel.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  panel.classList.remove("hidden");
  try {
    const r = await api("/api/briefing/archive");
    if (!r.ok) throw new Error(r.status);
    const list = await r.json();
    if (list.length < 1) { panel.innerHTML = `<div class="empty-state">${T('today.no_history','Пока нет истории')}</div>`; return; }
    panel.innerHTML = list.map(item => `
      <div class="hist-item" onclick="loadArchiveDate('${esc(item.date)}')">
        <span class="hist-date">${item.date}</span>
        <span class="hist-hl">${esc(item.headline || item.date)}</span>
      </div>`).join("");
  } catch { panel.innerHTML = `<div class="empty-state">${T('common.load_error','Ошибка загрузки')}</div>`; }
}

async function loadArchiveDate(date) {
  document.getElementById("history-panel").classList.add("hidden");
  const box = document.querySelector("#today-content");
  if (!box) return;
  box.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  try {
    const r = await api(`/api/briefing/${date}`);
    if (!r.ok) throw new Error(r.status);
    box.innerHTML = renderBriefing(await r.json());
  } catch { box.innerHTML = `<div class="empty-state">${T('today.archive_not_found','Обзор не найден')}</div>`; }
}

// ── EDUCATION ────────────────────────────────────────────────────────────────
function buildEdu(el, chapter) {
  const eduUrl = chapter
    ? `https://lp.sbfconsult.com/edu/b/${chapter}?embed=1`
    : "https://lp.sbfconsult.com/edu/?embed=1";
  el.innerHTML = `
    <div class="edu-header"><h2>${T('nav.edu','Обучение')}</h2></div>
    <iframe class="edu-frame" src="${eduUrl}" allow="fullscreen" loading="lazy"></iframe>`;
}

// ── GRAFIK ────────────────────────────────────────────────────────────────────
// Живой график с реальной ценой и уровнями (Пивоты/Паттерны/SMC) + библиотека
// схематичных паттернов ниже — тот же "Технический" вид, что на lp.sbfconsult.com,
// просто открытый через #tech. Раньше здесь был только собственный схематичный
// grafik.html без реальных данных и без уровней поддержки/сопротивления.
function _grafikSrc(cat, key) {
  // embed=1 просит market_intel скрыть свою шапку/тикер и переключатель
  // Фундаментальный/Технический — внутри мини-аппа это Сегодня-таб и наш собственный
  // хедер, показывать их ещё раз поверх было бы дублированием.
  return `https://lp.sbfconsult.com/?embed=1${(cat && key) ? `#tech/${cat}/${key}` : "#tech"}`;
}

function buildGrafik(el, cat, key) {
  el.innerHTML = `<iframe class="grafik-frame" src="${_grafikSrc(cat, key)}" loading="lazy" allow="fullscreen"></iframe>`;
}

function openGrafik(cat, key) {
  if (_screens["grafik"]) {
    const frame = _screens["grafik"].querySelector(".grafik-frame");
    if (frame) frame.src = _grafikSrc(cat, key);
    showScreen("grafik");
  } else {
    showScreen("grafik");
    const frame = _screens["grafik"]?.querySelector(".grafik-frame");
    if (frame) frame.src = _grafikSrc(cat, key);
  }
}

function openByConcept(cheatId) {
  const entry = _CM_BY_CHEAT[cheatId];
  if (entry?.grafik) openGrafik(entry.grafik.cat, entry.grafik.key);
  else openCheatsheet(cheatId);
}

function openEduChapter(ch) {
  if (_screens["edu"]) {
    const frame = _screens["edu"].querySelector(".edu-frame");
    if (frame) frame.src = `https://lp.sbfconsult.com/edu/b/${ch}?embed=1`;
    showScreen("edu");
  } else {
    // buildScreen("edu") будет вызван внутри showScreen → buildEdu без главы,
    // поэтому сначала создаём экран, потом меняем src
    showScreen("edu");
    const frame = _screens["edu"]?.querySelector(".edu-frame");
    if (frame) frame.src = `https://lp.sbfconsult.com/edu/b/${ch}?embed=1`;
  }
}

async function openCheatsheet(id) {
  showScreen("tools");
  await new Promise(r => setTimeout(r, 80));
  const drop = document.getElementById("tool-drop-cheatsheets");
  if (!drop?.classList.contains("open")) {
    await toggleTool("cheatsheets");
    await new Promise(r => setTimeout(r, 300));
  }
  await showCheatsheet(id);
}


// ── TOOLS ─────────────────────────────────────────────────────────────────────
const _TOOL_DEFS = [
  { id: "journal",     icon: "📓", name: T('tool.journal.name','Дневник трейдера'),         desc: T('tool.journal.desc','Сделки, аналитика, зеркало поведения') },
  { id: "cheatsheets", icon: "📋", name: T('tool.cheatsheets.name','Шпаргалки'),             desc: T('tool.cheatsheets.desc','Индикаторы, паттерны, события — офлайн') },
  { id: "checklist",   icon: "✅", name: T('tool.checklist.name','Чек-лист перед сделкой'),  desc: T('tool.checklist.desc','Дисциплина входа: 4 вопроса') },
  { id: "calendar",    icon: "📅", name: T('tool.calendar.name','Эконом-календарь'),         desc: T('tool.calendar.desc','FOMC, CPI, NFP и другие ключевые события') },
  { id: "patterns",    icon: "🧮", name: T('tool.patterns.name','Риск-калькулятор'),         desc: T('tool.patterns.desc','Позиция, ожидание системы, просадка') },
  { id: "sessions",    icon: "🌍", name: T('tool.sessions.name','Сессии рынка'),             desc: T('tool.sessions.desc','Какие сессии открыты прямо сейчас') },
  { id: "glossary",    icon: "📖", name: T('tool.glossary.name','Глоссарий'),                desc: T('tool.glossary.desc','Термины трейдера от A до Я') },
];

function buildTools(el) {
  const items = _TOOL_DEFS.map(t => `
    <div class="tool-item">
      <div class="tool-card" id="tool-card-${t.id}" onclick="toggleTool('${t.id}')">
        <div class="tool-icon">${t.icon}</div>
        <div class="tool-info">
          <div class="tool-name">${t.name}</div>
          <div class="tool-desc">${t.desc}</div>
        </div>
        <div class="tool-chevron" id="tool-chev-${t.id}">›</div>
      </div>
      <div class="tool-drop" id="tool-drop-${t.id}"></div>
    </div>`).join("");
  el.innerHTML = `<div class="tools-header"><h2>${T('nav.tools','Инструменты')}</h2></div>
    <div class="tools-list">${items}</div>`;
}

async function toggleTool(name, openForm) {
  const drop = document.getElementById("tool-drop-" + name);
  const chev = document.getElementById("tool-chev-" + name);
  const card = document.getElementById("tool-card-" + name);
  if (!drop) return;

  const isOpen = drop.classList.contains("open");

  // Close all
  document.querySelectorAll(".tool-drop.open").forEach(d => { d.classList.remove("open"); d.innerHTML = ""; });
  document.querySelectorAll(".tool-chevron").forEach(c => c.classList.remove("rotated"));
  document.querySelectorAll(".tool-card.t-active").forEach(c => c.classList.remove("t-active"));

  if (isOpen) return;

  drop.classList.add("open");
  chev?.classList.add("rotated");
  card?.classList.add("t-active");
  drop.innerHTML = `<div class="center-spin" style="padding:20px 0"><div class="spinner"></div></div>`;

  switch (name) {
    case "journal":     await renderJournal(drop, openForm === "new"); break;
    case "cheatsheets": await renderCheatsheets(drop); break;
    case "checklist":   await renderChecklist(drop); break;
    case "calendar":    await renderCalendar(drop); break;
    case "patterns":    drop.innerHTML = `<iframe class="tool-frame" src="/patterns.html" loading="lazy"></iframe>`; break;
    case "sessions":    drop.innerHTML = renderSessionsHTML(); break;
    case "glossary":    drop.innerHTML = `<iframe class="tool-frame" src="https://lp.sbfconsult.com/glossary" loading="lazy"></iframe>`; break;
  }
  drop.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function openTool(name) {
  showScreen("tools");
  await new Promise(r => setTimeout(r, 60));
  const isNew = name === "journal-new";
  await toggleTool(isNew ? "journal" : name, isNew ? "new" : null);
}

// ── JOURNAL ───────────────────────────────────────────────────────────────────
async function renderJournal(panel, showForm = false) {
  panel.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  try {
    const [tradesR, analyticsR] = await Promise.all([
      api("/api/journal/trades?limit=20"),
      api("/api/journal/analytics"),
    ]);
    const trades    = tradesR.ok    ? await tradesR.json()    : [];
    const analytics = analyticsR.ok ? await analyticsR.json() : {};

    const insights = (analytics.insights || []).map(i =>
      `<div class="insight-row">💡 ${esc(i)}</div>`).join("");
    const statsHtml = analytics.total ? `
      <div class="stats-grid">
        <div class="stat-cell"><div class="stat-val">${analytics.total}</div><div class="stat-lbl">${T('journal.stat_trades','Сделок')}</div></div>
        <div class="stat-cell"><div class="stat-val">${Math.round((analytics.winrate||0)*100)}%</div><div class="stat-lbl">${T('journal.stat_winrate','Винрейт')}</div></div>
        <div class="stat-cell"><div class="stat-val">${analytics.expectancy ?? "—"}R</div><div class="stat-lbl">${T('journal.stat_expectancy','Ожидание')}</div></div>
      </div>
      ${insights ? `<div class="insights-list">${insights}</div>` : ""}
    ` : "";

    const tradesHtml = trades.length ? trades.map(t => `
      <div class="trade-row">
        <div class="trade-meta">
          <span class="trade-instr">${esc(t.instrument||"—")}</span>
          <span class="trade-dir ${t.direction}">${t.direction||""}</span>
          ${t.setup_tag ? `<span class="trade-tag">${esc(t.setup_tag)}</span>` : ""}
          ${t.emotion_tag ? `<span class="trade-tag emo">${esc(t.emotion_tag)}</span>` : ""}
        </div>
        <div class="trade-pnl ${t.pnl > 0 ? 'pnl-pos' : t.pnl < 0 ? 'pnl-neg' : ''}">
          ${t.pnl != null ? (t.pnl > 0 ? "+" : "") + t.pnl.toFixed(2) : "—"}
          ${t.r_multiple != null ? `<span class="trade-r">${t.r_multiple > 0 ? "+" : ""}${t.r_multiple}R</span>` : ""}
        </div>
      </div>`).join("") : `<div class="empty-state" style="padding:20px 0">${T('journal.no_trades','Сделок пока нет')}</div>`;

    panel.innerHTML = `
      <div class="tool-widget">
        <div class="widget-title">📓 ${T('tool.journal.name','Дневник трейдера')}</div>
        ${statsHtml}
        <button class="btn" style="margin-bottom:12px" onclick="toggleTradeForm(this)">${T('journal.add_trade_btn','+ Записать сделку')}</button>
        <div id="trade-form-wrap" style="${showForm ? "" : "display:none"}">
          ${renderTradeForm()}
        </div>
        <div class="trades-list">${tradesHtml}</div>
      </div>`;
    if (showForm) document.getElementById("trade-form-wrap")?.scrollIntoView({ behavior: "smooth" });
  } catch { panel.innerHTML = `<div class="empty-state">${T('journal.load_error','Ошибка загрузки дневника')}</div>`; }
}

function toggleTradeForm(btn) {
  const wrap = document.getElementById("trade-form-wrap");
  if (!wrap) return;
  const visible = wrap.style.display !== "none";
  wrap.style.display = visible ? "none" : "";
  btn.textContent = visible ? T('journal.add_trade_btn','+ Записать сделку') : T('journal.hide_form_btn','— Скрыть форму');
}

function renderTradeForm() {
  const emotions = ["calm","fomo","fear","revenge","tired","confident","bored"];
  const setups   = ["breakout","pullback","range","reversal","news"];
  const emoOpts  = emotions.map(e => `<option value="${e}">${e}</option>`).join("");
  const setupOpts = setups.map(s => `<option value="${s}">${s}</option>`).join("");
  return `
    <div class="trade-form">
      <div class="tf-row"><input id="tf-instr" placeholder="${T('journal.instrument_placeholder','Инструмент (SPY, BTC…)')}" type="text">
        <select id="tf-dir"><option value="">${T('journal.direction_placeholder','Направление')}</option><option value="long">Long</option><option value="short">Short</option></select></div>
      <div class="tf-row"><select id="tf-setup"><option value="">${T('journal.setup_placeholder','Сетап')}</option>${setupOpts}</select>
        <select id="tf-emo"><option value="">${T('journal.emotion_placeholder','Эмоция')}</option>${emoOpts}</select></div>
      <div class="tf-row">
        <input id="tf-entry" placeholder="${T('journal.entry_price_placeholder','Цена входа')}" type="number" step="any">
        <input id="tf-exit"  placeholder="${T('journal.exit_price_placeholder','Цена выхода')}" type="number" step="any">
      </div>
      <div class="tf-row">
        <input id="tf-size"  placeholder="${T('journal.size_placeholder','Размер')}" type="number" step="any">
        <input id="tf-risk"  placeholder="${T('journal.risk_placeholder','Риск ($)')}" type="number" step="any">
      </div>
      <input id="tf-pnl" placeholder="${T('journal.pnl_placeholder','PnL (прибыль/убыток в $)')}" type="number" step="any" style="width:100%">
      <textarea id="tf-notes" placeholder="${T('journal.notes_placeholder','Заметки (необязательно)')}" rows="2"></textarea>
      <button class="btn" onclick="submitTrade()">${T('common.save_btn','Сохранить')}</button>
      <div id="tf-status" style="font-size:13px;color:var(--text3);margin-top:6px"></div>
    </div>`;
}

async function submitTrade() {
  const fields = {
    instrument:  document.getElementById("tf-instr")?.value.trim() || undefined,
    direction:   document.getElementById("tf-dir")?.value   || undefined,
    setup_tag:   document.getElementById("tf-setup")?.value || undefined,
    emotion_tag: document.getElementById("tf-emo")?.value   || undefined,
    entry_price: parseFloat(document.getElementById("tf-entry")?.value) || undefined,
    exit_price:  parseFloat(document.getElementById("tf-exit")?.value)  || undefined,
    size:        parseFloat(document.getElementById("tf-size")?.value)   || undefined,
    risk_amount: parseFloat(document.getElementById("tf-risk")?.value)   || undefined,
    pnl:         parseFloat(document.getElementById("tf-pnl")?.value)    ?? undefined,
    notes:       document.getElementById("tf-notes")?.value.trim()       || undefined,
  };
  const clean = Object.fromEntries(Object.entries(fields).filter(([,v]) => v !== undefined));
  const st = document.getElementById("tf-status");
  st.textContent = T('journal.saving','Сохраняем…');
  const r = await api("/api/journal/trades", { method: "POST", body: JSON.stringify(clean) });
  if (r.ok) {
    st.textContent = T('journal.trade_saved','✓ Сделка сохранена');
    await renderJournal(document.getElementById("tool-panel"));
  } else {
    const d = await r.json();
    st.textContent = T('journal.error_prefix','Ошибка: ') + (d.detail || r.status);
  }
}

// ── CHEATSHEETS ───────────────────────────────────────────────────────────────
const CAT_LABELS = {
  indicator: T('cheatsheets.cat_indicator','Индикаторы'), chart_pattern: T('cheatsheets.cat_chart_pattern','Граф. паттерны'),
  candle_pattern: T('cheatsheets.cat_candle_pattern','Свечные'), event: T('cheatsheets.cat_event','События рынка'), risk: T('cheatsheets.cat_risk','Риск')
};

async function renderCheatsheets(panel, query = "", category = "") {
  panel.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  const params = new URLSearchParams();
  if (query)    params.set("q", query);
  if (category) params.set("category", category);
  try {
    const r = await api(`/api/cheatsheets?${params}`);
    if (!r.ok) throw new Error(r.status);
    const cards = await r.json();

    const catBtns = Object.entries(CAT_LABELS).map(([k, v]) =>
      `<button class="cat-btn ${category === k ? "active" : ""}"
         onclick="renderCheatsheets(document.getElementById('tool-panel'),'${esc(query)}','${k}')">${v}</button>`
    ).join("");

    const grouped = {};
    for (const c of cards) (grouped[c.category] = grouped[c.category] || []).push(c);

    const cardsHtml = Object.entries(grouped).map(([cat, items]) => `
      <div class="cs-group">
        <div class="cs-group-title">${CAT_LABELS[cat] || cat}</div>
        ${items.map(c => `
          <div class="cs-card" onclick="showCheatsheet('${c.id}')">
            <div class="cs-title">${esc(c.title)}</div>
            <div class="cs-summary">${esc(c.summary)}</div>
          </div>`).join("")}
      </div>`).join("");

    panel.innerHTML = `
      <div class="tool-widget">
        <div class="widget-title">📋 ${T('tool.cheatsheets.name','Шпаргалки')}</div>
        <input type="search" placeholder="${T('cheatsheets.search_placeholder','Поиск: RSI, молот, NFP…')}" style="width:100%;margin-bottom:10px"
          value="${esc(query)}"
          oninput="renderCheatsheets(document.getElementById('tool-panel'),this.value,'${esc(category)}')">
        <div class="cat-bar">${catBtns}
          ${category ? `<button class="cat-btn" onclick="renderCheatsheets(document.getElementById('tool-panel'),'${esc(query)}','')">${T('cheatsheets.all_btn','× Все')}</button>` : ""}
        </div>
        <div id="cs-detail"></div>
        ${cards.length ? cardsHtml : `<div class="empty-state">${T('cheatsheets.no_results','Ничего не найдено')}</div>`}
      </div>`;
  } catch { panel.innerHTML = `<div class="empty-state">${T('common.load_error','Ошибка загрузки')}</div>`; }
}

async function showCheatsheet(id) {
  const detail = document.getElementById("cs-detail");
  if (!detail) return;
  const r = await api(`/api/cheatsheets/${id}`);
  if (!r.ok) return;
  const c = await r.json();
  const related = c.related ? c.related.split(",").filter(Boolean).map(rid =>
    `<span class="cs-related-tag" onclick="showCheatsheet('${rid.trim()}')">${rid.trim()}</span>`
  ).join("") : "";
  const _cmE = _CM_BY_CHEAT[id];
  const eduLink = _cmE?.chapter
    ? `<div class="cs-edu-link" onclick="openEduChapter(${_cmE.chapter})">${T('cheatsheets.learn_deeper','📚 Учить глубже')} → ${T('cheatsheets.chapter_word','Глава')} ${_cmE.chapter}</div>`
    : "";
  const grafikLink = _cmE?.grafik
    ? `<div class="cs-edu-link" style="margin-top:6px" onclick="openGrafik('${_cmE.grafik.cat}','${_cmE.grafik.key}')">${T('cheatsheets.show_on_chart','📈 Показать на графике')}</div>`
    : "";
  detail.innerHTML = `
    <div class="cs-detail-card">
      <div class="cs-detail-title">${esc(c.title)}</div>
      <div class="cs-detail-cat">${CAT_LABELS[c.category] || c.category}</div>
      <div class="cs-detail-body">${esc(c.body)}</div>
      ${related ? `<div class="cs-related"><span class="cs-rel-lbl">${T('cheatsheets.related_label','Связанные:')}</span>${related}</div>` : ""}
      ${eduLink}${grafikLink}
      <button class="btn btn-ghost" style="margin-top:12px" onclick="this.closest('.cs-detail-card').remove()">${T('common.close_btn','Закрыть')}</button>
    </div>`;
  detail.scrollIntoView({ behavior: "smooth" });
}

// ── CHECKLIST ─────────────────────────────────────────────────────────────────
async function renderChecklist(panel) {
  panel.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  try {
    const r = await api("/api/checklist/items");
    if (!r.ok) throw new Error(r.status);
    const items = await r.json();
    const itemsHtml = items.map(item => `
      <label class="cl-item">
        <input type="checkbox" id="cl-${item.id}" class="cl-check">
        <span class="cl-text">${esc(item.text)}</span>
      </label>`).join("");
    panel.innerHTML = `
      <div class="tool-widget">
        <div class="widget-title">✅ ${T('tool.checklist.name','Чек-лист перед сделкой')}</div>
        <div class="cl-list">${itemsHtml}</div>
        <button class="btn" style="margin-top:14px" onclick="submitChecklist(${JSON.stringify(items.map(i=>i.id))})">${T('checklist.confirm_btn','Подтвердить и продолжить')}</button>
        <div id="cl-result" style="margin-top:8px;font-size:13px;color:var(--text3)"></div>
      </div>`;
  } catch { panel.innerHTML = `<div class="empty-state">${T('common.load_error','Ошибка загрузки')}</div>`; }
}

async function submitChecklist(ids) {
  const answers = {};
  for (const id of ids) answers[id] = document.getElementById(`cl-${id}`)?.checked || false;
  const allOk = Object.values(answers).every(Boolean);
  const res = document.getElementById("cl-result");
  if (!allOk) {
    res.textContent = T('checklist.not_all_checked','⚠️ Не все пункты отмечены. Убедись, что готов.');
    res.style.color = "var(--red)";
    return;
  }
  const r = await api("/api/checklist/run", { method: "POST", body: JSON.stringify({ answers }) });
  res.textContent = r.ok ? T('checklist.passed','✓ Чек-лист пройден. Можно входить.') : T('checklist.save_error','Ошибка сохранения.');
  res.style.color = r.ok ? "var(--green)" : "var(--red)";
}

// ── CALENDAR ──────────────────────────────────────────────────────────────────
async function renderCalendar(panel) {
  panel.innerHTML = `<div class="center-spin"><div class="spinner"></div></div>`;
  const today = new Date().toISOString().slice(0, 10);
  try {
    const r = await api(`/api/calendar/events?date=${today}&impact=high`);
    if (!r.ok) throw new Error(r.status);
    const events = await r.json();
    const impactClass = { high: "imp-high", medium: "imp-med", low: "imp-low" };
    const evHtml = events.length ? events.map(ev => `
      <div class="ev-row">
        <div class="ev-meta">
          <span class="ev-country">${esc(ev.country)}</span>
          <span class="ev-impact ${impactClass[ev.impact]||""}">${ev.impact}</span>
        </div>
        <div class="ev-title">${esc(ev.title)}</div>
        <div class="ev-values">
          ${ev.actual   ? `<span class="ev-val">${T('calendar.actual_label','Факт: ')}<b>${esc(ev.actual)}</b></span>` : ""}
          ${ev.forecast ? `<span class="ev-val">${T('calendar.forecast_label','Прогноз: ')}${esc(ev.forecast)}</span>` : ""}
          ${ev.previous ? `<span class="ev-val">${T('calendar.previous_label','Пред.: ')}${esc(ev.previous)}</span>` : ""}
        </div>
        ${ev.yahoo_url ? `<a href="${esc(ev.yahoo_url)}" target="_blank" class="ev-link">${T('calendar.more_link','Подробнее →')}</a>` : ""}
      </div>`).join("") :
      `<div class="empty-state">${T('calendar.no_high_impact','Сегодня нет высокоимпактных событий 🟢')}<br>
        <small style="color:var(--text3)">${T('calendar.finnhub_note','Данные появятся после подключения FINNHUB_API_KEY')}</small></div>`;
    panel.innerHTML = `
      <div class="tool-widget">
        <div class="widget-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>📅 ${T('tool.calendar.name','Эконом-календарь')}</span>
          <select onchange="filterCalendar(this.value)" style="font-size:12px;padding:4px 8px">
            <option value="high">${T('calendar.impact_high','Высокий impact')}</option>
            <option value="medium">${T('calendar.impact_medium','Средний')}</option>
            <option value="">${T('calendar.impact_all','Все')}</option>
          </select>
        </div>
        <div id="cal-events">${evHtml}</div>
      </div>`;
  } catch { panel.innerHTML = `<div class="empty-state">${T('common.load_error','Ошибка загрузки')}</div>`; }
}

async function filterCalendar(impact) {
  const today = new Date().toISOString().slice(0, 10);
  const params = impact ? `?date=${today}&impact=${impact}` : `?date=${today}`;
  const r = await api(`/api/calendar/events${params}`);
  const evts = r.ok ? await r.json() : [];
  const impactClass = { high: "imp-high", medium: "imp-med", low: "imp-low" };
  document.getElementById("cal-events").innerHTML = evts.length
    ? evts.map(ev => `
      <div class="ev-row">
        <div class="ev-meta"><span class="ev-country">${esc(ev.country)}</span>
          <span class="ev-impact ${impactClass[ev.impact]||""}">${ev.impact}</span></div>
        <div class="ev-title">${esc(ev.title)}</div>
        ${ev.yahoo_url ? `<a href="${esc(ev.yahoo_url)}" target="_blank" class="ev-link">${T('calendar.more_link','Подробнее →')}</a>` : ""}
      </div>`).join("")
    : `<div class="empty-state">${T('calendar.no_events','Нет событий')}</div>`;
}

// Risk calculator
function renderRiskCalc() {
  return `
    <div class="tool-widget">
      <div class="widget-title">Калькулятор риска</div>
      <div class="calc-form">
        <div class="calc-row">
          <label>Депозит ($)</label>
          <input type="number" id="c-deposit" value="10000" min="1" oninput="calcRisk()">
        </div>
        <div class="calc-row">
          <label>Риск на сделку (%)</label>
          <input type="number" id="c-risk" value="1" min="0.1" max="10" step="0.1" oninput="calcRisk()">
        </div>
        <div class="calc-row">
          <label>Цена входа</label>
          <input type="number" id="c-entry" value="100" min="0.000001" step="any" oninput="calcRisk()">
        </div>
        <div class="calc-row">
          <label>Стоп-лосс</label>
          <input type="number" id="c-stop" value="95" min="0.000001" step="any" oninput="calcRisk()">
        </div>
      </div>
      <div class="calc-result" id="c-result">—</div>
    </div>`;
}

function calcRisk() {
  const deposit = parseFloat(document.getElementById("c-deposit")?.value) || 0;
  const riskPct = parseFloat(document.getElementById("c-risk")?.value) || 0;
  const entry   = parseFloat(document.getElementById("c-entry")?.value) || 0;
  const stop    = parseFloat(document.getElementById("c-stop")?.value) || 0;
  const res     = document.getElementById("c-result");
  if (!deposit || !riskPct || !entry || !stop || entry === stop) {
    res.textContent = "Заполните все поля"; return;
  }
  const riskUsd  = deposit * riskPct / 100;
  const riskPerU = Math.abs(entry - stop);
  const units    = riskUsd / riskPerU;
  const posSize  = units * entry;
  const dir      = entry > stop ? "Long" : "Short";
  res.innerHTML  = `
    <div class="res-row"><span>Риск $</span><b>$${riskUsd.toFixed(2)}</b></div>
    <div class="res-row"><span>Лотов / Единиц</span><b>${units.toFixed(4)}</b></div>
    <div class="res-row"><span>Размер позиции</span><b>$${posSize.toFixed(2)}</b></div>
    <div class="res-row"><span>Направление</span><b>${dir}</b></div>`;
}

// Market sessions
const _SESSIONS = [
  { name: T('sessions.sydney','Сидней'),    open: 21, close: 6,  flag: "🇦🇺" },
  { name: T('sessions.tokyo','Токио'),      open: 0,  close: 9,  flag: "🇯🇵" },
  { name: T('sessions.london','Лондон'),    open: 7,  close: 16, flag: "🇬🇧" },
  { name: T('sessions.newyork','Нью-Йорк'), open: 12, close: 21, flag: "🇺🇸" },
];

function _isOpen(s, utcH) {
  if (s.open < s.close) return utcH >= s.open && utcH < s.close;
  return utcH >= s.open || utcH < s.close;
}

function renderSessionsHTML() {
  const now = new Date();
  const utcH = now.getUTCHours();
  const utcM = now.getUTCMinutes();
  const rows = _SESSIONS.map(s => {
    const open = _isOpen(s, utcH);
    const cls  = open ? "sess-open" : "sess-closed";
    return `<div class="sess-row ${cls}">
      <span>${s.flag} ${s.name}</span>
      <span>${open ? "● " + T('sessions.open_label','Открыта') : "○ " + T('sessions.closed_label','Закрыта')}</span>
      <span class="sess-time">${s.open}:00 – ${s.close}:00 UTC</span>
    </div>`;
  }).join("");
  const utcStr = `${String(utcH).padStart(2,"0")}:${String(utcM).padStart(2,"0")} UTC`;
  return `<div class="tool-widget">
    <div class="widget-title">${T('sessions.widget_title','Сессии')} · ${T('sessions.now_at','сейчас')} ${utcStr}</div>
    <div class="sessions-list">${rows}</div>
    <div class="disclaimer">${T('sessions.disclaimer','Форекс — 24/5. Биржи (NYSE, Nasdaq) — 09:30–16:00 ET (Нью-Йорк).')}</div>
  </div>`;
}

function renderSessions(el) { /* Сессии обновляются при открытии тула */ }

// Glossary — { term, def, etym }. etym необязателен, но если есть — доступен по тапу.
const _GLOSSARY = [
  { term: "ATH", def: "All-Time High — исторический максимум цены актива.",
    etym: "Аббревиатура закрепилась в биржевых сводках как быстрый способ отметить ценовой рекорд." },
  { term: "Bear Market", def: "Падение рынка на 20%+ от недавнего максимума.",
    etym: "По одной из версий — от манеры медведя атаковать лапой сверху вниз, символ падающего рынка." },
  { term: "Bull Market", def: "Рост рынка на 20%+ от недавнего минимума.",
    etym: "Бык бьёт рогами снизу вверх — противоположность медведю, символ роста." },
  { term: "Volatility / VIX", def: "Мера неопределённости цены. VIX — «индекс страха» S&P 500.",
    etym: "VIX ввела биржа CBOE в 1993 году; прозвище «индекс страха» закрепилось после кризисов 2000-х." },
  { term: "Long / Short", def: "Long — ставка на рост. Short — ставка на падение.",
    etym: "Long («длинная позиция») — актив держат в ожидании роста. Short («короткая продажа») — продают взятое в долг, рассчитывая откупить дешевле." },
  { term: "Stop-Loss", def: "Ордер закрытия позиции при достижении убытка.",
    etym: "Дословно «остановить убыток» — термин из ранней электронной торговли США." },
  { term: "Take-Profit", def: "Ордер фиксации прибыли при достижении цели.",
    etym: "Дословно «взять прибыль»." },
  { term: "Leverage / Плечо", def: "Торговля заёмными средствами. Увеличивает и прибыль, и убыток.",
    etym: "От англ. lever — «рычаг»: небольшой капитал двигает крупную позицию, как рычаг — тяжёлый груз." },
  { term: "Liquidity", def: "Насколько легко купить/продать актив без сдвига цены.",
    etym: "От лат. liquidus — «жидкий, текучий»: чем «текучее» рынок, тем легче в нём двигаться." },
  { term: "PCE", def: "Personal Consumption Expenditures — предпочтительный инфляционный индикатор ФРС.",
    etym: "Индекс считает Бюро экономического анализа США (BEA); ФРС выбрала его основным ориентиром по инфляции." },
  { term: "FOMC", def: "Комитет ФРС по открытым рынкам. Устанавливает ставку в США.",
    etym: "Federal Open Market Committee создан в 1933 году после банковских кризисов Великой депрессии." },
  { term: "NFP", def: "Non-Farm Payrolls — отчёт о занятости в США. Выходит каждую первую пятницу месяца.",
    etym: "Отчёт публикует Бюро статистики труда США с 1939 года; «non-farm» исключает сельское хозяйство из-за его сезонности." },
  { term: "Hedge", def: "Позиция, страхующая против риска другой позиции.",
    etym: "От англ. hedge — «живая изгородь»: в смысле «ограждение», защита от риска с другой стороны." },
  { term: "Spread", def: "Разница между ценой покупки (ask) и продажи (bid).",
    etym: "От англ. spread — «разброс, растяжение» между двумя ценами." },
  { term: "Flash Crash", def: "Резкое падение цены за короткое время, часто с последующим восстановлением.",
    etym: "Термин закрепился после обвала рынка США 6 мая 2010 года, длившегося считанные минуты." },

  // Русский трейдерский сленг
  { term: "Лонг", def: "Покупка актива в расчёте на рост цены.",
    etym: "От англ. long position — «длинная позиция»: трейдер «долго» удерживает актив в ожидании роста." },
  { term: "Шорт", def: "Продажа взятого в долг у брокера актива в расчёте на падение цены.",
    etym: "От англ. short sale — «короткая продажа»; термин закрепился на биржах ещё в XIX веке." },
  { term: "Плечо", def: "Торговля на заёмные средства брокера — увеличивает и прибыль, и убыток.",
    etym: "Калька с англ. leverage — «рычаг»: управление большой позицией малым капиталом." },
  { term: "Хомяк", def: "Насмешливое прозвище неопытного розничного трейдера, часто теряющего деньги на эмоциях.",
    etym: "Сленг рунета 2010-х — ассоциация с суетливым и падким на «зерно» (лёгкую наживу) животным." },
  { term: "Кукловод", def: "Крупный игрок или маркетмейкер, чьи действия двигают цену против розничных трейдеров.",
    etym: "От «кукловод» — тот, кто дёргает за ниточки, управляя рынком как марионеткой." },
  { term: "Дно", def: "Минимальная точка падения цены перед разворотом вверх.",
    etym: "Прямой перевод торгового жаргона bottom." },
  { term: "Отскок", def: "Краткосрочный рост цены после резкого падения — не обязательно разворот тренда.",
    etym: "Калька с bounce: цена «отскакивает», как мяч от пола." },
  { term: "Пробой", def: "Выход цены за уровень поддержки или сопротивления.",
    etym: "От англ. breakout — «прорыв»." },
  { term: "Флэт", def: "Боковое движение цены без выраженного тренда.",
    etym: "От англ. flat — «плоский, ровный»." },
  { term: "Слив", def: "Быстрая и болезненная потеря депозита, часто из-за чрезмерного риска или плеча.",
    etym: "Сленг рунета: метафора «слить» — избавиться от чего-то безвозвратно, как воду." },
  { term: "Депозит", def: "Сумма денег на торговом счёте.",
    etym: "От лат. depositum — «отданное на хранение»." },
  { term: "Разворот", def: "Смена направления тренда с восходящего на нисходящий или наоборот.",
    etym: "Калька с англ. reversal." },
  { term: "Дивергенция", def: "Расхождение между движением цены и индикатора — сигнал возможного разворота.",
    etym: "От лат. divergere — «расходиться в разные стороны»." },
];

// _GLOSSARY больше не рендерится как отдельный экран в Инструментах — тот список
// дублировал канонический глоссарий market_intel (lp.sbfconsult.com/glossary),
// на который теперь ведёт вкладка напрямую. Данные здесь остаются только для
// подсветки терминов внутри текста брифинга через _linkConcepts (см. showEtymology).

// ── Etymology popup ─────────────────────────────────────────────────────────
function showEtymology(idx) {
  const g = _GLOSSARY[idx];
  if (!g) return;
  let modal = document.getElementById("etymology-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "etymology-modal";
    modal.className = "modal-overlay";
    modal.onclick = (e) => { if (e.target === modal) closeEtymology(); };
    document.getElementById("app").appendChild(modal);
  }
  modal.innerHTML = `
    <div class="modal-card">
      <div class="modal-close" onclick="closeEtymology()">✕</div>
      <div class="modal-title">${esc(g.term)}</div>
      <div class="modal-def">${esc(g.def)}</div>
      ${g.etym ? `<div class="modal-etym-label">${T('glossary.etymology_label','Этимология')}</div><div class="modal-etym">${esc(g.etym)}</div>` : ""}
    </div>`;
  modal.classList.add("open");
}

function closeEtymology() {
  document.getElementById("etymology-modal")?.classList.remove("open");
}

// ── Streak info popup ───────────────────────────────────────────────────────
function showStreakInfo(streak) {
  let modal = document.getElementById("streak-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "streak-modal";
    modal.className = "modal-overlay";
    modal.onclick = (e) => { if (e.target === modal) closeStreakInfo(); };
    document.getElementById("app").appendChild(modal);
  }
  modal.innerHTML = `
    <div class="modal-card">
      <div class="modal-close" onclick="closeStreakInfo()">✕</div>
      <div class="modal-title">🔥 ${T('streak.title_word','Серия')} ${streak} ${_streakDayWord(streak)}</div>
      <div class="modal-def">${T('streak.description','Столько дней подряд вы открываете обзор рынка. Пропустите день — счётчик обнулится и начнётся заново.')}</div>
    </div>`;
  modal.classList.add("open");
}

function closeStreakInfo() {
  document.getElementById("streak-modal")?.classList.remove("open");
}

function _streakDayWord(n) {
  // Румынский не различает "1 день / 2-4 дня / 5+ дней" как русский — просто
  // ед./мн. число (day_one/day_few в словаре для 'ro' оба хранят "zile" для
  // не-1, см. i18n.js). Правило склонения для русского оставлено как было.
  if (window.sbfI18n.lang === "ro") {
    return n === 1 ? T('streak.day_one','день') : T('streak.day_few','дня');
  }
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return T('streak.day_one','день');
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return T('streak.day_few','дня');
  return T('streak.day_many','дней');
}

// ── PROFILE ───────────────────────────────────────────────────────────────────
function buildProfile(el) {
  el.innerHTML = `<div class="profile-header"><h2>${T('nav.profile','Профиль')}</h2></div>
    <div id="prof-body"><div class="center-spin"><div class="spinner"></div></div></div>`;
  loadProfile(el);
}

// Переключатель языка интерфейса — ручной оверрайд поверх автоопределения по
// Telegram language_code (см. i18n.js). setLang() пишет sbf_lang в localStorage
// и перезагружает страницу — язык фиксируется на старте приложения, живого
// перерендера без reload не делаем (проще и надёжнее для SPA без фреймворка).
function _renderLangSwitcher() {
  const cur = window.sbfI18n.lang;
  return `
    <div class="profile-section">
      <div class="widget-title" style="margin-bottom:6px">${T('profile.language_label','Язык интерфейса')}</div>
      <div class="cat-bar">
        <button class="cat-btn ${cur === "ru" ? "active" : ""}" onclick="window.sbfI18n.setLang('ru')">RU</button>
        <button class="cat-btn ${cur === "ro" ? "active" : ""}" onclick="window.sbfI18n.setLang('ro')">RO</button>
      </div>
    </div>`;
}

async function loadProfile(el) {
  const body = el.querySelector("#prof-body");
  try {
    const r = await api("/api/me");
    if (!r.ok) throw new Error(r.status);
    const u = await r.json();

    // Full IANA timezone list via browser API
    const zones = Intl.supportedValuesOf
      ? Intl.supportedValuesOf("timeZone")
      : ["Asia/Almaty","Africa/Johannesburg","Europe/Moscow","UTC","Europe/London","America/New_York","America/Los_Angeles","Asia/Singapore","Asia/Dubai"];
    const defaultTz = u.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

    const PROVIDERS = [
      { id: "email",    label: "Email",    icon: "✉️" },
      { id: "telegram", label: "Telegram", icon: "✈️" },
      { id: "google",   label: "Google",   icon: "G" },
    ];
    const linkedSet = new Set(u.linked_providers || []);
    const providersHtml = PROVIDERS.map(p => {
      const linked = linkedSet.has(p.id);
      return `<div class="prof-provider-row">
        <span class="prof-provider-lbl">${p.icon} ${p.label}${linked ? ' <span class="prof-provider-linked">✓</span>' : ""}</span>
        <button class="btn btn-ghost btn-sm" onclick="${linked ? `unlinkProvider('${p.id}')` : `linkProvider('${p.id}')`}">${linked ? T('profile.unlink_btn','Отвязать') : T('profile.link_btn','Привязать')}</button>
      </div>`;
    }).join("");

    body.innerHTML = `
      <div class="profile-section">
        <div class="prof-row"><span class="prof-lbl">Email</span><span class="prof-val">${esc(u.email || "—")}</span></div>
      </div>
      ${_renderLangSwitcher()}
      <div class="profile-section">
        <div class="widget-title" style="margin-bottom:6px">${T('profile.login_methods_title','Способы входа')}</div>
        ${providersHtml}
      </div>
      <div class="profile-section">
        <div class="prof-field-group">
          <div class="prof-row prof-row-plain">
            <span class="prof-lbl">${T('profile.review_time_label','Время обзора')}</span>
            <input type="time" id="p-time" value="${esc(u.delivery_time || "09:00")}" onchange="saveProfile('delivery_time', this.value)">
          </div>
          <div class="prof-hint">${T('profile.review_time_hint','Во сколько пришлёт push-уведомление в Telegram. Бейдж «06:00» внутри самого отчёта — это время его генерации, к уведомлению отношения не имеет')}</div>
        </div>
        <div class="prof-field-group">
          <div class="prof-row prof-row-plain">
            <span class="prof-lbl">${T('profile.timezone_label','Часовой пояс')}</span>
            <select id="tz-select" onchange="saveProfile('timezone', this.value)"></select>
          </div>
          <div class="prof-hint">${T('profile.timezone_hint','Время обзора выше считается по этому часовому поясу')}</div>
        </div>
      </div>
      <div class="profile-section">
        <div class="prof-row">
          <span class="prof-lbl">${T('profile.accompaniment_label','Сопровождение счёта')}</span>
          <label class="toggle">
            <input type="checkbox" id="p-acc" ${u.accompaniment_interest ? "checked" : ""}
              onchange="saveProfile('accompaniment_interest', this.checked)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="prof-hint">${T('profile.accompaniment_hint','Сохраняет заинтересованность в персональном сопровождении счёта и открывает контакт менеджера ниже — чтобы вам ответили, напишите ему в Telegram напрямую')}</div>
        <div id="acc-cta" class="${u.accompaniment_interest ? "" : "hidden"}" style="padding:8px 0">
          <a class="btn" style="font-size:13px;padding:10px" href="https://t.me/SBF_Support" target="_blank">${T('profile.contact_manager_btn','Написать менеджеру в Telegram')}</a>
        </div>
      </div>
      <div class="profile-section">
        <button class="btn btn-ghost" onclick="doLogout()">${T('profile.logout_btn','Выйти')}</button>
      </div>`;

    // IANA timezone <select> — раньше был текстовый инпут с автокомплитом,
    // выглядел как поле, в которое можно вписать что угодно (и технически можно
    // было, просто несохранённое). Нативный select и есть выбор, без иллюзии свободного ввода.
    const tzSelect = document.getElementById("tz-select");
    tzSelect.innerHTML = zones.map(z =>
      `<option value="${esc(z)}"${z === defaultTz ? " selected" : ""}>${esc(z)}</option>`).join("");

    document.getElementById("p-acc").addEventListener("change", function() {
      document.getElementById("acc-cta").classList.toggle("hidden", !this.checked);
    });

  } catch { body.innerHTML = `<div class="empty-state">${T('profile.load_error','Ошибка загрузки профиля')}</div>`; }
}

// ── Link / unlink login methods ────────────────────────────────────────────────
function _ensureLinkModal() {
  let modal = document.getElementById("link-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "link-modal";
    modal.className = "modal-overlay";
    modal.onclick = (e) => { if (e.target === modal) closeLinkModal(); };
    document.getElementById("app").appendChild(modal);
  }
  return modal;
}

function closeLinkModal() {
  document.getElementById("link-modal")?.classList.remove("open");
}

function _refreshProfile() {
  if (_screens["profile"]) buildProfile(_screens["profile"]);
}

function linkProvider(id) {
  const modal = _ensureLinkModal();
  if (id === "email") {
    modal.innerHTML = `
      <div class="modal-card">
        <div class="modal-close" onclick="closeLinkModal()">✕</div>
        <div class="modal-title">${T('profile.link_email_title','Привязать email')}</div>
        <form onsubmit="return submitLinkEmail(event)">
          <input type="email" id="link-email" placeholder="Email" required
            style="width:100%;padding:12px;margin-bottom:8px;border:1px solid var(--border);border-radius:8px;font-size:14px;box-sizing:border-box">
          <input type="password" id="link-password" placeholder="${T('profile.link_password_placeholder','Пароль (мин. 8 символов)')}" required minlength="8"
            style="width:100%;padding:12px;margin-bottom:10px;border:1px solid var(--border);border-radius:8px;font-size:14px;box-sizing:border-box">
          <div id="link-error" style="color:#C0392B;font-size:13px;margin-bottom:8px;display:none"></div>
          <button type="submit" class="btn">${T('profile.link_btn','Привязать')}</button>
        </form>
      </div>`;
  } else if (id === "telegram") {
    // Виджет здесь больше не рендерим — тот же домен-конфликт, что и в
    // showLogin() (BotFather держит только ОДИН домен разом, сейчас это
    // lp.sbfconsult.com). Внутри самой Mini App это и не нужно: войдя через
    // Telegram, аккаунт уже резолвится по Telegram identity.
    modal.innerHTML = `
      <div class="modal-card">
        <div class="modal-close" onclick="closeLinkModal()">✕</div>
        <div class="modal-title">${T('profile.link_telegram_title','Привязать Telegram')}</div>
        <div class="modal-def">${T('profile.link_telegram_desc','Открыв это приложение через Telegram, вы уже входите под своим Telegram-аккаунтом. Привязать отдельный Telegram-аккаунт можно на <a href="https://lp.sbfconsult.com/login.html" target="_blank">lp.sbfconsult.com</a>.')}</div>
      </div>`;
  } else if (id === "google") {
    if (isTMA()) {
      // Google блокирует свою форму входа внутри встроенных WebView (в т.ч.
      // Telegram Mini Apps) — показывает пустой экран вместо формы. Поэтому
      // здесь не рисуем кнопку GSI, а открываем OAuth в системном браузере
      // телефона; результат прилетает на сервер напрямую с callback-страницы,
      // а не через JS этой вкладки — поэтому просто просим вернуться и обновить.
      modal.innerHTML = `
        <div class="modal-card">
          <div class="modal-close" onclick="closeLinkModal()">✕</div>
          <div class="modal-title">${T('profile.link_google_title','Привязать Google')}</div>
          <div class="modal-def" id="google-tma-status">${T('profile.google_opening_browser','Открываем Google в браузере телефона…')}</div>
        </div>`;
      modal.classList.add("open");
      _startGoogleLinkViaBrowser();
      return;
    }
    modal.innerHTML = `
      <div class="modal-card">
        <div class="modal-close" onclick="closeLinkModal()">✕</div>
        <div class="modal-title">${T('profile.link_google_title','Привязать Google')}</div>
        <div id="link-google-btn" style="display:flex;justify-content:center;margin-top:6px"></div>
      </div>`;
    _renderGoogleButton(document.getElementById("link-google-btn"), "onGoogleLinkCredential");
  } else return;
  modal.classList.add("open");
}

async function submitLinkEmail(e) {
  e.preventDefault();
  const email = document.getElementById("link-email").value.trim();
  const password = document.getElementById("link-password").value;
  const errEl = document.getElementById("link-error");
  try {
    const r = await api("/api/auth/link/email", { method: "POST", body: JSON.stringify({ email, password }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('profile.link_email_error','Не удалось привязать email'));
    closeLinkModal();
    _refreshProfile();
  } catch (err) {
    errEl.textContent = err.message || T('profile.link_email_error','Не удалось привязать email');
    errEl.style.display = "block";
  }
  return false;
}

async function onGoogleLinkCredential(response) {
  try {
    const r = await api("/api/auth/link/google", { method: "POST", body: JSON.stringify({ credential: response.credential }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('profile.link_google_error','Не удалось привязать Google'));
    closeLinkModal();
    _refreshProfile();
  } catch (err) {
    alert(err.message || T('profile.link_google_error','Не удалось привязать Google'));
  }
}
window.onGoogleLinkCredential = onGoogleLinkCredential;

async function _startGoogleLinkViaBrowser() {
  const statusEl = document.getElementById("google-tma-status");
  try {
    const r = await api("/api/auth/google/link-start", { method: "POST" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.oauth_url) throw new Error(d.detail || T('profile.google_start_error','Не удалось начать вход через Google'));
    if (window.Telegram?.WebApp?.openLink) window.Telegram.WebApp.openLink(d.oauth_url);
    else window.open(d.oauth_url, "_blank");
    if (statusEl) statusEl.textContent = T('profile.google_browser_instructions','Завершите вход в открывшемся браузере, затем вернитесь в Telegram — эта вкладка обновится сама.');
    // При возврате в Mini App (свернули браузер / переключились обратно) —
    // тихо перепроверяем /api/me и перерисовываем профиль, если привязка удалась.
    const onBack = () => {
      if (document.visibilityState !== "visible") return;
      document.removeEventListener("visibilitychange", onBack);
      closeLinkModal();
      _refreshProfile();
    };
    document.addEventListener("visibilitychange", onBack);
  } catch (err) {
    if (statusEl) statusEl.textContent = err.message || T('profile.google_start_error','Не удалось начать вход через Google');
  }
}

async function unlinkProvider(id) {
  if (!confirm(T('profile.unlink_confirm','Отвязать этот способ входа?'))) return;
  try {
    const r = await api("/api/auth/link/" + id, { method: "DELETE" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || T('profile.unlink_error','Не удалось отвязать'));
    _refreshProfile();
  } catch (err) {
    alert(err.message || T('profile.unlink_error','Не удалось отвязать'));
  }
}

async function saveProfile(field, value) {
  await api("/api/profile", { method: "PUT", body: JSON.stringify({ [field]: value }) });
}

async function doLogout() { tok.clear(); location.reload(); }

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ── Hardware back button (Android/iOS APK) ─────────────────────────────────────
// В Telegram и на web этим управляет сам браузер/Telegram. В нативной
// Capacitor-обёртке без явного обработчика системная кнопка «Назад» либо ничего
// не делает, либо сразу закрывает приложение — независимо от того, что открыто.
function handleHardwareBack() {
  const modal = document.getElementById("etymology-modal");
  if (modal && modal.classList.contains("open")) { closeEtymology(); return; }
  const linkModal = document.getElementById("link-modal");
  if (linkModal && linkModal.classList.contains("open")) { closeLinkModal(); return; }
  const streakModal = document.getElementById("streak-modal");
  if (streakModal && streakModal.classList.contains("open")) { closeStreakInfo(); return; }
  const openDrop = document.querySelector(".tool-drop.open");
  if (openDrop) {
    toggleTool(openDrop.id.replace("tool-drop-", ""));
    return;
  }
  const active = document.querySelector(".screen.active");
  if (active && active.id !== "screen-today") {
    showScreen("today");
    return;
  }
  if (window.Capacitor?.Plugins?.App) window.Capacitor.Plugins.App.exitApp();
}

if (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) {
  window.Capacitor?.Plugins?.App?.addListener("backButton", handleHardwareBack);
}

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", boot);
