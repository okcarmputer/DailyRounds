import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_connection(env: str):
    """env is 'dev' or 'prod'."""
    key = f"{env.upper()}_SQL_CONN_STRING"
    conn_str = os.environ[key]
    return pyodbc.connect(conn_str)
