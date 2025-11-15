import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_database_path():
    persistent_paths = ['/app/data', '/data', '/tmp/persistent']

    for path in persistent_paths:
        if os.path.exists(path) and os.access(path, os.W_OK):
            return f"sqlite:///{path}/travel_bot.db"

    return "sqlite:///travel_bot.db"


database_url = os.getenv('DATABASE_URL', get_database_path())
connect_args = {}

if 'sqlite' in database_url:
    connect_args = {'check_same_thread': False}

engine = create_engine(database_url, connect_args=connect_args, echo=True)
Session = sessionmaker(bind=engine)

print(f"📦 Database URL: {database_url}")

database_url = os.getenv('DATABASE_URL')

if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

if not database_url:
    database_url = 'sqlite:///travel_bot.db'

connect_args = {}
if 'sqlite' in database_url:
    connect_args = {'check_same_thread': False}

engine = create_engine(database_url, connect_args=connect_args)
Session = sessionmaker(bind=engine)

print(f"📦 Database URL: {database_url}")

engine = create_engine(database_url, connect_args=connect_args, echo=True)
Session = sessionmaker(bind=engine)
