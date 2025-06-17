import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='corp_training'
)

print("✅ Подключение успешно")
conn.close()