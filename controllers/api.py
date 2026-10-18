from core.routing import Request, Response
from modules.melodi_accounting.services.accounting_service import AccountingService


class AccountingAPIController:

    @staticmethod
    async def get_accounts(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"
        class_code = request.query.get("class_code")
        type_compte = request.query.get("type_compte")
        search = request.query.get("search")

        async with request.module.app.db.get_session() as session:
            accounts = await AccountingService.get_all_accounts(
                session,
                chart_id=chart_id,
                class_code=class_code,
                type_compte=type_compte,
                search=search
            )

        return response.render_json({
            "status": "success",
            "count": len(accounts),
            "data": [acc.to_dict() for acc in accounts]
        })

    @staticmethod
    async def post_opcode(request: Request, response: Response):
        data = request.json or {}
        opcode = data.get("opcode")
        agency_id = data.get("agency_id")
        chart_id = data.get("chart_id", "SYSCOHADA_2026")
        amount = float(data.get("amount", 0.0))
        description = data.get("description", f"Opération {opcode}")
        journal_code = data.get("journal_code", "VT")
        local_currency = data.get("local_currency", "XAF")
        exchange_rate = float(data.get("exchange_rate", 1.0))

        entry_date_raw = data.get("entry_date") or data.get("date")
        entry_date = None
        if entry_date_raw:
            from datetime import datetime
            entry_date = datetime.strptime(str(entry_date_raw)[:10], "%Y-%m-%d").date()

        if not opcode or not agency_id or amount <= 0:
            return response.render_json({
                "status": "error",
                "message": "Paramètres invalides (opcode, agency_id, amount requis)"
            }, status_code=400)

        async with request.module.app.db.get_session() as session:
            try:
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
                    entry_date=entry_date
                )
                return response.render_json({
                    "status": "success",
                    "entry_number": entry.entry_number,
                    "entry_id": entry.id
                })
            except Exception as e:
                return response.render_json({
                    "status": "error",
                    "message": str(e)
                }, status_code=500)

    @staticmethod
    async def get_balance(request: Request, response: Response):
        chart_id = request.query.get("chart_id") or "SYSCOHADA_2026"
        async with request.module.app.db.get_session() as session:
            balance_data = await AccountingService.get_trial_balance(session, chart_id=chart_id)

        return response.render_json({
            "status": "success",
            "chart_id": chart_id,
            "data": balance_data
        })

    @staticmethod
    async def get_queue(request: Request, response: Response):
        status = request.query.get("status")
        search = request.query.get("search")

        async with request.module.app.db.get_session() as session:
            items = await AccountingService.get_queue_items(session, status=status, search=search)

        return response.render_json({
            "status": "success",
            "count": len(items),
            "data": [item.to_dict() for item in items]
        })

    @staticmethod
    async def retry_queue(request: Request, response: Response):
        data = request.json or {}
        queue_id = data.get("queue_id")

        async with request.module.app.db.get_session() as session:
            try:
                if queue_id:
                    item = await AccountingService.retry_queue_item(session, int(queue_id), module_instance=request.module)
                    return response.render_json({
                        "status": "success",
                        "queue_id": item.id,
                        "queue_status": item.status.value if hasattr(item.status, "value") else str(item.status),
                        "last_error": item.last_error
                    })
                else:
                    count = await AccountingService.retry_all_failed_queue(session, module_instance=request.module)
                    return response.render_json({
                        "status": "success",
                        "retried_count": count
                    })
            except Exception as e:
                return response.render_json({
                    "status": "error",
                    "message": str(e)
                }, status_code=500)

    @staticmethod
    async def register_event(request: Request, response: Response):
        data = request.json or {}
        origin_module = data.get("origin_module") or data.get("module_owner")
        event_name = data.get("event_name")
        opcode = data.get("opcode")
        description = data.get("description", f"Événement {event_name}")

        if not origin_module or not event_name or not opcode:
            return response.render_json({
                "status": "error",
                "message": "Paramètres origin_module, event_name et opcode requis"
            }, status_code=400)

        async with request.module.app.db.get_session() as session:
            try:
                reg = await AccountingService.register_accounting_event(
                    session=session,
                    origin_module=origin_module,
                    event_name=event_name,
                    opcode=opcode,
                    description=description
                )
                request.module._subscribe_to_external_event(origin_module, event_name, opcode)
                return response.render_json({
                    "status": "success",
                    "event_id": reg.id,
                    "data": reg.to_dict()
                })
            except Exception as e:
                return response.render_json({
                    "status": "error",
                    "message": str(e)
                }, status_code=500)

