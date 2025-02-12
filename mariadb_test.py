import pymysql

conn = None
cur = None

sql = ""

conn = pymysql.connect(host='127.0.0.1', user='root', password='0728', db='pharmacy_db', charset='utf8')
cur = conn.cursor()


sql = "SELECT * FROM users"
cur.execute(sql)

row = cur.fetchone()
print(row)
cur.close()
conn.close()