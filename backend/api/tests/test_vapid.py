"""VAPID key bootstrap used by the Dokploy named volume."""

from pathlib import Path


def test_ensure_vapid_keys_generates_private_and_public(tmp_path, monkeypatch):
    from app.config import settings
    from app.notifications import ensure_vapid_keys, get_vapid_public_key

    private_path = tmp_path / "vapid_private.pem"
    public_path = tmp_path / "vapid_public.pem"
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "VAPID_AUTO_GENERATE", True)
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY_PATH", str(public_path))
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY_PATH", str(private_path))
    get_vapid_public_key.cache_clear()

    ensure_vapid_keys()

    assert private_path.is_file()
    assert public_path.is_file()
    assert (private_path.stat().st_mode & 0o777) == 0o600
    assert len(get_vapid_public_key() or "") > 40

    first = private_path.read_bytes()
    ensure_vapid_keys()
    assert private_path.read_bytes() == first
    get_vapid_public_key.cache_clear()
