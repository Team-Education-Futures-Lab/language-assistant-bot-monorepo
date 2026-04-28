"""
Supabase Database Provider Implementation
"""

import logging
from typing import Any, List, Dict, Optional
from supabase import create_client
from modules.database_provider import DatabaseProvider, TableQuery, QueryResult


logger = logging.getLogger(__name__)


class SupabaseTableQuery(TableQuery):
    """Supabase query builder"""

    def __init__(self, supabase_client, table_name: str):
        self.client = supabase_client
        self.table_name = table_name
        self._query = self.client.table(table_name)
        self._select_columns = '*'
        self._filters = []
        self._order_by = None
        self._limit_value = None
        self._is_insert = False
        self._is_update = False
        self._is_delete = False
        self._records = []
        self._updates = {}

    def select(self, columns: str = '*') -> 'SupabaseTableQuery':
        self._select_columns = columns
        return self

    def eq(self, column: str, value: Any) -> 'SupabaseTableQuery':
        self._filters.append((column, value))
        return self

    def order(self, column: str, ascending: bool = True) -> 'SupabaseTableQuery':
        self._order_by = (column, ascending)
        return self

    def limit(self, count: int) -> 'SupabaseTableQuery':
        self._limit_value = count
        return self

    def insert(self, records: List[Dict]) -> 'SupabaseTableQuery':
        self._is_insert = True
        self._records = records
        return self

    def update(self, updates: Dict) -> 'SupabaseTableQuery':
        self._is_update = True
        self._updates = updates
        return self

    def delete(self) -> 'SupabaseTableQuery':
        self._is_delete = True
        return self

    def execute(self) -> QueryResult:
        try:
            query = self.client.table(self.table_name)

            if self._is_insert:
                response = query.insert(self._records).execute()
                return QueryResult(data=response.data, status='success')

            if self._is_update:
                query = query.update(self._updates)
                for column, value in self._filters:
                    query = query.eq(column, value)
                response = query.execute()
                return QueryResult(data=response.data, status='success')

            if self._is_delete:
                query = query.delete()
                for column, value in self._filters:
                    query = query.eq(column, value)
                response = query.execute()
                return QueryResult(data=response.data, status='success')

            # SELECT query
            query = query.select(self._select_columns)
            for column, value in self._filters:
                query = query.eq(column, value)

            if self._order_by:
                column, ascending = self._order_by
                query = query.order(column, ascending=ascending)

            if self._limit_value:
                query = query.limit(self._limit_value)

            response = query.execute()
            return QueryResult(data=response.data, count=response.count, status='success')

        except Exception as e:
            logger.error(f"Supabase query error: {str(e)}")
            return QueryResult(data=[], status='error')


class SupabaseProvider(DatabaseProvider):
    """Supabase implementation of DatabaseProvider"""

    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        try:
            self.client = create_client(self.url, self.key)
            # Test connection
            self.client.table('subjects').select('id').limit(1).execute()
            self._connected = True
            logger.info("✓ Supabase connected successfully")
            return True
        except Exception as e:
            logger.error(f"✗ Supabase connection failed: {str(e)}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected and self.client is not None

    def table(self, table_name: str) -> SupabaseTableQuery:
        if not self.is_connected():
            raise RuntimeError("Supabase client not connected")
        return SupabaseTableQuery(self.client, table_name)

    def close(self) -> None:
        self._connected = False
        self.client = None
        logger.info("Supabase connection closed")
