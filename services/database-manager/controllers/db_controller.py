from typing import Any
import os

from providers.supabase_provider import SupabaseProvider
from providers.mariadb_provider import MariaDBProvider


class DBController:
    """Controller that selects and exposes a unified DB provider.

    It exposes a `table(name)` method so existing code can continue
    to call `supabase.table('...').select(...).execute()` while the
    controller delegates to the concrete provider.
    """

    def __init__(self, backend: str, config: dict):
        self.backend = (backend or 'supabase').strip().lower()
        self.config = config or {}
        self.provider = None
        self.client = None
        self._init_provider()

    def _init_provider(self):
        if self.backend == 'mariadb':
            self.provider = MariaDBProvider(self.config)
            self.client = self.provider.client
        else:
            self.provider = SupabaseProvider(self.config)
            self.client = self.provider.client

    def table(self, table_name: str) -> Any:
        return self.provider.table(table_name)

    def ping(self) -> None:
        return self.provider.ping()

    # allow attribute passthrough for advanced use
    def __getattr__(self, item):
        return getattr(self.provider, item)
