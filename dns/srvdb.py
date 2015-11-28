
import apsw
import time

class SrvDb(object):
    def __init__(self, filename):
        self.connection = apsw.Connection(filename)

    def domains(self):
        cursor = self.connection.cursor()

        # retrieve sorted domain list
        rows = []
        for row in cursor.execute("SELECT name FROM domains ORDER BY name"):
            rows.append(row[0])
        return rows

    def add_host(self, name, days, pkh):
        cursor = self.connection.cursor()

        # Create, expiration times
        tm_creat = int(time.time())
        tm_expire = tm_creat + (days * 24 * 60 * 60)

        # Add hash metadata to db
        cursor.execute("INSERT INTO hosts VALUES(?, ?, ?, ?)", (name, tm_creat, tm_expire, pkh))

        return True

    def get_host(self, name):
        cursor = self.connection.cursor()

        curtime = int(time.time())
        row = cursor.execute("SELECT * FROM hosts WHERE name = ? AND time_expire > ?", (name, curtime)).fetchone()
        if not row:
            return None
        obj = {
            'name': row[0],
            'create': int(row[1]),
            'expire': int(row[2]),
            'pkh': row[3],
        }
        return obj

    def update_host(self, name, host_records):
        cursor = self.connection.cursor()

        cursor.execute("DELETE FROM records WHERE name = ?", (name,))

        for host_rec in host_records:
            cursor.execute("INSERT INTO records VALUES(?, ?, ?, ?)", host_rec)

    def delete_host(self, name):
        cursor = self.connection.cursor()

        cursor.execute("DELETE FROM records WHERE name = ?", (name,))
        cursor.execute("DELETE FROM hosts WHERE name = ?", (name,))
