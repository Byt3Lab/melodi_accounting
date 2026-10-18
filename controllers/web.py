import json
from datetime import datetime, date
from core.routing import Request, Response
from core.routing.decorator import require_permission
from core.page_builder import Page, Component
from base.components import admin_layout
from base.repositories.branch_repository import BranchRepository
from modules.melodi_accounting.services.accounting_service import AccountingService
from modules.melodi_accounting.models.accounting import (
    JournalEntryModel,
    JournalItemModel,
    OperationCodeModel,
    AccountingRuleModel,
    TypeCompte,
    SensEcriture,
)
from sqlalchemy import select, func


class AccountingWebController:

    @staticmethod
    @require_permission("accounting:read")
    async def admin_dashboard(request: Request, response: Response):
        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            accounts = await AccountingService.get_all_accounts(session, chart_id="SYSCOHADA_2026")
            
            stmt_entries = select(JournalEntryModel).order_by(JournalEntryModel.id.desc()).limit(10)
            res_entries = await session.execute(stmt_entries)
            recent_entries = list(res_entries.scalars().all())

            stmt_count_entries = select(func.count(JournalEntryModel.id))
            res_count = await session.execute(stmt_count_entries)
            total_entries = res_count.scalar() or 0

        content = Component(module_name="melodi_accounting", name="admin_dashboard", context={
            "charts": charts,
            "total_accounts": len(accounts),
            "total_entries": total_entries,
            "recent_entries": recent_entries,
        })
        page = Page("Comptabilité - Tableau de Bord", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_charts(request: Request, response: Response):
        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "create_chart":
                    await AccountingService.create_chart_of_accounts(
                        session,
                        chart_id=form.get("id"),
                        name=form.get("name")
                    )
                elif action_type == "create_zone":
                    await AccountingService.create_zone(
                        session,
                        code=form.get("code"),
                        name=form.get("name"),
                        chart_id=form.get("chart_id")
                    )
                elif action_type == "link_country_zone":
                    await AccountingService.link_country_to_zone(
                        session,
                        country_code_iso=form.get("country_code_iso"),
                        zone_code=form.get("zone_code")
                    )
            return response.redirect("/admin/melodi_accounting/charts")

        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            
            from modules.melodi_accounting.models.accounting import ZoneModel
            from base.models.geo_model import CountryModel
            stmt_zones = select(ZoneModel)
            res_zones = await session.execute(stmt_zones)
            zones = list(res_zones.scalars().all())

            stmt_countries = select(CountryModel).order_by(CountryModel.name)
            res_countries = await session.execute(stmt_countries)
            countries = list(res_countries.scalars().all())

            branch_repo = BranchRepository(request.module)
            branches = await branch_repo.get_all_branches()

            hq_chart_id = await AccountingService.get_headquarters_chart_id(session)

        content = Component(module_name="melodi_accounting", name="admin_charts", context={
            "charts": charts,
            "zones": zones,
            "countries": countries,
            "branches": branches,
            "hq_chart_id": hq_chart_id,
        })
        page = Page("Plans Comptables & Zones", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:write")
    async def admin_mapping_hq(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"
        search = request.query.get("search")

        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "save_mapping":
                    acc_code = form.get("account_code")
                    hq_code = form.get("hq_account_code")
                    await AccountingService.map_account_to_hq(session, chart_id=chart_id, account_code=acc_code, hq_account_code=hq_code)
            return response.redirect(f"/admin/melodi_accounting/mapping_hq?chart_id={chart_id}")

        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            hq_chart_id = await AccountingService.get_headquarters_chart_id(session)
            
            local_accounts = await AccountingService.get_all_accounts(session, chart_id=chart_id, search=search)
            hq_accounts = await AccountingService.get_all_accounts(session, chart_id=hq_chart_id)

        content = Component(module_name="melodi_accounting", name="admin_mapping_hq", context={
            "charts": charts,
            "active_chart_id": chart_id,
            "hq_chart_id": hq_chart_id,
            "local_accounts": local_accounts,
            "hq_accounts": hq_accounts,
            "search": search,
        })
        page = Page("Mapping Comptable Siège", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_classes(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"

        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "create_class":
                    await AccountingService.create_account_class(
                        session,
                        chart_id=form.get("chart_id") or chart_id,
                        code=form.get("code"),
                        name=form.get("name"),
                        order=form.get("order") or 1
                    )
            return response.redirect(f"/admin/melodi_accounting/classes?chart_id={chart_id}")

        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            classes = await AccountingService.get_account_classes(session, chart_id=chart_id)

        content = Component(module_name="melodi_accounting", name="admin_classes", context={
            "charts": charts,
            "active_chart_id": chart_id,
            "classes": classes,
        })
        page = Page("Classes de Comptes", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_accounts(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"
        class_code = request.query.get("class_code")
        type_compte = request.query.get("type_compte")
        search = request.query.get("search")

        if request.method == "POST":
            form = request.form
            async with request.module.app.db.get_session() as session:
                await AccountingService.create_account(session, {
                    "code": form.get("code"),
                    "chart_id": form.get("chart_id") or chart_id,
                    "name": form.get("name"),
                    "type_compte": form.get("type_compte"),
                    "order": form.get("order"),
                    "is_result_account": form.get("is_result_account") == "on",
                    "class_code": form.get("class_code"),
                    "hq_account_code": form.get("hq_account_code") or None,
                })
            return response.redirect(f"/admin/melodi_accounting/accounts?chart_id={chart_id}")

        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            accounts = await AccountingService.get_all_accounts(
                session,
                chart_id=chart_id,
                class_code=class_code,
                type_compte=type_compte,
                search=search
            )

        content = Component(module_name="melodi_accounting", name="admin_accounts", context={
            "charts": charts,
            "active_chart_id": chart_id,
            "accounts": accounts,
            "active_class": class_code,
            "active_type": type_compte,
            "search": search,
        })
        page = Page("Plan de Comptes", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:write")
    async def admin_create_account(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"

        if request.method == "POST":
            form = request.form
            async with request.module.app.db.get_session() as session:
                await AccountingService.create_account(session, {
                    "code": form.get("code"),
                    "chart_id": form.get("chart_id") or chart_id,
                    "name": form.get("name"),
                    "type_compte": form.get("type_compte"),
                    "order": form.get("order"),
                    "is_result_account": form.get("is_result_account") == "on",
                    "class_code": form.get("class_code"),
                    "hq_account_code": form.get("hq_account_code") or None,
                })
            return response.redirect(f"/admin/melodi_accounting/accounts?chart_id={chart_id}")

        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)

        content = Component(module_name="melodi_accounting", name="admin_create_account", context={
            "charts": charts,
            "active_chart_id": chart_id,
        })
        page = Page("Ajouter un Compte", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_entries(request: Request, response: Response):
        branch_repo = BranchRepository(request.module)
        branches = await branch_repo.get_all_branches()

        if request.method == "POST":
            form = request.form
            raw_items = form.get("items_json")
            items = json.loads(raw_items) if raw_items else []
            
            agency_id = form.get("agency_id") or (branches[0].branch_id if branches else "default")
            journal_code = form.get("journal_code") or "VT"
            description = form.get("description") or "Écriture manuelle"

            async with request.module.app.db.get_session() as session:
                await AccountingService.post_journal_entry(
                    session=session,
                    agency_id=agency_id,
                    journal_code=journal_code,
                    description=description,
                    items=items
                )
            return response.redirect("/admin/melodi_accounting/entries")

        async with request.module.app.db.get_session() as session:
            stmt = select(JournalEntryModel).order_by(JournalEntryModel.id.desc())
            res = await session.execute(stmt)
            entries = list(res.scalars().all())
            accounts = await AccountingService.get_all_accounts(session, chart_id="SYSCOHADA_2026")

        content = Component(module_name="melodi_accounting", name="admin_entries", context={
            "entries": entries,
            "branches": branches,
            "accounts": accounts,
        })
        page = Page("Pièces & Écritures Comptables", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:post")
    async def admin_create_entry(request: Request, response: Response):
        branch_repo = BranchRepository(request.module)
        branches = await branch_repo.get_all_branches()

        if request.method == "POST":
            form = request.form
            raw_items = form.get("items_json")
            items = json.loads(raw_items) if raw_items else []
            
            agency_id = form.get("agency_id") or (branches[0].branch_id if branches else "default")
            journal_code = form.get("journal_code") or "VT"
            description = form.get("description") or "Écriture manuelle"
            entry_date_raw = form.get("entry_date")
            entry_date = datetime.strptime(entry_date_raw, "%Y-%m-%d").date() if entry_date_raw else date.today()

            async with request.module.app.db.get_session() as session:
                await AccountingService.post_journal_entry(
                    session=session,
                    agency_id=agency_id,
                    journal_code=journal_code,
                    description=description,
                    items=items,
                    entry_date=entry_date
                )
            return response.redirect("/admin/melodi_accounting/entries")

        async with request.module.app.db.get_session() as session:
            accounts = await AccountingService.get_all_accounts(session, chart_id="SYSCOHADA_2026")

        content = Component(module_name="melodi_accounting", name="admin_create_entry", context={
            "branches": branches,
            "accounts": accounts,
            "today_date": date.today().isoformat(),
        })
        page = Page("Nouvelle Pièce Comptable", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_fiscal_years(request: Request, response: Response):
        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "create_fy":
                    code = form.get("code")
                    d_start = datetime.strptime(form.get("date_start"), "%Y-%m-%d").date()
                    d_end = datetime.strptime(form.get("date_end"), "%Y-%m-%d").date()
                    await AccountingService.create_fiscal_year(session, code=code, date_start=d_start, date_end=d_end)
                elif form.get("fiscal_year_id") and form.get("status"):
                    fy_id = int(form.get("fiscal_year_id"))
                    st = form.get("status")
                    await AccountingService.update_fiscal_year_status(session, fy_id=fy_id, status=st)
            return response.redirect("/admin/melodi_accounting/fiscal_years")

        async with request.module.app.db.get_session() as session:
            fiscal_years = await AccountingService.get_all_fiscal_years(session)

        content = Component(module_name="melodi_accounting", name="admin_fiscal_years", context={
            "fiscal_years": fiscal_years,
        })
        page = Page("Exercices Fiscaux", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_grand_livre(request: Request, response: Response):
        account_code = request.query.get("account_code")
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"

        items = []
        selected_account = None
        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            accounts = await AccountingService.get_all_accounts(session, chart_id=chart_id)
            
            if account_code:
                stmt = select(JournalItemModel).where(
                    JournalItemModel.account_code == account_code
                ).order_by(JournalItemModel.id.asc())
                res = await session.execute(stmt)
                items = list(res.scalars().all())

                for acc in accounts:
                    if acc.code == account_code:
                        selected_account = acc
                        break

        tot_debit = sum(float(i.debit) for i in items)
        tot_credit = sum(float(i.credit) for i in items)
        sold = tot_debit - tot_credit

        content = Component(module_name="melodi_accounting", name="admin_grand_livre", context={
            "charts": charts,
            "accounts": accounts,
            "active_chart_id": chart_id,
            "account_code": account_code,
            "selected_account": selected_account,
            "items": items,
            "tot_debit": tot_debit,
            "tot_credit": tot_credit,
            "sold": sold,
        })
        page = Page("Grand Livre des Comptes", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_opcodes(request: Request, response: Response):
        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "add_opcode":
                    await AccountingService.register_opcode(
                        session,
                        code=form.get("code"),
                        module_owner=form.get("module_owner"),
                        description=form.get("description")
                    )
                elif action_type == "add_rule":
                    await AccountingService.create_accounting_rule(
                        session,
                        opcode=form.get("opcode"),
                        chart_id=form.get("chart_id"),
                        sens=form.get("sens"),
                        account_code=form.get("account_code")
                    )
            return response.redirect("/admin/melodi_accounting/opcodes")

        async with request.module.app.db.get_session() as session:
            stmt_op = select(OperationCodeModel)
            res_op = await session.execute(stmt_op)
            opcodes = list(res_op.scalars().all())

            charts = await AccountingService.get_all_charts(session)
            accounts = await AccountingService.get_all_accounts(session, chart_id="SYSCOHADA_2026")
            registered_events = await AccountingService.get_registered_accounting_events(session)

        content = Component(module_name="melodi_accounting", name="admin_opcodes", context={
            "opcodes": opcodes,
            "charts": charts,
            "accounts": accounts,
            "registered_events": registered_events,
        })
        page = Page("Règles & OpCodes Comptables", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_balance(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"
        async with request.module.app.db.get_session() as session:
            charts = await AccountingService.get_all_charts(session)
            balance_data = await AccountingService.get_trial_balance(session, chart_id=chart_id)

        tot_debit = sum(b["total_debit"] for b in balance_data)
        tot_credit = sum(b["total_credit"] for b in balance_data)
        tot_sold_debit = sum(b["sold_debit"] for b in balance_data)
        tot_sold_credit = sum(b["sold_credit"] for b in balance_data)

        content = Component(module_name="melodi_accounting", name="admin_balance", context={
            "charts": charts,
            "active_chart_id": chart_id,
            "balance": balance_data,
            "tot_debit": tot_debit,
            "tot_credit": tot_credit,
            "tot_sold_debit": tot_sold_debit,
            "tot_sold_credit": tot_sold_credit,
        })
        page = Page("Balance Générale des Comptes", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_consolidation(request: Request, response: Response):
        async with request.module.app.db.get_session() as session:
            consolidation_data = await AccountingService.get_consolidated_balance(session)

        content = Component(module_name="melodi_accounting", name="admin_consolidation", context=consolidation_data)
        page = Page("Consolidation Comptable Siège", admin_layout(content))
        return await response.render_page(page)

    @staticmethod
    @require_permission("accounting:read")
    async def admin_queue(request: Request, response: Response):
        status_filter = request.query.get("status")
        search = request.query.get("search")

        if request.method == "POST":
            form = request.form
            action_type = form.get("action_type")
            async with request.module.app.db.get_session() as session:
                if action_type == "retry_item" and form.get("queue_id"):
                    await AccountingService.retry_queue_item(session, int(form.get("queue_id")), module_instance=request.module)
                elif action_type == "retry_all":
                    await AccountingService.retry_all_failed_queue(session, module_instance=request.module)
            return response.redirect(f"/admin/melodi_accounting/queue?status={status_filter or ''}&search={search or ''}")

        async with request.module.app.db.get_session() as session:
            queue_items = await AccountingService.get_queue_items(session, status=status_filter, search=search)
            all_items = await AccountingService.get_queue_items(session)

            total_count = len(all_items)
            pending_count = sum(1 for item in all_items if str(getattr(item.status, "value", item.status)) == "PENDING")
            processed_count = sum(1 for item in all_items if str(getattr(item.status, "value", item.status)) == "PROCESSED")
            failed_count = sum(1 for item in all_items if str(getattr(item.status, "value", item.status)) == "FAILED")

        content = Component(module_name="melodi_accounting", name="admin_queue", context={
            "queue_items": queue_items,
            "status_filter": status_filter,
            "search": search,
            "total_count": total_count,
            "pending_count": pending_count,
            "processed_count": processed_count,
            "failed_count": failed_count,
        })
        page = Page("File d'Attente Comptable", admin_layout(content))
        return await response.render_page(page)

