import enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, BigInteger
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    premium = Column(Boolean, default=False)
    start_premium = Column(DateTime, nullable=True)
    end_premium = Column(DateTime, nullable=True)
    trip_count = Column(Integer, default=0)
    entries_count = Column(Integer, default=0)
    photos_count = Column(Integer, default=0)
    longest_trip = Column(Integer, default=0)


class Travel(Base):
    __tablename__ = 'travels'
    travel_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    status = Column(String(20), default="active")
    country = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    travel_comment = Column(String)
    travel_rating = Column(Integer)


class Entry(Base):
    __tablename__ = 'entries'
    place_id = Column(Integer, primary_key=True)
    travel_id = Column(Integer, ForeignKey('travels.travel_id'))
    city = Column(String)
    place_title = Column(String)
    place_comment = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    place_rating = Column(Integer)


class MediaTypeEnum(enum.Enum):
    photo = 'photo'
    video = 'video'
    audio = 'audio'


class Media(Base):
    __tablename__ = 'media'
    media_id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey('entries.place_id'))
    media_type = Column(Enum(MediaTypeEnum), nullable=False)
    file_id = Column(String)
    duration = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = 'achievements'
    achievement_id = Column(Integer, primary_key=True)
    code = Column(String(64), nullable=False, unique=False)
    description = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    achievement_name = Column(String)
    unlocked_at = Column(DateTime)


class AchievementList(Base):
    __tablename__ = "achievement_list"

    code = Column(String(64), primary_key=True)
    achievement_name = Column(String(64), nullable=False)
    description = Column(String(128), nullable=False)


class UserSettings(Base):
    __tablename__ = 'user_settings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    reminders_enabled = Column(Boolean, default=True)
    reminder_frequency = Column(Integer, default=30)
    last_reminder_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)