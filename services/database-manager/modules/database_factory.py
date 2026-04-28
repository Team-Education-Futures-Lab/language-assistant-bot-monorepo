"""
Database Provider Factory
Selects and initializes the appropriate database provider based on configuration
"""

import os
import logging
from modules.database_provider import DatabaseProvider
from modules.supabase_provider import SupabaseProvider
from modules.mariadb_provider import MariaDBProvider, MARIADB_ADAPTER_AVAILABLE


logger = logging.getLogger(__name__)


class DatabaseFactory:
    """Factory for creating database provider instances"""

    @staticmethod
    def create_provider(backend: str = None) -> DatabaseProvider:
        """
        Create a database provider based on backend type.
        
        Args:
            backend: 'supabase' or 'mariadb'. If None, reads from DB_BACKEND env var.
        
        Returns:
            Configured DatabaseProvider instance
        
        Raises:
            ValueError: If backend is invalid or dependencies missing
        """
        if backend is None:
            backend = os.getenv('DB_BACKEND', 'supabase').strip().lower()

        if backend == 'supabase':
            return DatabaseFactory._create_supabase_provider()
        elif backend == 'mariadb':
            return DatabaseFactory._create_mariadb_provider()
        else:
            raise ValueError(f"Unknown database backend: {backend}. Supported: 'supabase', 'mariadb'")

    @staticmethod
    def _create_supabase_provider() -> SupabaseProvider:
        """Create Supabase provider"""
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')

        if not url or not key:
            raise ValueError("Missing Supabase credentials: SUPABASE_URL and SUPABASE_KEY required")

        logger.info("Initializing Supabase provider")
        return SupabaseProvider(url=url, key=key)

    @staticmethod
    def _create_mariadb_provider() -> MariaDBProvider:
        """Create MariaDB provider"""
        if not MARIADB_ADAPTER_AVAILABLE:
            raise ValueError(
                "MariaDB dependencies not available. "
                "Install with: pip install sqlalchemy pymysql"
            )

        host = os.getenv('MARIADB_HOST', 'localhost').strip()
        port = int(os.getenv('MARIADB_PORT', '3306'))
        user = os.getenv('MARIADB_USER', '').strip()
        password = os.getenv('MARIADB_PASSWORD', '').strip()
        database = os.getenv('MARIADB_DATABASE', '').strip()

        if not all([user, password, database]):
            raise ValueError(
                "Missing MariaDB credentials: "
                "MARIADB_USER, MARIADB_PASSWORD, MARIADB_DATABASE required"
            )

        logger.info(f"Initializing MariaDB provider (host={host}, port={port})")
        return MariaDBProvider(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
