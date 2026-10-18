from core.module import ApplicationModule, Permission
from modules.melodi_accounting.services.accounting_service import AccountingService
from modules.melodi_accounting.controllers.web import AccountingWebController
from modules.melodi_accounting.controllers.api import AccountingAPIController


class MelodiAccountingModule(ApplicationModule):

    def _get_permissions(self):
        return [
            Permission(self, "accounting:read", "Consulter le plan comptable, les pièces et les rapports financiers"),
            Permission(self, "accounting:write", "Gérer le plan comptable, créer des comptes et configurer les OpCodes"),
            Permission(self, "accounting:post", "Saisir et valider les pièces comptables"),
        ]

    async def run_dev_migrations(self):
        """Création automatique des tables et initialisation des référentiels par défaut."""
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
            AccountingQueueModel,
            AccountingEventRegistryModel,
        )

        await self.app.db.create_all([
            ChartOfAccountsModel,
            ZoneModel,
            AccountClassModel,
            AccountModel,
            FiscalYearModel,
            JournalEntryModel,
            JournalItemModel,
            OperationCodeModel,
            AccountingRuleModel,
            AccountingQueueModel,
            AccountingEventRegistryModel,
        ])

        from sqlalchemy import text
        from base.config import BaseTables
        from modules.melodi_accounting.config import AccountingTables
        async with self.app.db.get_session() as session:
            try:
                await session.execute(text(f"ALTER TABLE {BaseTables.GEO_COUNTRIES} ADD COLUMN IF NOT EXISTS zone_code VARCHAR(10);"))
                await session.execute(text(f"ALTER TABLE {AccountingTables.CHART_OF_ACCOUNTS} DROP COLUMN IF EXISTS is_headquarters;"))
                await session.commit()
            except Exception as e:
                print(f"Error running dev migrations for melodi_accounting:", e)

            await AccountingService.seed_default_charts(session)

    async def load(self):
        """Initialisation et démarrage du module comptable."""
        self.permissions = self._get_permissions()

        # Initialisation de la BDD et des données par défaut en mode debug
        if self.app.server.app.debug:
            await self.run_dev_migrations()

        # Restauration des abonnements aux événements enregistrés
        await self._restore_registered_event_listeners()

        # Enregistrement des routes Administration Web
        self.admin_router.add_route("", AccountingWebController.admin_dashboard, methods=["GET"])
        self.admin_router.add_route("/", AccountingWebController.admin_dashboard, methods=["GET"])
        self.admin_router.add_route("/charts", AccountingWebController.admin_charts, methods=["GET", "POST"])
        self.admin_router.add_route("/classes", AccountingWebController.admin_classes, methods=["GET", "POST"])
        self.admin_router.add_route("/accounts", AccountingWebController.admin_accounts, methods=["GET", "POST"])
        self.admin_router.add_route("/accounts/create", AccountingWebController.admin_create_account, methods=["GET", "POST"])
        self.admin_router.add_route("/mapping_hq", AccountingWebController.admin_mapping_hq, methods=["GET", "POST"])
        self.admin_router.add_route("/entries", AccountingWebController.admin_entries, methods=["GET", "POST"])
        self.admin_router.add_route("/entries/create", AccountingWebController.admin_create_entry, methods=["GET", "POST"])
        self.admin_router.add_route("/grand_livre", AccountingWebController.admin_grand_livre, methods=["GET"])
        self.admin_router.add_route("/fiscal_years", AccountingWebController.admin_fiscal_years, methods=["GET", "POST"])
        self.admin_router.add_route("/opcodes", AccountingWebController.admin_opcodes, methods=["GET", "POST"])
        self.admin_router.add_route("/queue", AccountingWebController.admin_queue, methods=["GET", "POST"])
        self.admin_router.add_route("/balance", AccountingWebController.admin_balance, methods=["GET"])
        self.admin_router.add_route("/consolidation", AccountingWebController.admin_consolidation, methods=["GET"])

        # Enregistrement des routes API JSON
        self.api_router.add_route("/accounts", AccountingAPIController.get_accounts, methods=["GET"])
        self.api_router.add_route("/opcodes/post", AccountingAPIController.post_opcode, methods=["POST"])
        self.api_router.add_route("/balance", AccountingAPIController.get_balance, methods=["GET"])
        self.api_router.add_route("/queue", AccountingAPIController.get_queue, methods=["GET"])
        self.api_router.add_route("/queue/retry", AccountingAPIController.retry_queue, methods=["POST"])
        self.api_router.add_route("/events/register", AccountingAPIController.register_event, methods=["POST"])

        # Enregistrement des actions inter-modules
        self._register_actions()

        # Enregistrement de la navigation dans le menu admin
        self.register_navigation(
            id="accounting_root",
            label="Comptabilité",
            icon="name=account_balance&fill=white",
            url="/admin/melodi_accounting",
            priority=70,
            children=[
                {"label": "Tableau de Bord", "icon": "name=dashboard&fill=white", "url": "/admin/melodi_accounting"},
                {"label": "Classes de Comptes", "icon": "name=folder_open&fill=white", "url": "/admin/melodi_accounting/classes"},
                {"label": "Plan de Comptes", "icon": "name=format_list_bulleted&fill=white", "url": "/admin/melodi_accounting/accounts"},
                {"label": "Mapping Siège", "icon": "name=alt_route&fill=white", "url": "/admin/melodi_accounting/mapping_hq"},
                {"label": "Exercices Fiscaux", "icon": "name=event&fill=white", "url": "/admin/melodi_accounting/fiscal_years"},
                {"label": "Pièces Comptables", "icon": "name=menu_book&fill=white", "url": "/admin/melodi_accounting/entries"},
                {"label": "Saisie de Pièce", "icon": "name=add_circle&fill=white", "url": "/admin/melodi_accounting/entries/create"},
                {"label": "Grand Livre", "icon": "name=book&fill=white", "url": "/admin/melodi_accounting/grand_livre"},
                {"label": "OpCodes & Règles", "icon": "name=tune&fill=white", "url": "/admin/melodi_accounting/opcodes"},
                {"label": "File d'Attente", "icon": "name=hourglass_empty&fill=white", "url": "/admin/melodi_accounting/queue"},
                {"label": "Balance Générale", "icon": "name=bar_chart&fill=white", "url": "/admin/melodi_accounting/balance"},
                {"label": "Consolidation Siège", "icon": "name=domain&fill=white", "url": "/admin/melodi_accounting/consolidation"},
                {"label": "Plans & Zones", "icon": "name=map&fill=white", "url": "/admin/melodi_accounting/charts"},
            ]
        )

    async def _restore_registered_event_listeners(self):
        """Recharge tous les événements inscrits en BDD par les modules tiers et s'y abonne."""
        async with self.app.db.get_session() as session:
            try:
                events = await AccountingService.get_registered_accounting_events(session)
                for ev in events:
                    self._subscribe_to_external_event(ev.origin_module, ev.event_name, ev.opcode)
            except Exception as e:
                print(f"Error restoring accounting event listeners: {e}")

    def _subscribe_to_external_event(self, origin_module: str, event_name: str, opcode: str):
        """Souscrit aux événements publiés par d'autres modules."""
        async def _event_handler(payload):
            await self._handle_incoming_accounting_event(origin_module, event_name, opcode, payload)

        self.app.hook_manager.event_listener.add(origin_module, event_name, _event_handler)

    async def _handle_incoming_accounting_event(self, origin_module: str, event_name: str, opcode: str, payload: dict):
        """Intercepte un événement déclenché par un module tiers, le met en file d'attente et lance le traitement."""
        data = payload if isinstance(payload, dict) else {"raw": payload}
        actual_opcode = data.get("opcode") or opcode
        agency_id = data.get("agency_id")

        queue_id = None
        async with self.app.db.get_session() as session:
            try:
                queue_item = await AccountingService.enqueue_accounting_operation(
                    session=session,
                    origin_module=origin_module,
                    event_name=event_name,
                    opcode=actual_opcode,
                    payload=data,
                    agency_id=agency_id
                )
                queue_id = queue_item.id
            except Exception as e:
                print(f"Error enqueuing accounting event from {origin_module}.{event_name}: {e}")
                return

        if queue_id:
            async with self.app.db.get_session() as session:
                try:
                    await AccountingService.process_queue_item(session, queue_id, module_instance=self)
                except Exception as e:
                    print(f"Error processing queue item #{queue_id}: {e}")


    def _register_actions(self):
        """Enregistre les actions exposées aux autres modules pour l'automatisation comptable."""
        self.add_action("register_opcode", self.action_register_opcode)
        self.add_action("create_accounting_rule", self.action_create_accounting_rule)
        self.add_action("post_operation_code", self.action_post_operation_code)
        self.add_action("create_journal_entry", self.action_create_journal_entry)
        self.add_action("get_account_balance", self.action_get_account_balance)
        self.add_action("register_accounting_event", self.action_register_accounting_event)
        self.add_action("retry_accounting_queue", self.action_retry_accounting_queue)
        self.add_action("get_registered_accounting_events", self.action_get_registered_accounting_events)

    # --- Handlers d'actions inter-modules ---

    async def action_register_accounting_event(self, payload: dict) -> dict:
        """Permet à un module tiers de déclarer les événements qu'il publie pour l'automatisation comptable."""
        origin_module = payload.get("origin_module") or payload.get("module_owner")
        event_name = payload.get("event_name")
        opcode = payload.get("opcode")
        description = payload.get("description", f"Événement {event_name} de {origin_module}")

        if not origin_module or not event_name or not opcode:
            return {"status": "error", "message": "Paramètres origin_module, event_name et opcode requis."}

        async with self.app.db.get_session() as session:
            try:
                reg = await AccountingService.register_accounting_event(
                    session=session,
                    origin_module=origin_module,
                    event_name=event_name,
                    opcode=opcode,
                    description=description
                )
                self._subscribe_to_external_event(origin_module, event_name, opcode)
                return {"status": "success", "event_id": reg.id}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_retry_accounting_queue(self, payload: dict) -> dict:
        queue_id = payload.get("queue_id")
        async with self.app.db.get_session() as session:
            try:
                if queue_id:
                    item = await AccountingService.retry_queue_item(session, int(queue_id), module_instance=self)
                    return {"status": "success", "queue_id": item.id, "queue_status": item.status}
                else:
                    count = await AccountingService.retry_all_failed_queue(session, module_instance=self)
                    return {"status": "success", "retried_count": count}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_get_registered_accounting_events(self, payload: dict) -> dict:
        async with self.app.db.get_session() as session:
            try:
                events = await AccountingService.get_registered_accounting_events(session)
                return {"status": "success", "events": [e.to_dict() for e in events]}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_register_opcode(self, payload: dict) -> dict:
        """Permet à un module tiers de déclarer un nouveau code d'opération comptable."""
        async with self.app.db.get_session() as session:
            try:
                op = await AccountingService.register_opcode(
                    session=session,
                    code=payload.get("code"),
                    module_owner=payload.get("module_owner", "UNKNOWN"),
                    description=payload.get("description", "")
                )
                return {"status": "success", "code": op.code}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_create_accounting_rule(self, payload: dict) -> dict:
        """Crée une règle d'imputation comptable pour un OpCode et un plan donné (chart_id)."""
        async with self.app.db.get_session() as session:
            try:
                rule = await AccountingService.create_accounting_rule(
                    session=session,
                    opcode=payload.get("opcode"),
                    chart_id=payload.get("chart_id"),
                    sens=payload.get("sens"),
                    account_code=payload.get("account_code")
                )
                return {"status": "success", "rule_id": rule.id}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_post_operation_code(self, payload: dict) -> dict:
        """Déclenche la comptabilisation automatique d'une opération émise par un module tiers."""
        async with self.app.db.get_session() as session:
            try:
                entry = await AccountingService.post_opcode_operation(
                    session=session,
                    opcode=payload.get("opcode"),
                    agency_id=payload.get("agency_id"),
                    chart_id=payload.get("chart_id", "SYSCOHADA_2026"),
                    amount=float(payload.get("amount", 0.0)),
                    description=payload.get("description", f"Opération {payload.get('opcode')}"),
                    journal_code=payload.get("journal_code", "VT"),
                    local_currency=payload.get("local_currency", "XAF"),
                    exchange_rate=float(payload.get("exchange_rate", 1.0)),
                    label=payload.get("label")
                )
                return {
                    "status": "success",
                    "entry_number": entry.entry_number,
                    "entry_id": entry.id
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_create_journal_entry(self, payload: dict) -> dict:
        """Création manuelle ou programmée d'une pièce comptable équilibrée."""
        async with self.app.db.get_session() as session:
            try:
                entry = await AccountingService.post_journal_entry(
                    session=session,
                    agency_id=payload.get("agency_id"),
                    journal_code=payload.get("journal_code", "OD"),
                    description=payload.get("description", "Écriture"),
                    items=payload.get("items", []),
                    entry_date=payload.get("entry_date")
                )
                return {
                    "status": "success",
                    "entry_number": entry.entry_number,
                    "entry_id": entry.id
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def action_get_account_balance(self, payload: dict) -> dict:
        """Calcule et renvoie la balance des comptes."""
        chart_id = payload.get("chart_id", "SYSCOHADA_2026")
        async with self.app.db.get_session() as session:
            try:
                data = await AccountingService.get_trial_balance(session, chart_id=chart_id)
                return {"status": "success", "chart_id": chart_id, "data": data}
            except Exception as e:
                return {"status": "error", "message": str(e)}


module = MelodiAccountingModule(
    name="melodi_accounting",
    router_name="melodi_accounting"
)

