from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from modules.melodi_accounting.models.accounting import (
    ChartOfAccountsModel,
    ZoneModel,
    AccountClassModel,
    AccountModel,
    JournalEntryModel,
    JournalItemModel,
    OperationCodeModel,
    AccountingRuleModel,
    FiscalYearModel,
    FiscalYearStatus,
    AccountingQueueModel,
    AccountingQueueStatus,
    AccountingEventRegistryModel,
    TypeCompte,
    SensEcriture,
)


class AccountingService:

    @staticmethod
    async def seed_default_charts(session: AsyncSession):
        """Initialise les plans comptables par défaut et les classes de comptes."""
        # 1. Chart of Accounts
        stmt = select(ChartOfAccountsModel).where(ChartOfAccountsModel.id == "SYSCOHADA_2026")
        res = await session.execute(stmt)
        syscohada = res.scalar_one_or_none()

        if not syscohada:
            syscohada = ChartOfAccountsModel(
                id="SYSCOHADA_2026",
                name="Plan Comptable SYSCOHADA Révisé 2026",
                is_active=True,
                is_headquarters=False
            )
            session.add(syscohada)

        stmt_hq = select(ChartOfAccountsModel).where(ChartOfAccountsModel.id == "IFRS_HQ")
        res_hq = await session.execute(stmt_hq)
        ifrs_hq = res_hq.scalar_one_or_none()

        if not ifrs_hq:
            ifrs_hq = ChartOfAccountsModel(
                id="IFRS_HQ",
                name="Plan Comptable International Siège (IFRS)",
                is_active=True,
                is_headquarters=True
            )
            session.add(ifrs_hq)

        await session.flush()

        # 2. Zones
        zones_data = [
            ("CEMAC", "Zone Afrique Centrale (CEMAC)", "SYSCOHADA_2026"),
            ("UEMOA", "Zone Afrique de l'Ouest (UEMOA)", "SYSCOHADA_2026"),
            ("HQ_ZONE", "Zone Siège International", "IFRS_HQ"),
        ]
        for z_code, z_name, z_chart in zones_data:
            stmt_z = select(ZoneModel).where(ZoneModel.code == z_code)
            res_z = await session.execute(stmt_z)
            if not res_z.scalar_one_or_none():
                session.add(ZoneModel(code=z_code, name=z_name, chart_id=z_chart))

        # 3. Account Classes for SYSCOHADA
        syscohada_classes = [
            ("1", "Comptes de ressources durables", 100),
            ("2", "Comptes d'actif immobilisé", 200),
            ("3", "Comptes de stocks", 300),
            ("4", "Comptes de tiers", 400),
            ("5", "Comptes de trésorerie", 500),
            ("6", "Comptes de charges", 600),
            ("7", "Comptes de produits", 700),
        ]
        for c_code, c_name, c_order in syscohada_classes:
            stmt_c = select(AccountClassModel).where(
                AccountClassModel.code == c_code,
                AccountClassModel.chart_id == "SYSCOHADA_2026"
            )
            res_c = await session.execute(stmt_c)
            if not res_c.scalar_one_or_none():
                session.add(AccountClassModel(code=c_code, chart_id="SYSCOHADA_2026", name=c_name, order=c_order))

        # Account Classes for IFRS_HQ
        ifrs_classes = [
            ("1", "Assets (Non-Current & Current)", 100),
            ("2", "Liabilities", 200),
            ("3", "Equity", 300),
            ("4", "Revenue & Income", 400),
            ("5", "Expenses", 500),
        ]
        for c_code, c_name, c_order in ifrs_classes:
            stmt_c = select(AccountClassModel).where(
                AccountClassModel.code == c_code,
                AccountClassModel.chart_id == "IFRS_HQ"
            )
            res_c = await session.execute(stmt_c)
            if not res_c.scalar_one_or_none():
                session.add(AccountClassModel(code=c_code, chart_id="IFRS_HQ", name=c_name, order=c_order))

        await session.flush()

        # 4. Standard Accounts for SYSCOHADA_2026
        accounts_data = [
            ("101000", "SYSCOHADA_2026", "Capital social", TypeCompte.PASSIF, 101, False, "1"),
            ("131000", "SYSCOHADA_2026", "Résultat net de l'exercice", TypeCompte.PASSIF, 131, True, "1"),
            ("211000", "SYSCOHADA_2026", "Bâtiments et installations", TypeCompte.ACTIF, 211, False, "2"),
            ("311000", "SYSCOHADA_2026", "Marchandises en stock", TypeCompte.ACTIF, 311, False, "3"),
            ("401100", "SYSCOHADA_2026", "Fournisseurs locaux", TypeCompte.PASSIF, 401, False, "4"),
            ("411100", "SYSCOHADA_2026", "Clients ordinaires", TypeCompte.ACTIF, 411, False, "4"),
            ("521100", "SYSCOHADA_2026", "Banques locales", TypeCompte.ACTIF, 521, False, "5"),
            ("571100", "SYSCOHADA_2026", "Caisse principale", TypeCompte.ACTIF, 571, False, "5"),
            ("601100", "SYSCOHADA_2026", "Achats de marchandises", TypeCompte.ACTIF, 601, False, "6"),
            ("701100", "SYSCOHADA_2026", "Ventes de marchandises", TypeCompte.PASSIF, 701, False, "7"),
        ]
        for acc_code, acc_chart, acc_name, acc_type, acc_order, acc_res, acc_class in accounts_data:
            stmt_a = select(AccountModel).where(
                AccountModel.code == acc_code,
                AccountModel.chart_id == acc_chart
            )
            res_a = await session.execute(stmt_a)
            if not res_a.scalar_one_or_none():
                session.add(AccountModel(
                    code=acc_code,
                    chart_id=acc_chart,
                    name=acc_name,
                    type_compte=acc_type,
                    order=acc_order,
                    is_result_account=acc_res,
                    class_code=acc_class
                ))

        # Default OpCodes
        opcodes_data = [
            ("POS_CASH_SALE", "POS", "Vente directe au comptoir par caisse"),
            ("TREASURY_TRANSFER", "TREASURY", "Transfert ou virement inter-caisses"),
            ("PAYROLL_SALARY", "PAYROLL", "Comptabilisation de la paie du personnel"),
        ]
        for op_code, op_owner, op_desc in opcodes_data:
            stmt_o = select(OperationCodeModel).where(OperationCodeModel.code == op_code)
            res_o = await session.execute(stmt_o)
            if not res_o.scalar_one_or_none():
                session.add(OperationCodeModel(code=op_code, module_owner=op_owner, description=op_desc))

        await session.flush()

        # Default Rules for POS_CASH_SALE under SYSCOHADA_2026
        rules_data = [
            ("POS_CASH_SALE", "SYSCOHADA_2026", SensEcriture.DEBIT, "571100"),
            ("POS_CASH_SALE", "SYSCOHADA_2026", SensEcriture.CREDIT, "701100"),
        ]
        for r_op, r_chart, r_sens, r_acc in rules_data:
            stmt_r = select(AccountingRuleModel).where(
                AccountingRuleModel.opcode == r_op,
                AccountingRuleModel.chart_id == r_chart,
                AccountingRuleModel.sens == r_sens,
                AccountingRuleModel.account_code == r_acc
            )
            res_r = await session.execute(stmt_r)
            if not res_r.scalar_one_or_none():
                session.add(AccountingRuleModel(
                    opcode=r_op,
                    chart_id=r_chart,
                    sens=r_sens,
                    account_code=r_acc
                ))

        await session.commit()

    @staticmethod
    async def get_all_charts(session: AsyncSession) -> List[ChartOfAccountsModel]:
        stmt = select(ChartOfAccountsModel).order_by(ChartOfAccountsModel.id)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_chart_of_accounts(session: AsyncSession, chart_id: str, name: str) -> ChartOfAccountsModel:
        chart = ChartOfAccountsModel(
            id=chart_id.strip(),
            name=name.strip(),
            is_active=True
        )
        session.add(chart)
        await session.commit()
        return chart

    @staticmethod
    async def create_zone(session: AsyncSession, code: str, name: str, chart_id: str) -> ZoneModel:
        zone = ZoneModel(
            code=code.strip(),
            name=name.strip(),
            chart_id=chart_id.strip()
        )
        session.add(zone)
        await session.commit()
    @staticmethod
    async def get_account_classes(session: AsyncSession, chart_id: str) -> List[AccountClassModel]:
        stmt = select(AccountClassModel).where(AccountClassModel.chart_id == chart_id).order_by(AccountClassModel.order, AccountClassModel.code)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_account_class(session: AsyncSession, chart_id: str, code: str, name: str, order: int) -> AccountClassModel:
        acc_class = AccountClassModel(
            chart_id=chart_id.strip(),
            code=code.strip(),
            name=name.strip(),
            order=int(order)
        )
        session.add(acc_class)
        await session.commit()
        return acc_class

    @staticmethod
    async def link_country_to_zone(session: AsyncSession, country_code_iso: str, zone_code: str) -> bool:
        from base.models.geo_model import CountryModel
        country = await session.get(CountryModel, country_code_iso)
        if not country:
            raise ValueError(f"Pays avec le code ISO '{country_code_iso}' introuvable")

        country.zone_code = zone_code
        await session.commit()
        return True

    @staticmethod
    async def get_headquarters_chart_id(session: AsyncSession) -> str:
        from base.models.branch_model import BranchModel, BranchCategoryModel, BranchCategoryRelModel
        from base.models.geo_model import CountryModel, CityModel, RegionModel

        # Chercher l'agence principale / siège
        stmt_hq = (
            select(BranchModel)
            .join(BranchCategoryRelModel, BranchModel.branch_id == BranchCategoryRelModel.branch_id)
            .join(BranchCategoryModel, BranchCategoryRelModel.branch_category_id == BranchCategoryModel.branch_category_id)
            .where(or_(
                func.lower(BranchCategoryModel.slug).in_(["hq", "headquarters", "siege", "head-office"]),
                func.lower(BranchCategoryModel.name).like("%siège%"),
                func.lower(BranchCategoryModel.name).like("%hq%")
            ))
        )
        res_hq = await session.execute(stmt_hq)
        hq_branch = res_hq.scalars().first()

        # Fallback si pas de catégorie siège explicite : première agence
        if not hq_branch:
            stmt_first = select(BranchModel).order_by(BranchModel.created_at.asc())
            res_first = await session.execute(stmt_first)
            hq_branch = res_first.scalars().first()

        if hq_branch:
            # Récupération du plan comptable de cette agence via sa zone
            if hq_branch.city_id:
                city = await session.get(CityModel, hq_branch.city_id)
                if city and city.region:
                    region = await session.get(RegionModel, city.region_id)
                    if region and region.country_id:
                        country = await session.get(CountryModel, region.country_id)
                        if country and country.zone and country.zone.chart_id:
                            return country.zone.chart_id

            if hq_branch.country:
                stmt_country = select(CountryModel).where(or_(
                    func.lower(CountryModel.code_iso) == hq_branch.country.lower(),
                    func.lower(CountryModel.name) == hq_branch.country.lower()
                ))
                res_c = await session.execute(stmt_country)
                country = res_c.scalar_one_or_none()
                if country and country.zone and country.zone.chart_id:
                    return country.zone.chart_id

        return "SYSCOHADA_2026"

    @staticmethod
    async def get_all_accounts(
        session: AsyncSession,
        chart_id: Optional[str] = None,
        class_code: Optional[str] = None,
        type_compte: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[AccountModel]:
        stmt = select(AccountModel).order_by(AccountModel.order, AccountModel.code)
        if chart_id:
            stmt = stmt.where(AccountModel.chart_id == chart_id)
        if class_code:
            stmt = stmt.where(AccountModel.class_code == class_code)
        if type_compte:
            stmt = stmt.where(AccountModel.type_compte == type_compte)
        if search:
            s = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(func.lower(AccountModel.name).like(s), func.lower(AccountModel.code).like(s)))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_account(session: AsyncSession, data: dict) -> AccountModel:
        code = str(data.get("code")).strip()
        chart_id = str(data.get("chart_id")).strip()
        name = str(data.get("name")).strip()
        type_compte = TypeCompte(data.get("type_compte"))
        order = int(data.get("order") or code[:3] or 100)
        is_result_account = bool(data.get("is_result_account", False))
        class_code = str(data.get("class_code") or code[0]).strip()
        hq_account_code = data.get("hq_account_code") or None

        account = AccountModel(
            code=code,
            chart_id=chart_id,
            name=name,
            type_compte=type_compte,
            order=order,
            is_result_account=is_result_account,
            class_code=class_code,
            hq_account_code=hq_account_code
        )
        session.add(account)
        await session.commit()
        return account

    @staticmethod
    async def map_account_to_hq(session: AsyncSession, chart_id: str, account_code: str, hq_account_code: Optional[str]) -> bool:
        stmt = select(AccountModel).where(
            AccountModel.chart_id == chart_id,
            AccountModel.code == account_code
        )
        res = await session.execute(stmt)
        acc = res.scalar_one_or_none()
        if not acc:
            raise ValueError(f"Compte {account_code} introuvable dans le plan {chart_id}")

        acc.hq_account_code = hq_account_code.strip() if hq_account_code else None
        await session.commit()
        return True

    @staticmethod
    async def register_opcode(session: AsyncSession, code: str, module_owner: str, description: str) -> OperationCodeModel:
        stmt = select(OperationCodeModel).where(OperationCodeModel.code == code)
        res = await session.execute(stmt)
        opcode = res.scalar_one_or_none()
        if not opcode:
            opcode = OperationCodeModel(code=code, module_owner=module_owner, description=description)
            session.add(opcode)
            await session.commit()
        return opcode

    @staticmethod
    async def create_accounting_rule(session: AsyncSession, opcode: str, chart_id: str, sens: str, account_code: str) -> AccountingRuleModel:
        sens_enum = SensEcriture(sens)
        rule = AccountingRuleModel(
            opcode=opcode,
            chart_id=chart_id,
            sens=sens_enum,
            account_code=account_code
        )
        session.add(rule)
        await session.commit()
        return rule

    @staticmethod
    async def get_or_create_fiscal_year_for_date(session: AsyncSession, op_date: date) -> FiscalYearModel:
        """
        Trouve l'exercice fiscal couvrant la date d'opération.
        Vérifie qu'il est au statut OPEN.
        S'il n'existe pas, en crée un automatiquement au statut OPEN.
        Si l'exercice est CLOSING ou CLOSED, lève une exception.
        """
        stmt = select(FiscalYearModel).where(
            FiscalYearModel.date_start <= op_date,
            FiscalYearModel.date_end >= op_date
        )
        res = await session.execute(stmt)
        fy = res.scalar_one_or_none()

        if not fy:
            year_val = op_date.year
            fy_code = f"FY-{year_val}"
            fy = FiscalYearModel(
                code=fy_code,
                date_start=date(year_val, 1, 1),
                date_end=date(year_val, 12, 31),
                status=FiscalYearStatus.OPEN
            )
            session.add(fy)
            await session.flush()

        if fy.status != FiscalYearStatus.OPEN and str(fy.status) != "OPEN":
            raise ValueError(f"L'exercice fiscal '{fy.code}' pour la date {op_date} est clôturé ou en cours de clôture ({fy.status.value if hasattr(fy.status, 'value') else fy.status}). Aucune écriture n'est autorisée.")

        return fy

    @staticmethod
    async def get_all_fiscal_years(session: AsyncSession) -> List[FiscalYearModel]:
        stmt = select(FiscalYearModel).order_by(FiscalYearModel.date_start.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_fiscal_year(session: AsyncSession, code: str, date_start: date, date_end: date, company_id: Optional[str] = None) -> FiscalYearModel:
        fy = FiscalYearModel(
            code=code,
            date_start=date_start,
            date_end=date_end,
            company_id=company_id,
            status=FiscalYearStatus.OPEN
        )
        session.add(fy)
        await session.commit()
        return fy

    @staticmethod
    async def update_fiscal_year_status(session: AsyncSession, fy_id: int, status: str) -> FiscalYearModel:
        fy = await session.get(FiscalYearModel, fy_id)
        if not fy:
            raise ValueError(f"Exercice fiscal {fy_id} introuvable")
        fy.status = FiscalYearStatus(status)
        await session.commit()
        return fy

    @staticmethod
    async def post_journal_entry(
        session: AsyncSession,
        agency_id: str,
        journal_code: str,
        description: str,
        items: List[dict],
        entry_date: Optional[date] = None
    ) -> JournalEntryModel:
        """
        Poste une pièce comptable en validant l'équilibre des débits et crédits,
        l'ouverture de l'exercice fiscal correspondant, et la traçabilité rétrospective.
        """
        if not entry_date:
            entry_date = date.today()

        # Contrôle de l'exercice fiscal (doit être OPEN)
        fy = await AccountingService.get_or_create_fiscal_year_for_date(session, entry_date)

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        item_models = []
        for item in items:
            deb = Decimal(str(item.get("debit", 0.0)))
            cred = Decimal(str(item.get("credit", 0.0)))
            rate = Decimal(str(item.get("exchange_rate", 1.0)))

            total_debit += deb
            total_credit += cred

            hq_deb = deb * rate
            hq_cred = cred * rate

            item_models.append(JournalItemModel(
                account_code=str(item.get("account_code")),
                debit=float(deb),
                credit=float(cred),
                local_currency=str(item.get("local_currency", "XAF")),
                hq_debit=float(hq_deb),
                hq_credit=float(hq_cred),
                exchange_rate=float(rate),
                label=item.get("label") or description
            ))

        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Écriture déséquilibrée : Total Débit ({total_debit}) != Total Crédit ({total_credit})")

        # Numéro de pièce unique
        num_stmt = select(func.coalesce(func.max(JournalEntryModel.id), 0))
        count_res = await session.execute(num_stmt)
        count_val = (count_res.scalar() or 0) + 1
        entry_number = f"ECR-{entry_date.strftime('%Y%m')}-{count_val:05d}"


        entry = JournalEntryModel(
            entry_number=entry_number,
            date=entry_date,
            created_at=date.today(),
            journal_code=journal_code,
            description=description,
            agency_id=agency_id,
            fiscal_year_id=fy.id,
            items=item_models
        )
        session.add(entry)
        await session.commit()
        return entry

    @staticmethod
    async def post_opcode_operation(
        session: AsyncSession,
        opcode: str,
        agency_id: str,
        chart_id: str,
        amount: float,
        description: str,
        journal_code: str = "VT",
        local_currency: str = "XAF",
        exchange_rate: float = 1.0,
        label: Optional[str] = None,
        entry_date: Optional[date] = None
    ) -> JournalEntryModel:
        """
        Transforme un OperationCode (OpCode) en pièce comptable selon les règles enregistrées pour un chart_id.
        Supporte les opérations rétrospectives via entry_date.
        """
        stmt = select(AccountingRuleModel).where(
            AccountingRuleModel.opcode == opcode,
            AccountingRuleModel.chart_id == chart_id
        )
        res = await session.execute(stmt)
        rules = list(res.scalars().all())

        if not rules:
            raise ValueError(f"Aucune règle comptable configurée pour l'OpCode '{opcode}' sur le plan '{chart_id}'")

        items = []
        for rule in rules:
            is_debit = (rule.sens == SensEcriture.DEBIT or str(rule.sens) == "DEBIT")
            items.append({
                "account_code": rule.account_code,
                "debit": amount if is_debit else 0.0,
                "credit": 0.0 if is_debit else amount,
                "local_currency": local_currency,
                "exchange_rate": exchange_rate,
                "label": label or description
            })

        return await AccountingService.post_journal_entry(
            session=session,
            agency_id=agency_id,
            journal_code=journal_code,
            description=description,
            items=items,
            entry_date=entry_date
        )

    @staticmethod
    async def get_trial_balance(session: AsyncSession, chart_id: str = "SYSCOHADA_2026") -> List[dict]:
        """
        Génère la balance générale des comptes triée par le champ 'order'.
        """
        accounts = await AccountingService.get_all_accounts(session, chart_id=chart_id)
        
        balance_list = []
        for acc in accounts:
            stmt = select(
                func.coalesce(func.sum(JournalItemModel.debit), 0.0).label("sum_debit"),
                func.coalesce(func.sum(JournalItemModel.credit), 0.0).label("sum_credit")
            ).where(JournalItemModel.account_code == acc.code)
            
            res = await session.execute(stmt)
            row = res.first()
            sum_debit = float(row.sum_debit) if row else 0.0
            sum_credit = float(row.sum_credit) if row else 0.0

            sold_debit = sum_debit - sum_credit if sum_debit >= sum_credit else 0.0
            sold_credit = sum_credit - sum_debit if sum_credit > sum_debit else 0.0

            balance_list.append({
                "account_code": acc.code,
                "account_name": acc.name,
                "class_code": acc.class_code,
                "type_compte": acc.type_compte.value if hasattr(acc.type_compte, "value") else str(acc.type_compte),
                "order": acc.order,
                "is_result_account": acc.is_result_account,
                "total_debit": sum_debit,
                "total_credit": sum_credit,
                "sold_debit": sold_debit,
                "sold_credit": sold_credit,
            })

        return balance_list

    @staticmethod
    async def get_consolidated_balance(session: AsyncSession) -> dict:
        """
        Génère la balance consolidée au niveau du Siège (HQ).
        Regroupe les données de tous les plans comptables locaux via le mapping hq_account_code.
        Pour le plan Siège lui-même, hq_account_code est son propre code de compte.
        """
        hq_chart_id = await AccountingService.get_headquarters_chart_id(session)
        hq_accounts = await AccountingService.get_all_accounts(session, chart_id=hq_chart_id)

        # Structure de données pour stocker la consolidation par compte Siège
        consolidated_map = {}
        for hq_acc in hq_accounts:
            consolidated_map[hq_acc.code] = {
                "account_code": hq_acc.code,
                "account_name": hq_acc.name,
                "class_code": hq_acc.class_code,
                "type_compte": hq_acc.type_compte.value if hasattr(hq_acc.type_compte, "value") else str(hq_acc.type_compte),
                "order": hq_acc.order,
                "total_debit": 0.0,
                "total_credit": 0.0,
                "mapped_local_accounts": []
            }

        # Récupération de tous les comptes de tous les plans
        all_accounts = await AccountingService.get_all_accounts(session)

        for acc in all_accounts:
            # Détermination du code compte Siège cible (auto-mapping si plan Siège ou si hq_account_code défini)
            target_hq_code = None
            if acc.chart_id == hq_chart_id:
                target_hq_code = acc.code
            elif acc.hq_account_code:
                target_hq_code = acc.hq_account_code

            # Somme des mouvements du compte local
            stmt = select(
                func.coalesce(func.sum(JournalItemModel.debit), 0.0).label("sum_debit"),
                func.coalesce(func.sum(JournalItemModel.credit), 0.0).label("sum_credit")
            ).where(JournalItemModel.account_code == acc.code)
            
            res = await session.execute(stmt)
            row = res.first()
            sum_deb = float(row.sum_debit) if row else 0.0
            sum_cred = float(row.sum_credit) if row else 0.0

            if target_hq_code and target_hq_code in consolidated_map:
                consolidated_map[target_hq_code]["total_debit"] += sum_deb
                consolidated_map[target_hq_code]["total_credit"] += sum_cred
                if sum_deb > 0 or sum_cred > 0:
                    consolidated_map[target_hq_code]["mapped_local_accounts"].append({
                        "chart_id": acc.chart_id,
                        "code": acc.code,
                        "name": acc.name,
                        "debit": sum_deb,
                        "credit": sum_cred
                    })

        consolidated_list = []
        tot_debit = 0.0
        tot_credit = 0.0

        for hq_code, item in sorted(consolidated_map.items(), key=lambda x: (x[1]["order"], x[1]["account_code"])):
            sum_debit = item["total_debit"]
            sum_credit = item["total_credit"]
            sold_debit = sum_debit - sum_credit if sum_debit >= sum_credit else 0.0
            sold_credit = sum_credit - sum_debit if sum_credit > sum_debit else 0.0

            item["sold_debit"] = sold_debit
            item["sold_credit"] = sold_credit
            consolidated_list.append(item)

            tot_debit += sum_debit
            tot_credit += sum_credit

        tot_sold_debit = tot_debit - tot_credit if tot_debit >= tot_credit else 0.0
        tot_sold_credit = tot_credit - tot_debit if tot_credit > tot_debit else 0.0

        return {
            "hq_chart_id": hq_chart_id,
            "consolidated_balance": consolidated_list,
            "tot_debit": tot_debit,
            "tot_credit": tot_credit,
            "tot_sold_debit": tot_sold_debit,
            "tot_sold_credit": tot_sold_credit,
        }

    # --- FILE D'ATTENTE & REGISTRE D'ÉVÉNEMENTS COMPTABLES ---

    @staticmethod
    async def register_accounting_event(
        session: AsyncSession,
        origin_module: str,
        event_name: str,
        opcode: str,
        description: str
    ) -> AccountingEventRegistryModel:
        await AccountingService.register_opcode(session, code=opcode, module_owner=origin_module, description=description)

        stmt = select(AccountingEventRegistryModel).where(
            AccountingEventRegistryModel.origin_module == origin_module,
            AccountingEventRegistryModel.event_name == event_name,
            AccountingEventRegistryModel.opcode == opcode
        )
        res = await session.execute(stmt)
        reg = res.scalar_one_or_none()
        if not reg:
            reg = AccountingEventRegistryModel(
                origin_module=origin_module,
                event_name=event_name,
                opcode=opcode,
                description=description,
                is_active=True
            )
            session.add(reg)
            await session.commit()
        return reg

    @staticmethod
    async def get_registered_accounting_events(session: AsyncSession) -> List[AccountingEventRegistryModel]:
        stmt = select(AccountingEventRegistryModel).where(AccountingEventRegistryModel.is_active == True)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def enqueue_accounting_operation(
        session: AsyncSession,
        origin_module: str,
        event_name: str,
        opcode: str,
        payload: dict,
        agency_id: Optional[str] = None
    ) -> AccountingQueueModel:
        import json
        payload_str = json.dumps(payload, default=str)
        queue_item = AccountingQueueModel(
            opcode=opcode,
            origin_module=origin_module,
            event_name=event_name,
            payload=payload_str,
            status=AccountingQueueStatus.PENDING,
            attempts=0,
            agency_id=agency_id or payload.get("agency_id")
        )
        session.add(queue_item)
        await session.commit()
        return queue_item

    @staticmethod
    async def process_queue_item(session: AsyncSession, queue_id: int, module_instance=None) -> AccountingQueueModel:
        import json
        stmt = select(AccountingQueueModel).where(AccountingQueueModel.id == queue_id)
        res = await session.execute(stmt)
        queue_item = res.scalar_one_or_none()
        if not queue_item:
            raise ValueError(f"Élément de file d'attente #{queue_id} introuvable")

        payload_dict = {}
        if queue_item.payload:
            try:
                payload_dict = json.loads(queue_item.payload)
            except Exception:
                payload_dict = {}

        try:
            opcode = queue_item.opcode
            agency_id = queue_item.agency_id or payload_dict.get("agency_id")
            chart_id = payload_dict.get("chart_id", "SYSCOHADA_2026")
            amount = float(payload_dict.get("amount", 0.0))
            description = payload_dict.get("description", f"Opération {opcode} via événement {queue_item.event_name}")
            journal_code = payload_dict.get("journal_code", "VT")
            local_currency = payload_dict.get("local_currency", "XAF")
            exchange_rate = float(payload_dict.get("exchange_rate", 1.0))
            label = payload_dict.get("label")
            entry_date_raw = payload_dict.get("entry_date") or payload_dict.get("date")
            entry_date = None
            if entry_date_raw:
                entry_date = datetime.strptime(str(entry_date_raw)[:10], "%Y-%m-%d").date()

            if not agency_id:
                raise ValueError("agency_id manquant dans les données de l'opération")
            if amount <= 0:
                raise ValueError(f"Montant invalide: {amount}")

            entry = await AccountingService.post_opcode_operation(
                session=session,
                opcode=opcode,
                agency_id=agency_id,
                chart_id=chart_id,
                amount=amount,
                description=description,
                journal_code=journal_code,
                local_currency=local_currency,
                exchange_rate=exchange_rate,
                label=label,
                entry_date=entry_date
            )

            queue_item.status = AccountingQueueStatus.PROCESSED
            queue_item.journal_entry_id = entry.id
            queue_item.processed_at = date.today()
            queue_item.last_error = None
            await session.commit()

            if module_instance:
                event_data = {
                    "queue_id": queue_item.id,
                    "status": "SUCCESS",
                    "origin_module": queue_item.origin_module,
                    "event_name": queue_item.event_name,
                    "opcode": queue_item.opcode,
                    "journal_entry_id": entry.id,
                    "entry_number": entry.entry_number,
                    "agency_id": entry.agency_id,
                    "payload": payload_dict
                }
                await module_instance.notify_event_listener("journal_entry_created", event_data)

        except Exception as e:
            try:
                await session.rollback()
                stmt = select(AccountingQueueModel).where(AccountingQueueModel.id == queue_id)
                res = await session.execute(stmt)
                queue_item = res.scalar_one_or_none()
                if queue_item:
                    queue_item.status = AccountingQueueStatus.FAILED
                    queue_item.attempts += 1
                    queue_item.last_error = str(e)
                    await session.commit()
            except Exception as rollback_err:
                print(f"Error during queue error handling: {rollback_err}")

            if module_instance:
                event_data = {
                    "queue_id": queue_id,
                    "status": "FAILED",
                    "origin_module": queue_item.origin_module if queue_item else "UNKNOWN",
                    "event_name": queue_item.event_name if queue_item else "UNKNOWN",
                    "opcode": queue_item.opcode if queue_item else "UNKNOWN",
                    "error_message": str(e),
                    "payload": payload_dict
                }
                await module_instance.notify_event_listener("journal_entry_failed", event_data)


        return queue_item

    @staticmethod
    async def get_queue_items(session: AsyncSession, status: Optional[str] = None, search: Optional[str] = None) -> List[AccountingQueueModel]:
        stmt = select(AccountingQueueModel).order_by(AccountingQueueModel.id.desc())
        if status and status.upper() in ["PENDING", "PROCESSED", "FAILED"]:
            stmt = stmt.where(AccountingQueueModel.status == AccountingQueueStatus(status.upper()))
        if search:
            s = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(
                func.lower(AccountingQueueModel.opcode).like(s),
                func.lower(AccountingQueueModel.origin_module).like(s),
                func.lower(AccountingQueueModel.event_name).like(s),
                func.lower(AccountingQueueModel.last_error).like(s),
            ))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def retry_queue_item(session: AsyncSession, queue_id: int, module_instance=None) -> AccountingQueueModel:
        return await AccountingService.process_queue_item(session, queue_id, module_instance)

    @staticmethod
    async def retry_all_failed_queue(session: AsyncSession, module_instance=None) -> int:
        stmt = select(AccountingQueueModel).where(AccountingQueueModel.status == AccountingQueueStatus.FAILED)
        res = await session.execute(stmt)
        failed_items = list(res.scalars().all())
        count = 0
        for item in failed_items:
            await AccountingService.process_queue_item(session, item.id, module_instance)
            count += 1
        return count

