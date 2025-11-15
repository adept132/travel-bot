import asyncio
import re
from datetime import datetime, timedelta
from typing import List
from venv import logger

import requests
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import func
from bot.config import mail

from app.travel_database import User, Entry, Travel, Achievement, Media
from app.travel_session import Session


def validate_country(country: str) -> bool:
    if not country or len(country.strip()) == 0:
        return False
    if len(country) > 50:
        return False
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\-\'\.]+$', country):
        return False
    return True


def validate_city(city: str) -> bool:
    if not city or len(city.strip()) == 0:
        return False
    if len(city) > 50:
        return False
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\-\'\.]+$', city):
        return False
    return True


def validate_place_title(title: str) -> bool:
    if not title or len(title.strip()) == 0:
        return False
    if len(title) > 100:
        return False
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\'\.\,\!\(\)\#\&]+$', title):
        return False
    return True


def validate_comment(comment: str) -> bool:
    if comment == "-":
        return True
    if len(comment) > 500:
        return False
    if re.search(r'[<>{}\[\]]', comment):
        return False
    return True


def validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        date = datetime.strptime(date_str, "%d.%m.%Y")
        if date > datetime.now():
            return False
        return True
    except ValueError:
        return False


def validate_rating(rating_str: str) -> bool:
    try:
        rating = int(rating_str)
        return 1 <= rating <= 10
    except ValueError:
        return False

def validate_date_within_travel(visit_date: datetime, travel_start: datetime, travel_end: datetime) -> bool:
    return travel_start <= visit_date <= travel_end

def user_has_premium(tg_id: int) -> bool:
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=tg_id).first()
        if user and user.premium:
            return True
        return False
    finally:
        session.close()

def can_add_media(tg_id: int, place_id: int) -> bool:
    session = Session()
    try:
        user = session.query(User).filter_by(tg_id=tg_id).first()
        media_count = session.query(Media).filter_by(place_id=place_id).count()
        limit = 8 if user.premium else 3
        return media_count < limit
    finally:
        session.close()


def date_difference(start_date, end_date):
    try:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
        if isinstance(start_date, datetime) and isinstance(end_date, datetime):
            return (end_date - start_date).days
        else:
            return 0
    except Exception as e:
        print(f"❌ Ошибка вычисления длительности: {e}")
        return 0

def check_achievements(user, session):
    new_achievements = []

    try:
        finished_travels = session.query(Travel).filter(
            Travel.user_id == user.user_id,
            Travel.end_date != None
        ).count()

        places_count = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id
        ).count()

        photos_count = session.query(Media).join(Entry).join(Travel).filter(
            Travel.user_id == user.user_id,
            Media.media_type == 'photo'
        ).count()

        travels_with_dates = session.query(Travel).filter(
            Travel.user_id == user.user_id,
            Travel.end_date != None,
            Travel.start_date != None
        ).all()

        has_long_trip_7 = False
        has_long_trip_30 = False

        for travel in travels_with_dates:
            # ИСПОЛЬЗУЕМ БЕЗОПАСНУЮ ФУНКЦИЮ
            duration = date_difference(travel.start_date, travel.end_date)
            if duration >= 30:
                has_long_trip_30 = True
                has_long_trip_7 = True
            elif duration >= 7:
                has_long_trip_7 = True

        has_10_rating = session.query(Entry).join(Travel).filter(
            Travel.user_id == user.user_id,
            Entry.place_rating == 10
        ).first() is not None

        countries_count = session.query(func.distinct(Travel.country)).filter(
            Travel.user_id == user.user_id
        ).count()

        achievement_conditions = [
            ("FIRST_TRAVEL", "🎯 Первый шаг", "Завершите свое первое путешествие", finished_travels >= 1),
            ("TRAVELER_5", "🧳 Начинающий турист", "Завершите 5 путешествий", finished_travels >= 5),
            ("TRAVELER_10", "🌍 Опытный путешественник", "Завершите 10 путешествий", finished_travels >= 10),
            ("TRAVELER_25", "🏆 Мастер путешествий", "Завершите 25 путешествий", finished_travels >= 25),
            ("TRAVELER_50", "👑 Легенда дорог", "Завершите 50 путешествий", finished_travels >= 50),

            ("PLACE_1", "📍 Первое место", "Добавьте свое первое место", places_count >= 1),
            ("PLACE_10", "🔭 Полевой исследователь", "Посетите 10 мест", places_count >= 10),
            ("PLACE_25", "🗿 Искатель достопримечательностей", "Посетите 25 мест", places_count >= 25),
            ("PLACE_50", "🗺️ Искатель приключений", "Посетите 50 мест", places_count >= 50),
            ("PLACE_100", "🌎 Гражданин мира", "Посетите 100 мест", places_count >= 100),

            ("PHOTO_10", "📸 Фотограф-любитель", "Добавьте 10 фотографий", photos_count >= 10),
            ("PHOTO_50", "📷 Профессиональный фотограф", "Добавьте 50 фотографий", photos_count >= 50),
            ("PHOTO_100", "🎨 Художник света", "Добавьте 100 фотографий", photos_count >= 100),

            ("LONG_TRIP_7", "⏳ Неделя в пути", "Совершите путешествие длительностью 7+ дней", has_long_trip_7),
            ("LONG_TRIP_30", "📅 Месяц странствий", "Совершите путешествие длительностью 30+ дней", has_long_trip_30),

            ("RATING_10", "⭐ Перфекционист", "Поставьте оценку 10 какому-либо месту", has_10_rating),
            ("MULTI_COUNTRY", "🚩 Коллекционер стран", "Посетите 5 разных стран", countries_count >= 5),
            ("PREMIUM_USER", "💎 Премиум статус", "Активируйте премиум подписку", user.premium),
        ]

        for code, title, desc, achieved in achievement_conditions:
            if achieved:
                exists = session.query(Achievement).filter_by(user_id=user.user_id, code=code).first()
                if not exists:
                    print(f"🎉 Новое достижение: {title}")
                    ach = Achievement(
                        user_id=user.user_id,
                        code=code,
                        achievement_name=title,
                        description=desc
                    )
                    session.add(ach)
                    new_achievements.append(ach)
        return new_achievements

    except Exception as e:
        print(f"❌ Error in check_achievements: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_progress_bar(percentage: int, length: int = 10) -> str:
    filled = int(length * percentage / 100)
    empty = length - filled
    return "█" * filled + "░" * empty


async def send_progress_message(bot, chat_id: int, operation: str, percentage: int) -> Message:
    progress_bar = create_progress_bar(percentage)
    text = (
        f"⏳ <b>{operation}</b>\n\n"
        f"{progress_bar} {percentage}%\n\n"
        f"<i>Пожалуйста, подождите...</i>"
    )
    return await bot.send_message(chat_id, text, parse_mode="HTML")


async def simulate_progress(bot, chat_id: int, operation: str, steps: List[str], delays: List[float]):
    total_steps = len(steps)

    for i, (step, delay) in enumerate(zip(steps, delays)):
        percentage = int((i + 1) * 100 / total_steps)
        await send_progress_message(bot, chat_id, operation, percentage)

        progress_bar = create_progress_bar(percentage)
        text = (
            f"⏳ <b>{operation}</b>\n\n"
            f"{progress_bar} {percentage}%\n\n"
            f"<b>Текущий шаг:</b> {step}\n"
            f"<i>Пожалуйста, подождите...</i>"
        )
        await asyncio.sleep(delay)

    progress_bar = create_progress_bar(100)
    completion_text = (
        f"✅ <b>{operation} завершено!</b>\n\n"
        f"{progress_bar} 100%\n\n"
        f"<i>Операция успешно выполнена</i> 🎉"
    )
    await bot.send_message(chat_id, completion_text, parse_mode="HTML")


class ProgressManager:
    def __init__(self):
        self.progress_messages = {}

    async def start_progress(self, bot, chat_id: int, operation: str, message: Message = None) -> int:
        """Начинает прогресс и возвращает message_id"""
        try:
            progress_bar = "░" * 10
            text = (
                f"⏳ <b>{operation}</b>\n\n"
                f"{progress_bar} 0%\n\n"
                f"<i>Подготовка к работе...</i>"
            )

            if message and hasattr(message, 'message_id'):
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    text=text,
                    parse_mode="HTML"
                )
                message_id = message.message_id
            else:
                sent_message = await bot.send_message(chat_id, text, parse_mode="HTML")
                message_id = sent_message.message_id

            self.progress_messages[chat_id] = message_id
            return message_id

        except Exception as e:
            print(f"❌ Ошибка старта прогресса: {e}")
            sent_message = await bot.send_message(chat_id, text, parse_mode="HTML")
            return sent_message.message_id

    async def update_progress(self, bot, chat_id: int, operation: str, percentage: int, step: str = ""):
        """Обновляет прогресс-бар"""
        try:
            if chat_id not in self.progress_messages:
                return

            filled = max(0, min(10, int(10 * percentage / 100)))
            empty = 10 - filled
            progress_bar = "█" * filled + "░" * empty

            text = (
                f"⏳ <b>{operation}</b>\n\n"
                f"{progress_bar} {percentage}%\n"
            )

            if step:
                text += f"\n<b>Текущий шаг:</b> {step}\n"

            text += "\n<i>Пожалуйста, подождите...</i>"

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=self.progress_messages[chat_id],
                text=text,
                parse_mode="HTML"
            )

        except Exception as e:
            print(f"❌ Ошибка обновления прогресса: {e}")

    async def complete_progress(self, bot, chat_id: int, operation: str, success: bool = True, result_text: str = ""):
        """Завершает прогресс"""
        try:
            if chat_id not in self.progress_messages:
                return

            progress_bar = "█" * 10

            if success:
                text = (
                    f"✅ <b>{operation} завершено!</b>\n\n"
                    f"{progress_bar} 100%\n\n"
                )
                if result_text:
                    text += f"{result_text}\n\n"
                text += "<i>Операция успешно выполнена</i> 🎉"
            else:
                text = (
                    f"❌ <b>{operation} прервано</b>\n\n"
                    f"{progress_bar} 100%\n\n"
                    f"<i>Произошла ошибка при выполнении</i>"
                )

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=self.progress_messages[chat_id],
                text=text,
                parse_mode="HTML"
            )

            # Удаляем сообщение из отслеживания после завершения
            if chat_id in self.progress_messages:
                del self.progress_messages[chat_id]

        except Exception as e:
            print(f"❌ Ошибка завершения прогресса: {e}")
            if success:
                await bot.send_message(chat_id, f"✅ {operation} завершено! 🎉", parse_mode="HTML")
            else:
                await bot.send_message(chat_id, f"❌ {operation} прервано", parse_mode="HTML")


class RateLimiter:
    def __init__(self):
        self.requests = {}
        # Дефолтные лимиты для разных категорий
        self.default_limits = {
            "default": {"max_requests": 10, "time_window": 60},
            "heatmap": {"max_requests": 3, "time_window": 300},
            "media_upload": {"max_requests": 10, "time_window": 120},
            "stats": {"max_requests": 5, "time_window": 60},
            "export": {"max_requests": 1, "time_window": 300},
            "geocoding_api": {"max_requests": 50, "time_window": 60},
        }

    def is_allowed(self, user_id: int, category: str = "default", max_requests: int = None,
                   window_seconds: int = None) -> bool:
        if max_requests is None or window_seconds is None:
            category_limits = self.default_limits.get(category, self.default_limits["default"])
            max_requests = category_limits["max_requests"]
            window_seconds = category_limits["time_window"]

        now = datetime.now()
        key = f"{user_id}:{category}"

        if key not in self.requests:
            self.requests[key] = []

        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < timedelta(seconds=window_seconds)
        ]

        if len(self.requests[key]) >= max_requests:
            return False

        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()
export_limiter = rate_limiter

progress_manager = ProgressManager()

def translate_text(text, target_lang='en'):
    try:
        url = "https://libretranslate.com/translate"
        data = {
            "q": text,
            "source": "auto",
            "target": target_lang,
            "format": "text"
        }
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get('translatedText', text)
        else:
            print(f"❌ LibreTranslate error: {response.status_code}")
            return text

    except Exception as e:
        print(f"❌ Translation failed: {e}")
        return text


def translate_text_safe(text, target_lang='en'):
    if not text or text.strip() == "":
        return text
    try:
        return translate_text(text, target_lang)
    except:
        return text


def has_cyrillic(text):
    return bool(re.search('[а-яА-Я]', text)) if text else False

def try_nominatim(query):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "accept-language": "ru,en"
        }
        headers = {
            "User-Agent": f"TravelBot/1.0 ({mail})",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
        }

        print(f"🔍 Nominatim запрос: {query}")
        response = requests.get(url, params=params, headers=headers, timeout=20)

        if response.status_code == 200:
            data = response.json()
            if data:
                result = data[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                display_name = result.get('display_name', 'N/A')[:100]
                print(f"✅ Найдено: {lat}, {lon} -> {display_name}")
                return lat, lon
            else:
                print(f"❌ Nominatim: нет результатов для '{query}'")
                return None, None
        else:
            print(f"❌ Nominatim error {response.status_code}: {response.text[:200]}")
            return None, None

    except requests.exceptions.Timeout:
        print(f"❌ Nominatim timeout для '{query}'")
        return None, None
    except Exception as e:
        print(f"❌ Nominatim failed для '{query}': {e}")
        return None, None


def geocode_place(query):
    if not query or query.strip() == "":
        return None, None

    lat, lon = try_nominatim(query)
    if lat and lon:
        return lat, lon

    return None, None

def geocoding(country, city, place_title):
    if not rate_limiter.is_allowed("geocoding_api", "geocoding_api"):
        logger.warning("Geocoding API rate limit exceeded")
        return None, None

    print(f"🎯 Геокодируем: {country}, {city}, {place_title}")

    queries = []
    if country and city and place_title:
        queries.extend([
            f"{country}, {city}, {place_title}",
            f"{city}, {country}, {place_title}",
            f"{place_title}, {city}, {country}",
        ])
    if city and place_title:
        queries.extend([
            f"{city}, {place_title}",
            f"{place_title}, {city}",
        ])
    if place_title:
        queries.append(place_title)
    if has_cyrillic(place_title) or has_cyrillic(city):
        place_en = translate_text_safe(place_title)
        city_en = translate_text_safe(city)
        country_en = translate_text_safe(country)

        if place_en != place_title:
            queries.extend([
                f"{country_en}, {city_en}, {place_en}",
                f"{city_en}, {place_en}",
                place_en
            ])
    for query in queries:
        if not query or query.strip() == "":
            continue

        lat, lon = try_nominatim(query)
        if lat and lon:
            return lat, lon

    return None, None

async def save_place_with_coordinates(msg: Message, state: FSMContext, lat: float, lon: float):
    data = await state.get_data()
    session = Session()
    try:
        entry = Entry(
            travel_id=data["travel_id"],
            city=data["city"],
            place_title=data["place_title"],
            place_comment=None if data.get("place_comment") == "-" else data.get("place_comment"),
            date=datetime.strptime(data["visitation_date"], "%d.%m.%Y"),
            latitude=lat,
            longitude=lon
        )

        user = session.query(User).filter_by(tg_id=msg.from_user.id).first()
        session.add(entry)
        session.commit()
        await state.update_data(place_id=entry.place_id)

        new_achievements = check_achievements(user, session)
        session.commit()

        for ach in new_achievements:
            await msg.answer(
                f'🏆 <b>Новое достижение!</b>\n\n<b>{ach.achievement_name}</b>\n{ach.description}',
                parse_mode='HTML'
            )

    except Exception as e:
        print(f"❌ Ошибка сохранения места: {e}")
        await progress_manager.complete_progress(
            msg.bot,
            msg.from_user.id,
            "Определение координат",
            False
        )
        await msg.answer("❌ Ошибка при сохранении места")
        return
    finally:
        session.close()

CONTINENTS = {
    'europe': {
        'name': '🇪🇺 Европа',
        'countries': [
            'россия', 'украина', 'беларусь', 'польша', 'германия', 'франция', 'италия', 'испания',
            'великобритания', 'нидерланды', 'бельгия', 'швейцария', 'австрия', 'чехия', 'словакия',
            'венгрия', 'румыния', 'болгария', 'греция', 'швеция', 'норвегия', 'финляндия', 'дания',
            'португалия', 'ирландия', 'хорватия', 'сербия', 'босния', 'албания', 'словения', 'литва',
            'латвия', 'эстония', 'молдова', 'македония', 'черногория', 'люксембург', 'мальта', 'исландия',
            'кипр', 'андорра', 'монако', 'сан-марино', 'лихтенштейн', 'ватикан',
            # Английские названия
            'russia', 'ukraine', 'belarus', 'poland', 'germany', 'france', 'italy', 'spain',
            'united kingdom', 'netherlands', 'belgium', 'switzerland', 'austria', 'czech republic', 'slovakia',
            'hungary', 'romania', 'bulgaria', 'greece', 'sweden', 'norway', 'finland', 'denmark',
            'portugal', 'ireland', 'croatia', 'serbia', 'bosnia', 'albania', 'slovenia', 'lithuania',
            'latvia', 'estonia', 'moldova', 'macedonia', 'montenegro', 'luxembourg', 'malta', 'iceland',
            'cyprus', 'andorra', 'monaco', 'san marino', 'liechtenstein', 'vatican'
        ]
    },
    'asia': {
        'name': '🌏 Азия',
        'countries': [
            'китай', 'япония', 'корея', 'индия', 'пакистан', 'бангладеш', 'индонезия', 'филиппины',
            'вьетнам', 'таиланд', 'мьянма', 'малайзия', 'казахстан', 'узбекистан', 'туркменистан',
            'кыргызстан', 'таджикистан', 'афганистан', 'иран', 'ирак', 'саудовская аравия', 'оаэ',
            'катар', 'оман', 'кувейт', 'бахрейн', 'турция', 'сирия', 'ливан', 'иордания', 'израиль',
            'палестина', 'йемен', 'шри-ланка', 'непал', 'бутан', 'мальдивы', 'монголия', 'тайвань',
            'гонконг', 'макао', 'сингапур', 'бруней', 'восточный тимор',
            # Английские названия
            'china', 'japan', 'south korea', 'north korea', 'india', 'pakistan', 'bangladesh',
            'indonesia', 'philippines', 'vietnam', 'thailand', 'myanmar', 'malaysia', 'kazakhstan',
            'uzbekistan', 'turkmenistan', 'kyrgyzstan', 'tajikistan', 'afghanistan', 'iran', 'iraq',
            'saudi arabia', 'united arab emirates', 'qatar', 'oman', 'kuwait', 'bahrain', 'turkey',
            'syria', 'lebanon', 'jordan', 'israel', 'palestine', 'yemen', 'sri lanka', 'nepal',
            'bhutan', 'maldives', 'mongolia', 'taiwan', 'hong kong', 'macao', 'singapore', 'brunei',
            'east timor'
        ]
    },
    'america': {
        'name': '🌎 Америка',
        'countries': [
            'сша', 'канада', 'мексика', 'бразилия', 'аргентина', 'колумбия', 'перу', 'венесуэла',
            'чили', 'эквадор', 'гватемала', 'куба', 'боливия', 'доминикана', 'гондурас', 'парагвай',
            'сальвадор', 'никарагуа', 'коста-рика', 'панама', 'уругвай', 'ямайка', 'тринидад', 'тобаго',
            'гайана', 'суринам', 'багамы', 'барбадос', 'сент-люсия', 'гренада', 'антигуа', 'барбуда',
            'доминика', 'сент-винсент', 'гренадины', 'сент-китс', 'невис', 'белиз', 'гаити',
            # Английские названия
            'usa', 'united states', 'canada', 'mexico', 'brazil', 'argentina', 'colombia', 'peru',
            'venezuela', 'chile', 'ecuador', 'guatemala', 'cuba', 'bolivia', 'dominican republic',
            'honduras', 'paraguay', 'el salvador', 'nicaragua', 'costa rica', 'panama', 'uruguay',
            'jamaica', 'trinidad', 'tobago', 'guyana', 'suriname', 'bahamas', 'barbados', 'saint lucia',
            'grenada', 'antigua', 'barbuda', 'dominica', 'saint vincent', 'grenadines', 'saint kitts',
            'nevis', 'belize', 'haiti'
        ]
    },
    'africa': {
        'name': '🌍 Африка',
        'countries': [
            'египет', 'юар', 'нигерия', 'эфиопия', 'кения', 'танзания', 'алжир', 'марокко', 'ангола',
            'гана', 'конго', 'судан', 'уганда', 'мозамбик', 'кот-д\'ивуар', 'мадагаскар', 'камерун',
            'нигер', 'мали', 'буркина-фасо', 'малави', 'замбия', 'сенегал', 'чад', 'сомали', 'зимбабве',
            'гвинея', 'руанда', 'бенин', 'бурунди', 'тунис', 'южный судан', 'того', 'ливия', 'либерия',
            'цар', 'мавритания', 'эритрея', 'намибия', 'гамбия', 'ботсвана', 'габон', 'лесото', 'гвинея-бисау',
            'сьерра-леоне', 'реюньон', 'маврикий', 'эсватини', 'джибути', 'коморы', 'кабо-верде', 'сейшелы',
            # Английские названия
            'egypt', 'south africa', 'nigeria', 'ethiopia', 'kenya', 'tanzania', 'algeria', 'morocco',
            'angola', 'ghana', 'congo', 'sudan', 'uganda', 'mozambique', 'ivory coast', 'madagascar',
            'cameroon', 'niger', 'mali', 'burkina faso', 'malawi', 'zambia', 'senegal', 'chad', 'somalia',
            'zimbabwe', 'guinea', 'rwanda', 'benin', 'burundi', 'tunisia', 'south sudan', 'togo', 'libya',
            'liberia', 'central african republic', 'mauritania', 'eritrea', 'namibia', 'gambia', 'botswana',
            'gabon', 'lesotho', 'guinea-bissau', 'sierra leone', 'reunion', 'mauritius', 'eswatini',
            'djibouti', 'comoros', 'cape verde', 'seychelles'
        ]
    },
    'oceania': {
        'name': '🦘 Океания',
        'countries': [
            'австралия', 'новая зеландия', 'папуа', 'новая гвинея', 'фиджи', 'соломоновы острова',
            'вануату', 'самоа', 'кирибати', 'микронезия', 'тонга', 'палау', 'маршалловы острова',
            'науру', 'тувалу', 'острова кука', 'ниуэ', 'токелау',
            # Английские названия
            'australia', 'new zealand', 'papua new guinea', 'fiji', 'solomon islands', 'vanuatu',
            'samoa', 'kiribati', 'micronesia', 'tonga', 'palau', 'marshall islands', 'nauru',
            'tuvalu', 'cook islands', 'niue', 'tokelau'
        ]
    }
}

def normalize_country_name(country):
    if not country:
        return ""
    return country.lower().strip()

def get_user_continents(user_id, session):
    user_countries = session.query(
        func.distinct(Travel.country)
    ).filter(Travel.user_id == user_id).all()

    user_countries = [country[0] for country in user_countries if country[0]]

    available_continents = set()

    for country in user_countries:
        normalized_country = normalize_country_name(country)
        for continent_code, continent_data in CONTINENTS.items():
            if any(normalized_country in normalize_country_name(c) for c in continent_data['countries']):
                available_continents.add(continent_code)
                break

    return available_continents