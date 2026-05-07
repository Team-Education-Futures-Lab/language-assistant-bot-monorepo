from pathlib import Path
import sys

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

import providers.mariadb_provider as mariadb_provider_module


class DummyEngine:
    pass


def test_uses_explicit_mariadb_url(monkeypatch):
    captured = {}

    def fake_create_engine(url, pool_pre_ping=True):
        captured["url"] = url
        captured["pool_pre_ping"] = pool_pre_ping
        return DummyEngine()

    monkeypatch.setattr(mariadb_provider_module, "create_engine", fake_create_engine)

    provider = mariadb_provider_module.MariaDBProvider(
        {"MARIADB_URL": "mysql+pymysql://user:pass@db:3306/mydb"}
    )

    assert isinstance(provider.engine, DummyEngine)
    assert captured["url"] == "mysql+pymysql://user:pass@db:3306/mydb"
    assert captured["pool_pre_ping"] is True


def test_builds_url_from_components(monkeypatch):
    captured = {}

    def fake_create_engine(url, pool_pre_ping=True):
        captured["url"] = url
        return DummyEngine()

    monkeypatch.setattr(mariadb_provider_module, "create_engine", fake_create_engine)

    mariadb_provider_module.MariaDBProvider(
        {
            "MARIADB_HOST": "localhost",
            "MARIADB_PORT": "3306",
            "MARIADB_USER": "demo",
            "MARIADB_PASSWORD": "secret",
            "MARIADB_DATABASE": "school",
        }
    )

    assert captured["url"] == "mysql+pymysql://demo:secret@localhost:3306/school"


def test_raises_when_no_url_and_missing_required_components(monkeypatch):
    monkeypatch.setattr(mariadb_provider_module, "create_engine", lambda *args, **kwargs: DummyEngine())

    with pytest.raises(RuntimeError, match="MARIADB_URL or MARIADB_USER/MARIADB_DATABASE"):
        mariadb_provider_module.MariaDBProvider({"MARIADB_HOST": "localhost"})
