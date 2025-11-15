from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="travel_bot")

def geocode_place(place_name: str):
    location = geolocator.geocode(place_name)
    if location:
        return location.latitude, location.longitude
    return None, None
