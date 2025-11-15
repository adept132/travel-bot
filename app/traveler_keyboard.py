from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='❓ О проекте', callback_data='info')]
])

after_info_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🚀 Начать путешествовать', callback_data='start')],
    [InlineKeyboardButton(text='💰 Условия использования', callback_data='free')]
])

travel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🎒 Начать новое путешествие', callback_data='start_travel')]
])

type_media_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='📸 Добавить фото', callback_data='photo')],
    [InlineKeyboardButton(text='🎥 Добавить видео', callback_data='video')]
])

media_more_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📸 Еще фото", callback_data="add_photo_again")],
    [InlineKeyboardButton(text="🎥 Еще видео", callback_data="add_video_again")],
    [InlineKeyboardButton(text="✅ Готово", callback_data="finish_media")]
])

finish_place_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📍 Добавить место", callback_data="another_place")],
    [InlineKeyboardButton(text="🏁 Закончить", callback_data="finish_travel")]
])

menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='🌍 Новое путешествие', callback_data='start_travel'),
        InlineKeyboardButton(text='➡️ Продолжить', callback_data='continue_travel'),
        InlineKeyboardButton(text="🚀 Быстрое добавление", callback_data="quick_add_place")
    ],
    [
        InlineKeyboardButton(text='📊 Отчеты', callback_data='report'),
        InlineKeyboardButton(text='🗺️ Карта', callback_data='heatmap')
    ],
    [
        InlineKeyboardButton(text='👤 Профиль', callback_data='profile_check'),
        InlineKeyboardButton(text='🏆 Достижения', callback_data='achievements'),
        InlineKeyboardButton(text="📤 Экспорт данных", callback_data="export_menu")
    ],
    [
        InlineKeyboardButton(text="🔍 Умный поиск", callback_data="smart_search"),
        InlineKeyboardButton(text="🔔 Напоминания", callback_data="reminders_settings")

    ],
    [
        InlineKeyboardButton(text='💎 Премиум', callback_data='premium_check'),
        InlineKeyboardButton(text='⚡ Функции', callback_data='premium_functions')
    ]
])

back_to_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
])

achievements_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_achievements")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
])

location_manual_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📍 Отправить геолокацию", request_location=True),
            KeyboardButton(text="➡️ Пропустить")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)