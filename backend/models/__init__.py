# Import all models here so Alembic can detect them for migrations.
# Order matters — import tables with no foreign keys first.

from models.user import Role, User
from models.clause import Clause
from models.rule import Rule
from models.log_event import LogEvent
from models.case import Case, AlertComment
from models.alert import Alert
from models.report import Report, AuditLog
