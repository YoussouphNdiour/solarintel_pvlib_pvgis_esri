"""ORM model registry for SolarIntel v2.

Importing this package ensures that all model classes are registered with
the SQLAlchemy ``Base`` metadata before Alembic or ``create_all()`` is called.

Usage::

    from app.models import Base, User, Project  # noqa: F401
    # Now Base.metadata knows about all tables.
"""

from app.models.base import Base
from app.models.equipment import Equipment
from app.models.monitoring import Monitoring
from app.models.project import Project
from app.models.report import Report
from app.models.simulation import Simulation
from app.models.tariff_history import TariffHistory
from app.models.user import User

__all__ = [
    "Base",
    "Equipment",
    "Monitoring",
    "Project",
    "Report",
    "Simulation",
    "TariffHistory",
    "User",
]
