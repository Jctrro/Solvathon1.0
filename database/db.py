import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection_repo():
    return psycopg2.connect(os.getenv("REPO_DATABASE_URL"))

def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))
