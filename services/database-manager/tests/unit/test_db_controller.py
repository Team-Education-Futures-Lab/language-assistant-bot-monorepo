from pathlib import Path
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

import controllers.db_controller as db_controller_module


class FakeSupabaseProvider:
    def __init__(self, config):
        self.config = config
        self.client = {"provider": "supabase"}
        self.provider_name = "supabase"

    def table(self, table_name):
        return {"table": table_name, "provider": self.provider_name}

    def ping(self):
        return True


class FakeMariaDBProvider:
    def __init__(self, config):
        self.config = config
        self.client = {"provider": "mariadb"}
        self.provider_name = "mariadb"

    def table(self, table_name):
        return {"table": table_name, "provider": self.provider_name}

    def ping(self):
        return True


def test_defaults_to_supabase_when_backend_missing(monkeypatch):
    monkeypatch.setattr(db_controller_module, "SupabaseProvider", FakeSupabaseProvider)
    monkeypatch.setattr(db_controller_module, "MariaDBProvider", FakeMariaDBProvider)

    controller = db_controller_module.DBController(None, {"x": "y"})

    assert controller.backend == "supabase"
    assert controller.client == {"provider": "supabase"}
    assert controller.table("subjects") == {"table": "subjects", "provider": "supabase"}


def test_uses_mariadb_provider_when_requested(monkeypatch):
    monkeypatch.setattr(db_controller_module, "SupabaseProvider", FakeSupabaseProvider)
    monkeypatch.setattr(db_controller_module, "MariaDBProvider", FakeMariaDBProvider)

    controller = db_controller_module.DBController("mariadb", {"MARIADB_HOST": "localhost"})

    assert controller.backend == "mariadb"
    assert controller.client == {"provider": "mariadb"}
    assert controller.table("chunks") == {"table": "chunks", "provider": "mariadb"}


def test_ping_is_delegated_to_provider(monkeypatch):
    monkeypatch.setattr(db_controller_module, "SupabaseProvider", FakeSupabaseProvider)
    monkeypatch.setattr(db_controller_module, "MariaDBProvider", FakeMariaDBProvider)

    controller = db_controller_module.DBController("supabase", {})
    assert controller.ping() is True
