"""Test configuration."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflow_manager.core.models import Base


@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = testing_session_local()
    yield session
    session.close()


@pytest.fixture
def test_settings():
    """Create test settings."""
    from workflow_manager.config import Settings

    return Settings(
        database_url="sqlite:///:memory:",
        debug=True,
        scheduler_enabled=False,
    )
