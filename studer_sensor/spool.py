import json
import sqlite3
import time


class Spool:
    """A small durable FIFO queue for records that could not be delivered."""

    def __init__(self, path, max_records=10000, base_delay=1, max_delay=300):
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self.db = sqlite3.connect(path)
        self.max_records = max_records
        self.base_delay = base_delay
        # Without a cap the delay doubles forever; after a few hours offline a record would wait
        # hours more, and the backlog would reach Grafana (accepts samples at most 2 h behind the
        # newest one of a series) too late to be accepted.
        self.max_delay = max_delay
        self.db.execute(
            "create table if not exists queue("
            "id integer primary key, payload text not null, created text not null,"
            "attempts integer not null default 0, next_try real not null default 0)"
        )
        self.db.commit()

    def enqueue(self, payload, created):
        self.db.execute(
            "insert into queue(payload,created) values(?,?)",
            (json.dumps(payload), created),
        )
        # Keep the newest records when storage is bounded.
        self.db.execute(
            "delete from queue where id in "
            "(select id from queue order by id asc limit "
            "max(0, (select count(*) from queue) - ?))",
            (self.max_records,),
        )
        self.db.commit()

    def due(self, now=None):
        now = time.time() if now is None else now
        rows = self.db.execute(
            "select id,payload,created,attempts from queue "
            "where next_try<=? order by id",
            (now,),
        ).fetchall()
        return [
            {"id": row[0], "payload": json.loads(row[1]),
             "created": row[2], "attempts": row[3]}
            for row in rows
        ]

    def acknowledge(self, record_id):
        self.db.execute("delete from queue where id=?", (record_id,))
        self.db.commit()

    def retry(self, record_id, attempts):
        self.db.execute(
            "update queue set attempts=?,next_try=? where id=?",
            (attempts + 1,
             time.time() + min(self.base_delay * (2 ** min(attempts, 30)), self.max_delay),
             record_id),
        )
        self.db.commit()

    def close(self):
        self.db.close()
