import pymysql
from flask import g

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host='sql7.freesqldatabase.com',
            user='sql7786198',
            password='pm8haR585d',
            database='sql7786198',
            port=3306,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db