import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_database_url():
    cloud_db_url = os.getenv('DATABASE_URL')
    if cloud_db_url:
        return cloud_db_url
    
    db_host = os.getenv('db_host')
    if db_host:
        user = os.getenv('db_user', 'travel_admin')
        password = os.getenv('db_password', 'SQLDataBase132!')
        db_name = os.getenv('db_name', 'travel_db')
        return f'mysql+pymysql://{user}:{password}@{db_host}:3306/{db_name}'
    
    return 'sqlite:///travel_bot.db'

database_url = get_database_url()

connect_args = {}
if 'sqlite' in database_url:
    connect_args = {'check_same_thread': False}

engine = create_engine(database_url, connect_args=connect_args, echo=True)
Session = sessionmaker(bind=engine)
