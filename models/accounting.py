import enum
from typing import Optional, List
from datetime import date as PyDate

from sqlalchemy import (
    Column,
    String as SAString,
    Integer as SAInteger,
    Boolean as SABoolean,
    Enum as SAEnum,
    ForeignKey as SAFK,
    ForeignKeyConstraint,
    Index,
    Numeric as SANumeric,
    Date as SADate,
    Text as SAText,
)
from sqlalchemy.orm import backref

from core.orm.model import (
    BaseModel,
    Mapped,
    mapped_column,
    relationship,
    Integer,
    String,
    Boolean,
    Date,
    Numeric,
    Enum,
    ForeignKey,
)
from base.config import BaseTables
from base.models.geo_model import CountryModel
from base.models.branch_model import BranchModel
from ..config import AccountingTables


class TypeCompte(str, enum.Enum):
    ACTIF = "ACTIF"
    PASSIF = "PASSIF"


class SensEcriture(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class FiscalYearStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class AccountingQueueStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


# --- 1. GÉOGRAPHIE COMPTABLE & PLANS COMPTABLES ---

class AccountClassModel(BaseModel):
    __tablename__ = AccountingTables.ACCOUNT_CLASSES

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    chart_id: Mapped[str] = mapped_column(String(20), ForeignKey(f"{AccountingTables.CHART_OF_ACCOUNTS}.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    chart: Mapped["ChartOfAccountsModel"] = relationship("ChartOfAccountsModel", back_populates="classes", lazy="selectin")
    accounts: Mapped[List["AccountModel"]] = relationship("AccountModel", back_populates="account_class", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "chart_id": self.chart_id,
            "name": self.name,
            "order": self.order,
        }


class AccountModel(BaseModel):
    __tablename__ = AccountingTables.ACCOUNTS

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    chart_id: Mapped[str] = mapped_column(String(20), ForeignKey(f"{AccountingTables.CHART_OF_ACCOUNTS}.id"), primary_key=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type_compte: Mapped[TypeCompte] = mapped_column(Enum(TypeCompte), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_result_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    class_code: Mapped[str] = mapped_column(String(10), nullable=False)
    hq_account_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    chart: Mapped["ChartOfAccountsModel"] = relationship("ChartOfAccountsModel", back_populates="accounts", lazy="selectin", overlaps="account_class,accounts")
    account_class: Mapped["AccountClassModel"] = relationship("AccountClassModel", back_populates="accounts", lazy="selectin", overlaps="chart,accounts")
    hq_account: Mapped[Optional["AccountModel"]] = relationship(
        "AccountModel",
        remote_side=[code],
        primaryjoin="and_(AccountModel.hq_account_code==AccountModel.code, AccountModel.chart_id=='IFRS_HQ')",
        foreign_keys=[hq_account_code],
        lazy="selectin",
        post_update=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['class_code', 'chart_id'],
            [f'{AccountingTables.ACCOUNT_CLASSES}.code', f'{AccountingTables.ACCOUNT_CLASSES}.chart_id']
        ),
        Index('idx_account_chart_order', 'chart_id', 'order'),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "chart_id": self.chart_id,
            "name": self.name,
            "type_compte": self.type_compte.value if hasattr(self.type_compte, "value") else str(self.type_compte),
            "order": self.order,
            "is_result_account": self.is_result_account,
            "class_code": self.class_code,
            "hq_account_code": self.hq_account_code,
        }


class ChartOfAccountsModel(BaseModel):
    __tablename__ = AccountingTables.CHART_OF_ACCOUNTS

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # Ex: "SYSCOHADA_2026", "IFRS_HQ"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    zones: Mapped[List["ZoneModel"]] = relationship("ZoneModel", back_populates="chart", lazy="selectin")
    classes: Mapped[List["AccountClassModel"]] = relationship("AccountClassModel", back_populates="chart", cascade="all, delete-orphan", lazy="selectin")
    accounts: Mapped[List["AccountModel"]] = relationship("AccountModel", back_populates="chart", cascade="all, delete-orphan", lazy="selectin", overlaps="account_class,accounts,chart")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_active": self.is_active,
        }


class ZoneModel(BaseModel):
    __tablename__ = AccountingTables.ZONES

    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # Ex: "CEMAC", "UEMOA", "UE"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    chart_id: Mapped[str] = mapped_column(String(20), ForeignKey(f"{AccountingTables.CHART_OF_ACCOUNTS}.id"), nullable=False)

    chart: Mapped["ChartOfAccountsModel"] = relationship("ChartOfAccountsModel", back_populates="zones", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "chart_id": self.chart_id,
        }


# Extension dynamique du modèle CountryModel du module de base
if not hasattr(CountryModel, 'zone_code'):
    CountryModel.zone_code = Column(SAString(10), SAFK(f"{AccountingTables.ZONES}.code"), nullable=True)
    CountryModel.zone = relationship("ZoneModel", backref=backref("countries", lazy="selectin"), lazy="selectin")

# Extension dynamique du modèle BranchModel pour la comptabilité
if not hasattr(BranchModel, 'chart_id'):
    @property
    def chart_id(self):
        if hasattr(self, 'city_ref') and self.city_ref and self.city_ref.region and self.city_ref.region.country:
            country_obj = self.city_ref.region.country
            if hasattr(country_obj, 'zone') and country_obj.zone:
                return country_obj.zone.chart_id
        return "SYSCOHADA_2026"  # Défaut fallback
    BranchModel.chart_id = chart_id

if not hasattr(BranchModel, 'local_currency'):
    @property
    def local_currency(self):
        return self.currency_code or "XAF"
    BranchModel.local_currency = local_currency


# --- 2. PIÈCES ET LIGNES D'ÉCRITURES COMPTABLES & EXERCICES FISCAUX ---

class JournalEntryModel(BaseModel):
    __tablename__ = AccountingTables.JOURNAL_ENTRIES

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # Dates de traçabilité & rattrapage rétrospectif
    date: Mapped[PyDate] = mapped_column(Date, nullable=False)                         # Date réelle de la transaction
    created_at: Mapped[PyDate] = mapped_column(Date, default=PyDate.today, nullable=False) # Date d'enregistrement en BDD
    
    journal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    agency_id: Mapped[str] = mapped_column(String(100), ForeignKey(f"{BaseTables.COMPANY_BRANCHES}.branch_id"), nullable=False)
    fiscal_year_id: Mapped[int] = mapped_column(Integer, ForeignKey(f"{AccountingTables.FISCAL_YEARS}.id"), nullable=False)

    fiscal_year: Mapped["FiscalYearModel"] = relationship("FiscalYearModel", back_populates="entries", lazy="selectin")
    items: Mapped[List["JournalItemModel"]] = relationship("JournalItemModel", back_populates="entry", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entry_number": self.entry_number,
            "date": self.date.isoformat() if self.date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "journal_code": self.journal_code,
            "description": self.description,
            "agency_id": self.agency_id,
            "fiscal_year_id": self.fiscal_year_id,
            "items": [item.to_dict() for item in self.items],
        }


class FiscalYearModel(BaseModel):
    __tablename__ = AccountingTables.FISCAL_YEARS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Rattaché à la société / organisation
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)     # Ex: "FY-2026"
    date_start: Mapped[PyDate] = mapped_column(Date, nullable=False)                # Ex: 2026-01-01
    date_end: Mapped[PyDate] = mapped_column(Date, nullable=False)                  # Ex: 2026-12-31
    status: Mapped[FiscalYearStatus] = mapped_column(Enum(FiscalYearStatus), default=FiscalYearStatus.OPEN, nullable=False)

    entries: Mapped[List["JournalEntryModel"]] = relationship("JournalEntryModel", back_populates="fiscal_year", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "code": self.code,
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
        }


class JournalItemModel(BaseModel):
    __tablename__ = AccountingTables.JOURNAL_ITEMS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey(f"{AccountingTables.JOURNAL_ENTRIES}.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(20), nullable=False)

    # Devises Locales
    debit: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0, nullable=False)
    credit: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0, nullable=False)
    local_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Conversion Devise Siège (Consolidation)
    hq_debit: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0, nullable=False)
    hq_credit: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0, nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(12, 6), default=1.0, nullable=False)

    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    entry: Mapped["JournalEntryModel"] = relationship("JournalEntryModel", back_populates="items", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "account_code": self.account_code,
            "debit": float(self.debit) if self.debit is not None else 0.0,
            "credit": float(self.credit) if self.credit is not None else 0.0,
            "local_currency": self.local_currency,
            "hq_debit": float(self.hq_debit) if self.hq_debit is not None else 0.0,
            "hq_credit": float(self.hq_credit) if self.hq_credit is not None else 0.0,
            "exchange_rate": float(self.exchange_rate) if self.exchange_rate is not None else 1.0,
            "label": self.label,
        }


# --- 4. CONFIGURATION OPCODES ---

class OperationCodeModel(BaseModel):
    __tablename__ = AccountingTables.OPERATION_CODES

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    module_owner: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    rules: Mapped[List["AccountingRuleModel"]] = relationship("AccountingRuleModel", back_populates="operation_code", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "module_owner": self.module_owner,
            "description": self.description,
            "rules": [rule.to_dict() for rule in self.rules],
        }


class AccountingRuleModel(BaseModel):
    __tablename__ = AccountingTables.ACCOUNTING_RULES

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opcode: Mapped[str] = mapped_column(String(50), ForeignKey(f"{AccountingTables.OPERATION_CODES}.code"), nullable=False)
    chart_id: Mapped[str] = mapped_column(String(20), ForeignKey(f"{AccountingTables.CHART_OF_ACCOUNTS}.id"), nullable=False)
    sens: Mapped[SensEcriture] = mapped_column(Enum(SensEcriture), nullable=False)
    account_code: Mapped[str] = mapped_column(String(20), nullable=False)

    operation_code: Mapped["OperationCodeModel"] = relationship("OperationCodeModel", back_populates="rules", lazy="selectin")

    __table_args__ = (
        ForeignKeyConstraint(
            ['account_code', 'chart_id'],
            [f'{AccountingTables.ACCOUNTS}.code', f'{AccountingTables.ACCOUNTS}.chart_id']
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "opcode": self.opcode,
            "chart_id": self.chart_id,
            "sens": self.sens.value if hasattr(self.sens, "value") else str(self.sens),
            "account_code": self.account_code,
        }


# --- 5. FILE D'ATTENTE & REGISTRE D'ÉVÉNEMENTS ---

class AccountingQueueModel(BaseModel):
    __tablename__ = AccountingTables.ACCOUNTING_QUEUE

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opcode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    origin_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(SAText, nullable=True)

    status: Mapped[AccountingQueueStatus] = mapped_column(Enum(AccountingQueueStatus), default=AccountingQueueStatus.PENDING, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(SAText, nullable=True)

    journal_entry_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey(f"{AccountingTables.JOURNAL_ENTRIES}.id"), nullable=True)
    created_at: Mapped[PyDate] = mapped_column(Date, default=PyDate.today, nullable=False)
    processed_at: Mapped[Optional[PyDate]] = mapped_column(Date, nullable=True)
    agency_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    journal_entry: Mapped[Optional["JournalEntryModel"]] = relationship("JournalEntryModel", lazy="selectin")

    def to_dict(self) -> dict:
        import json
        payload_dict = {}
        if self.payload:
            try:
                payload_dict = json.loads(self.payload)
            except Exception:
                payload_dict = {"raw": self.payload}

        return {
            "id": self.id,
            "opcode": self.opcode,
            "origin_module": self.origin_module,
            "event_name": self.event_name,
            "payload": payload_dict,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "attempts": self.attempts,
            "last_error": self.last_error,
            "journal_entry_id": self.journal_entry_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "agency_id": self.agency_id,
        }


class AccountingEventRegistryModel(BaseModel):
    __tablename__ = AccountingTables.EVENT_REGISTRATION

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_module: Mapped[str] = mapped_column(String(50), nullable=False)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    opcode: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index('idx_event_reg_unique', 'origin_module', 'event_name', 'opcode', unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "origin_module": self.origin_module,
            "event_name": self.event_name,
            "opcode": self.opcode,
            "description": self.description,
            "is_active": self.is_active,
        }

