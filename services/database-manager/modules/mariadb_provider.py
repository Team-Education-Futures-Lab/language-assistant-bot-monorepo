"""
MariaDB Database Provider Implementation
Wraps the existing MariaDBAdapter with the DatabaseProvider interface
"""

import logging
from typing import Any, List, Dict, Optional
from modules.database_provider import DatabaseProvider, TableQuery, QueryResult

try:
    from modules.mariadb_adapter import MariaDBAdapter, MARIADB_ADAPTER_AVAILABLE
except Exception:
    MARIADB_ADAPTER_AVAILABLE = False
    MariaDBAdapter = None


logger = logging.getLogger(__name__)


class MariaDBTableQuery(TableQuery):
    """MariaDB query builder wrapping the existing adapter"""

    def __init__(self, adapter: 'MariaDBAdapter', table_name: str):
        self.adapter = adapter
        self.table_name = table_name
        self._query = adapter._create_query(table_name)

    def select(self, columns: str = '*') -> 'MariaDBTableQuery':
        self._query = self._query.select(columns)
        return self

    def eq(self, column: str, value: Any) -> 'MariaDBTableQuery':
        self._query = self._query.eq(column, value)
        return self

    def order(self, column: str, ascending: bool = True) -> 'MariaDBTableQuery':
        self._query = self._query.order(column, ascending=ascending)
        return self

    def limit(self, count: int) -> 'MariaDBTableQuery':
        self._query = self._query.limit(count)
        return self

    def insert(self, records: List[Dict]) -> 'MariaDBTableQuery':
        self._query = self._query.insert(records)
        return self

    def update(self, updates: Dict) -> 'MariaDBTableQuery':
        self._query = self._query.update(updates)
        return self

    def delete(self) -> 'MariaDBTableQuery':
        self._query = self._query.delete()
        return self

    def execute(self) -> QueryResult:
        try:
            result = self._query.execute()
            return QueryResult(data=result.data if hasattr(result, 'data') else result, status='success')
        except Exception as e:
            logger.error(f"MariaDB query error: {str(e)}")
            return QueryResult(data=[], status='error')


class MariaDBProvider(DatabaseProvider):
    """MariaDB implementation of DatabaseProvider"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        if not MARIADB_ADAPTER_AVAILABLE:
            raise RuntimeError("MariaDB dependencies not installed. Install sqlalchemy and pymysql.")
        
        self.adapter = MariaDBAdapter(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        self._connected = False

    def connect(self) -> bool:
        try:
            self.adapter.connect()
            self._connected = True
            logger.info("✓ MariaDB connected successfully")
            return True
        except Exception as e:
            logger.error(f"✗ MariaDB connection failed: {str(e)}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected and self.adapter is not None

    def table(self, table_name: str) -> MariaDBTableQuery:
        if not self.is_connected():
            raise RuntimeError("MariaDB adapter not connected")
        return MariaDBTableQuery(self.adapter, table_name)

    def close(self) -> None:
        try:
            if self.adapter:
                self.adapter.close()
            self._connected = False
            logger.info("MariaDB connection closed")
        except Exception as e:
            logger.warning(f"Error closing MariaDB: {str(e)}")
