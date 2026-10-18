from core import get_prefix_table
from core.db.base_module_tables import BaseModuleTables

MODULE_NAME = "melodi_accounting"
PREFIX_TABLE = get_prefix_table(MODULE_NAME)

class AccountingTables(BaseModuleTables):
    """Centralisation dynamique des tables SQL du module de comptabilité."""
    CHART_OF_ACCOUNTS = f"{PREFIX_TABLE}chart_of_accounts"
    ZONES = f"{PREFIX_TABLE}zones"
    ACCOUNT_CLASSES = f"{PREFIX_TABLE}account_classes"
    ACCOUNTS = f"{PREFIX_TABLE}accounts"
    JOURNAL_ENTRIES = f"{PREFIX_TABLE}journal_entries"
    JOURNAL_ITEMS = f"{PREFIX_TABLE}journal_items"
    OPERATION_CODES = f"{PREFIX_TABLE}operation_codes"
    ACCOUNTING_RULES = f"{PREFIX_TABLE}accounting_rules"
    FISCAL_YEARS = f"{PREFIX_TABLE}fiscal_years"
    ACCOUNTING_QUEUE = f"{PREFIX_TABLE}queue"
    EVENT_REGISTRATION = f"{PREFIX_TABLE}event_registry"

