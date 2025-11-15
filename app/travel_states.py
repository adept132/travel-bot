from aiogram.fsm.state import State, StatesGroup

class TravelState(StatesGroup):
    country = State()
    start_date = State()
    end_date = State()

class EntryState(StatesGroup):
    city = State()
    visitation_date = State()
    place_title = State()
    place_comment = State()
    location_manual = State()
    place_media = State()
    adding_more_photo = State()
    adding_more_video = State()
    place_rating = State()
    another_place = State()

class TravelFinish(StatesGroup):
    travel_comment = State()
    travel_rating = State()

class Menu(StatesGroup):
    menu = State()

class PremiumPayment(StatesGroup):
    waiting_for_screenshot = State()

class QuickAddState(StatesGroup):
    country = State()
    city = State()
    place_title = State()
    place_comment = State()
    date = State()
    custom_date = State()
    adding_photo = State()
    adding_video = State()
    rating = State()
    adding_coordinates = State()
    waiting_location = State()
    waiting_coordinates_input = State()