# backend/tests/test_config_db.py
"""Tests per a get_config (prevalença BD > env)."""
import pytest


@pytest.fixture
def app_ctx(in_memory_db):
    """Context Flask amb BD en memòria."""
    from unittest.mock import MagicMock, patch
    import backend.app.db as db_module
    saved_engine = db_module._engine
    saved_session = db_module._SessionLocal

    def _noop(url):
        db_module._engine = saved_engine
        db_module._SessionLocal = saved_session

    with patch('backend.app.db.init_db', side_effect=_noop):
        from backend.app import create_app
        app = create_app()
    app.config['TESTING'] = True
    app.extensions['storage'] = MagicMock()
    db_module._engine = saved_engine
    db_module._SessionLocal = saved_session
    with app.app_context():
        yield app


def _insert_config(key, value, value_type='string', is_secret=False):
    from backend.app.models.db_models import SystemConfigModel
    from backend.app.db import get_session
    with get_session() as db:
        db.merge(SystemConfigModel(
            key=key, value=value, value_type=value_type,
            group='test', label='', description='', is_secret=is_secret
        ))
        db.commit()


def test_returns_default_when_key_missing(app_ctx):
    from backend.app.config_db import get_config
    result = get_config('nonexistent.key', default='fallback')
    assert result == 'fallback'


def test_returns_string_value_from_db(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.model_name', 'gpt-4o', 'string')
    assert get_config('llm.model_name', 'default-model') == 'gpt-4o'


def test_casts_int_value(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('simulation.max_rounds', '15', 'int')
    result = get_config('simulation.max_rounds', 10)
    assert result == 15
    assert isinstance(result, int)


def test_casts_float_value(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('report.temperature', '0.7', 'float')
    result = get_config('report.temperature', 0.5)
    assert abs(result - 0.7) < 1e-9
    assert isinstance(result, float)


def test_returns_default_when_value_is_none(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.model_name', None, 'string')
    assert get_config('llm.model_name', 'fallback') == 'fallback'


def test_max_tokens_zero_returns_none(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('llm.max_tokens', '0', 'int')
    assert get_config('llm.max_tokens', 9999) is None


def test_casts_bool_value(app_ctx):
    from backend.app.config_db import get_config
    _insert_config('feature.enabled', 'true', 'bool')
    assert get_config('feature.enabled', False) is True
    _insert_config('feature.enabled', 'false', 'bool')
    assert get_config('feature.enabled', True) is False


def test_returns_default_on_db_error(app_ctx):
    """Si la BD no és accessible, retorna el default sense llançar excepció."""
    import backend.app.db as db_module
    from backend.app.config_db import get_config
    saved = db_module._SessionLocal
    db_module._SessionLocal = None
    try:
        result = get_config('llm.model_name', 'safe-default')
        assert result == 'safe-default'
    finally:
        db_module._SessionLocal = saved
