TEXTS = {
    "ru": {
        # Start
        "choose_lang":    "🌍 Выбери язык / Choose language:",
        "welcome":        "👋 Привет!\n\nЭто бот для хозяев вилл на Бали 🌴\n\n🔑 Введи инвайт-код для доступа:",
        "wrong_code":     "❌ Неверный код. Попробуй ещё раз:",
        "code_used":      "❌ Этот код уже использован.",
        "code_expired":   "❌ Срок действия кода истёк.",
        "welcome_name":   "✅ Добро пожаловать, {}!\n\nТеперь у тебя есть доступ к боту 🎉",

        # Menu
        "menu_title":     "🌴 Панель хозяина\n\nПривет, {}!\nЧто хочешь сделать?",
        "btn_add_villa":  "🏠 Добавить виллу",
        "btn_my_villas":  "📋 Мои виллы",
        "btn_stats":      "📊 Статистика броней",

        # Виллы
        "no_villas":      "🏠 У тебя пока нет вилл.\n\nНажми *🏠 Добавить виллу*!",
        "my_villas":      "🏠 *Мои виллы* ({}):\n\n✅ — опубликована\n❌ — скрыта\n\nВыбери виллу:",
        "not_authorized": "❌ Ты не авторизован!",
    },
    "en": {
        # Start
        "choose_lang":    "🌍 Выбери язык / Choose language:",
        "welcome":        "👋 Hello!\n\nThis is a bot for Bali villa owners 🌴\n\n🔑 Enter your invite code:",
        "wrong_code":     "❌ Wrong code. Try again:",
        "code_used":      "❌ This code has already been used.",
        "code_expired":   "❌ The code has expired.",
        "welcome_name":   "✅ Welcome, {}!\n\nYou now have access to the bot 🎉",

        # Menu
        "menu_title":     "🌴 Owner Panel\n\nHello, {}!\nWhat would you like to do?",
        "btn_add_villa":  "🏠 Add villa",
        "btn_my_villas":  "📋 My villas",
        "btn_stats":      "📊 Booking stats",

        # Villas
        "no_villas":      "🏠 You don't have any villas yet.\n\nPress *🏠 Add villa*!",
        "my_villas":      "🏠 *My villas* ({}):\n\n✅ — published\n❌ — hidden\n\nChoose a villa:",
        "not_authorized": "❌ You are not authorized!",
    }
}

def get(key: str, lang: str, *args) -> str:
    """Получить текст по ключу и языку"""
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, TEXTS["ru"].get(key, key))
    if args:
        return text.format(*args)
    return text