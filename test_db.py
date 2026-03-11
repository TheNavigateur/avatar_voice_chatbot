import os
import psycopg2
db_url = os.environ.get("DATABASE_URL")
print(db_url)
try:
    conn = psycopg2.connect(db_url)
    print("Success")
except Exception as e:
    print(e)
