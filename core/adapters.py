"""DB adapters: unified interface for different databases."""
import sqlite3, sys, os
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class Article:
    id: str
    title: str
    content: str
    source: str
    publish_date: str
    url: str
    db_name: str


class DBAdapter:
    """Base adapter interface."""
    name: str = ''
    db_type: str = ''

    def get_total_count(self) -> int:
        raise NotImplementedError

    def get_unprocessed_ids(self, last_processed_row_id: int) -> List[int]:
        raise NotImplementedError

    def get_articles(self, row_ids: List[int]) -> List[Article]:
        raise NotImplementedError


# ── Institutions SQLite ──────────────────────────────────────────

class InstitutionsAdapter(DBAdapter):
    name = 'institutions'
    db_type = 'sqlite'

    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_total_count(self):
        conn = self._connect()
        c = conn.execute('SELECT COUNT(*) FROM articles')
        count = c.fetchone()[0]
        conn.close()
        return count

    def get_unprocessed_ids(self, last_id):
        conn = self._connect()
        rows = conn.execute(
            'SELECT id FROM articles WHERE id > ? ORDER BY id', (last_id,)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_articles(self, row_ids):
        if not row_ids:
            return []
        conn = self._connect()
        placeholders = ','.join('?' * len(row_ids))
        rows = conn.execute(
            f'SELECT id, title, content, source, publish_date, url '
            f'FROM articles WHERE id IN ({placeholders})',
            row_ids,
        ).fetchall()
        conn.close()
        return [
            Article(
                id=f'{self.name}:{r["id"]}',
                title=r['title'] or '',
                content=r['content'] or '',
                source=r['source'] or '',
                publish_date=r['publish_date'] or '',
                url=r['url'] or '',
                db_name=self.name,
            )
            for r in rows
        ]


# ── Liangke Historical SQLite ─────────────────────────────────────

class LiangkeHistoricalAdapter(DBAdapter):
    name = 'liangke_historical'
    db_type = 'sqlite'

    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_total_count(self):
        conn = self._connect()
        c = conn.execute('SELECT COUNT(*) FROM articles')
        count = c.fetchone()[0]
        conn.close()
        return count

    def get_unprocessed_ids(self, last_id):
        conn = self._connect()
        rows = conn.execute(
            'SELECT id FROM articles WHERE id > ? ORDER BY id', (last_id,)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_articles(self, row_ids):
        if not row_ids:
            return []
        conn = self._connect()
        placeholders = ','.join('?' * len(row_ids))
        rows = conn.execute(
            f'SELECT id, title, content, source_domain, published_at, liangke_url '
            f'FROM articles WHERE id IN ({placeholders})',
            row_ids,
        ).fetchall()
        conn.close()
        return [
            Article(
                id=f'{self.name}:{r["id"]}',
                title=r['title'] or '',
                content=r['content'] or '',
                source=r['source_domain'] or '',
                publish_date=str(r['published_at'] or '')[:10],
                url=r['liangke_url'] or '',
                db_name=self.name,
            )
            for r in rows
        ]


# ── Liangke Daily MySQL ───────────────────────────────────────────

class LiangkeDailyAdapter(DBAdapter):
    name = 'liangke_daily'
    db_type = 'mysql'

    def __init__(self, host, port, user, password, database):
        self.conn_info = {
            'host': host, 'port': port, 'user': user,
            'password': password, 'database': database,
        }

    def _connect(self):
        import pymysql
        return pymysql.connect(
            **self.conn_info,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )

    def get_total_count(self):
        conn = self._connect()
        with conn.cursor() as c:
            c.execute('SELECT COUNT(*) as cnt FROM articles')
            count = c.fetchone()['cnt']
        conn.close()
        return count

    def get_unprocessed_ids(self, last_id):
        conn = self._connect()
        with conn.cursor() as c:
            c.execute('SELECT id FROM articles WHERE id > %s ORDER BY id', (last_id,))
            rows = c.fetchall()
        conn.close()
        return [r['id'] for r in rows]

    def get_articles(self, row_ids):
        if not row_ids:
            return []
        conn = self._connect()
        placeholders = ','.join('%s' for _ in row_ids)
        with conn.cursor() as c:
            c.execute(
                f'SELECT id, title, content, source_domain, original_date, reference_url '
                f'FROM articles WHERE id IN ({placeholders})',
                row_ids,
            )
            rows = c.fetchall()
        conn.close()
        return [
            Article(
                id=f'{self.name}:{r["id"]}',
                title=r['title'] or '',
                content=r['content'] or '',
                source=r['source_domain'] or '',
                publish_date=str(r['original_date'] or '')[:10],
                url=r['reference_url'] or '',
                db_name=self.name,
            )
            for r in rows
        ]
