import pymysql
from flask import g
from config import DB_CONFIG

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG.get('port', 3307),
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db
