from typing import Any, Dict
import json
import os

try:
    from sqlalchemy import create_engine, MetaData, Table, text
    from sqlalchemy import select as sa_select
    from sqlalchemy import update as sa_update
    from sqlalchemy import delete as sa_delete
    from sqlalchemy.dialects.mysql import insert as mysql_insert
except Exception:
    create_engine = None
    MetaData = None
    Table = None
    text = None
    sa_select = None
    sa_update = None
    sa_delete = None
    mysql_insert = None
import uuid
import psycopg2


class _QueryResult:
    def __init__(self, data=None):
        self.data = data or []


class _MariaQuery:
    def __init__(self, adapter, table_name):
        self.adapter = adapter
        self.table_name = table_name
        self.action = 'select'
        self.select_columns = ['*']
        self.filters = []
        self.order_column = None
        self.order_desc = False
        self.limit_value = None
        self.payload = None
        self.upsert_conflict = None

    def select(self, columns='*'):
        if isinstance(columns, str):
            if columns.strip() == '*':
                self.select_columns = ['*']
            else:
                self.select_columns = [c.strip() for c in columns.split(',') if c.strip()]
        elif isinstance(columns, (list, tuple)):
            self.select_columns = [str(c).strip() for c in columns if str(c).strip()]
        return self

    def eq(self, key, value):
        self.filters.append(('eq', key, value))
        return self

    def in_(self, key, values):
        self.filters.append(('in', key, list(values)))
        return self

    def like(self, key, value):
        self.filters.append(('like', key, value))
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = bool(desc)
        return self

    def limit(self, value):
        self.limit_value = int(value)
        return self

    def insert(self, payload):
        self.action = 'insert'
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.action = 'upsert'
        self.payload = payload
        self.upsert_conflict = on_conflict
        return self

    def update(self, payload):
        self.action = 'update'
        self.payload = payload
        return self

    def delete(self):
        self.action = 'delete'
        return self

    def _build_where_clauses(self, table):
        clauses = []
        for op, key, value in self.filters:
            column = table.c[key]
            if op == 'eq':
                clauses.append(column == value)
            elif op == 'in':
                clauses.append(column.in_(value))
            elif op == 'like':
                clauses.append(column.like(value))
        return clauses

    def _select_rows(self, conn, table, where_clauses=None):
        stmt = sa_select(table)
        for clause in where_clauses or []:
            stmt = stmt.where(clause)
        rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_row_payload(payload):
        normalized = {}
        for key, value in (payload or {}).items():
            if isinstance(value, (dict, list)):
                normalized[key] = json.dumps(value, ensure_ascii=False)
            else:
                normalized[key] = value
        return normalized

    def execute(self):
        table = self.adapter.get_table(self.table_name)
        with self.adapter.engine.begin() as conn:
            if self.action == 'select':
                if self.select_columns == ['*']:
                    stmt = sa_select(table)
                else:
                    selected = [table.c[name] for name in self.select_columns]
                    stmt = sa_select(*selected)

                for clause in self._build_where_clauses(table):
                    stmt = stmt.where(clause)

                if self.order_column:
                    order_col = table.c[self.order_column]
                    stmt = stmt.order_by(order_col.desc() if self.order_desc else order_col.asc())

                if self.limit_value is not None:
                    stmt = stmt.limit(self.limit_value)

                rows = conn.execute(stmt).mappings().all()
                return _QueryResult([dict(row) for row in rows])

            if self.action == 'insert':
                if isinstance(self.payload, list):
                    if not self.payload:
                        return _QueryResult([])
                    rows_payload = [self._normalize_row_payload(row) for row in self.payload]
                    conn.execute(mysql_insert(table).values(rows_payload))
                    return _QueryResult(rows_payload)

                payload = self._normalize_row_payload(dict(self.payload or {}))
                result = conn.execute(mysql_insert(table).values(payload))
                primary_key = self.adapter.primary_key_name(table)
                if primary_key and primary_key not in payload and result.lastrowid is not None:
                    payload[primary_key] = result.lastrowid
                return _QueryResult([payload])

            if self.action == 'upsert':
                payload = self._normalize_row_payload(dict(self.payload or {}))
                conflict_keys = [k.strip() for k in str(self.upsert_conflict or '').split(',') if k.strip()]
                if not conflict_keys:
                    conflict_keys = [self.adapter.primary_key_name(table)]
                    conflict_keys = [k for k in conflict_keys if k]

                insert_stmt = mysql_insert(table).values(payload)
                update_map = {
                    key: getattr(insert_stmt.inserted, key)
                    for key in payload.keys()
                    if key not in conflict_keys
                }
                stmt = insert_stmt.on_duplicate_key_update(**update_map)
                conn.execute(stmt)

                lookup = sa_select(table)
                for key in conflict_keys:
                    lookup = lookup.where(table.c[key] == payload.get(key))
                rows = conn.execute(lookup).mappings().all()
                return _QueryResult([dict(row) for row in rows])

            if self.action == 'update':
                where_clauses = self._build_where_clauses(table)
                stmt = sa_update(table).values(self._normalize_row_payload(dict(self.payload or {})))
                for clause in where_clauses:
                    stmt = stmt.where(clause)
                conn.execute(stmt)
                rows = self._select_rows(conn, table, where_clauses)
                return _QueryResult(rows)

            if self.action == 'delete':
                where_clauses = self._build_where_clauses(table)
                rows = self._select_rows(conn, table, where_clauses)
                stmt = sa_delete(table)
                for clause in where_clauses:
                    stmt = stmt.where(clause)
                conn.execute(stmt)
                return _QueryResult(rows)

        return _QueryResult([])


class MariaDBProvider:
    def __init__(self, config: Dict[str, str]):
        if create_engine is None:
            raise RuntimeError('MariaDB provider requires SQLAlchemy and pymysql')

        # Accept either MARIADB_URL or components
        url = config.get('MARIADB_URL') or os.getenv('MARIADB_URL')
        if not url:
            host = config.get('MARIADB_HOST') or os.getenv('MARIADB_HOST', 'localhost')
            port = config.get('MARIADB_PORT') or os.getenv('MARIADB_PORT', '3306')
            user = config.get('MARIADB_USER') or os.getenv('MARIADB_USER')
            password = config.get('MARIADB_PASSWORD') or os.getenv('MARIADB_PASSWORD')
            database = config.get('MARIADB_DATABASE') or os.getenv('MARIADB_DATABASE')
            if not (user and database):
                raise RuntimeError('MARIADB_URL or MARIADB_USER/MARIADB_DATABASE must be set for MariaDBProvider')
            url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

        self.engine = create_engine(url, pool_pre_ping=True)
        self.metadata = MetaData()
        self.table_cache = {}

    def ping(self):
        with self.engine.connect() as conn:
            conn.execute(text('SELECT 1'))

    def table(self, table_name: str) -> Any:
        return _MariaQuery(self, table_name)

    def get_table(self, table_name: str):
        if table_name not in self.table_cache:
            self.table_cache[table_name] = Table(table_name, self.metadata, autoload_with=self.engine)
        return self.table_cache[table_name]

    @staticmethod
    def primary_key_name(table):
        primary_keys = list(table.primary_key.columns)
        if not primary_keys:
            return None
        return primary_keys[0].name

    def populate_langchain_embeddings(self, collection_name: str, chunk_records: list, subject_id: int) -> int:
        """Insert chunk embeddings into langchain_pg_embedding for PGVector usage (Postgres-backed index).

        This writes directly to the Postgres `langchain_pg_*` tables (PGVector). It uses the
        runtime Postgres connection configured via environment variables so the vector index
        can live in Postgres while the primary DB backend is MariaDB.
        """
        inserted = 0
        try:
            db_conn = psycopg2.connect(
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT'),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            )
            db_cur = db_conn.cursor()

            db_cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name = %s;", (collection_name,))
            collection_row = db_cur.fetchone()
            if not collection_row:
                raise RuntimeError(f"Collection '{collection_name}' not found in langchain_pg_collection")
            collection_id = collection_row[0]

            for chunk_record in chunk_records:
                if 'embedding' in chunk_record and chunk_record['embedding']:
                    embedding_id = str(uuid.uuid4())
                    cmetadata = {
                        'subject_id': subject_id,
                        'source_file': chunk_record.get('source_file'),
                        'chunk_index': chunk_record.get('chunk_metadata', {}).get('chunk_index'),
                    }
                    db_cur.execute(
                        """
                        INSERT INTO langchain_pg_embedding (id, collection_id, embedding, document, cmetadata)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            embedding_id,
                            collection_id,
                            chunk_record['embedding'],
                            chunk_record['content'],
                            json.dumps(cmetadata)
                        )
                    )
                    inserted += 1

            db_conn.commit()
            db_cur.close()
            db_conn.close()
            return inserted
        except Exception:
            try:
                if 'db_conn' in locals():
                    db_conn.rollback()
                    db_conn.close()
            except Exception:
                pass
            raise
