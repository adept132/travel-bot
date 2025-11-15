import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
load_dotenv()
user = os.getenv('db_user')
password = os.getenv('db_password')
host = os.getenv('db_host')
name = os.getenv('db_name')
engine = create_engine(
    "mysql+pymysql://travel_admin:SQLDataBase132!@localhost:3306/travel_db",
    echo=True
)
Session = sessionmaker(bind=engine)
