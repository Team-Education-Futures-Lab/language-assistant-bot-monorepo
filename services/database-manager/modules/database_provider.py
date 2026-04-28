"""
Abstract Database Provider Interface
Defines the contract for all database implementations (Supabase, MariaDB, etc.)
"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional


class DatabaseProvider(ABC):
    """Abstract base class for database providers"""

    @abstractmethod
    def connect(self) -> bool:
        """Establish database connection. Returns True on success."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database is connected."""
        pass

    @abstractmethod
    def table(self, table_name: str) -> 'TableQuery':
        """Get a query builder for a table."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass


class TableQuery(ABC):
    """Abstract query builder for table operations"""

    @abstractmethod
    def select(self, columns: str = '*') -> 'TableQuery':
        """SELECT columns from table."""
        pass

    @abstractmethod
    def eq(self, column: str, value: Any) -> 'TableQuery':
        """WHERE column = value."""
        pass

    @abstractmethod
    def order(self, column: str, ascending: bool = True) -> 'TableQuery':
        """ORDER BY column ASC/DESC."""
        pass

    @abstractmethod
    def limit(self, count: int) -> 'TableQuery':
        """LIMIT count."""
        pass

    @abstractmethod
    def execute(self) -> 'QueryResult':
        """Execute query and return results."""
        pass

    @abstractmethod
    def insert(self, records: List[Dict]) -> 'TableQuery':
        """INSERT records into table."""
        pass

    @abstractmethod
    def update(self, updates: Dict) -> 'TableQuery':
        """UPDATE records."""
        pass

    @abstractmethod
    def delete(self) -> 'TableQuery':
        """DELETE records."""
        pass


class QueryResult:
    """Standardized query result"""

    def __init__(self, data: List[Dict] = None, count: Optional[int] = None, status: str = 'success'):
        self.data = data or []
        self.count = count if count is not None else len(self.data)
        self.status = status

    def __bool__(self):
        return bool(self.data)

    def __len__(self):
        return len(self.data)
