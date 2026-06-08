"""
WorkPipe CRM Data Bridge

Reads data from WorkPipe's Postgres database to provide CRM context
to AgencyOS department AI agents.

Connection: Uses the same Postgres instance, reads WorkPipe tables directly.
This is READ-ONLY — all writes go through WorkPipe's own API/Prisma layer.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("agencyos.workpipe")


class WorkPipeService:
    """Read-only bridge to WorkPipe CRM data."""

    def __init__(self):
        self.db_url = os.environ.get("WORKPIPE_DATABASE_URL", "")
        self._engine = None
        self._session_factory = None

        if self.db_url:
            self._engine = create_engine(self.db_url, pool_pre_ping=True, pool_size=5)
            self._session_factory = sessionmaker(bind=self._engine)
            logger.info("WorkPipe data bridge initialized")
        else:
            logger.warning("WORKPIPE_DATABASE_URL not set — CRM integration disabled")

    @property
    def is_connected(self) -> bool:
        """Return whether WorkPipe DB access is configured."""
        return self._engine is not None

    def _not_configured(self) -> dict:
        return {"error": "WorkPipe integration not configured", "data": []}

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return value

    def _rows_to_dicts(self, result) -> list[dict]:
        rows: list[dict] = []
        for row in result.mappings().all():
            rows.append({k: self._serialize(v) for k, v in dict(row).items()})
        return rows

    def _get_session(self) -> Optional[Session]:
        if not self._session_factory:
            return None
        return self._session_factory()

    # ── Contacts ──────────────────────────────────────────

    async def get_contacts(
        self, sub_account_id: str, limit: int = 50, offset: int = 0
    ) -> dict:
        """Get contacts for a sub-account."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            query = text(
                'SELECT id, name, email, "createdAt", "updatedAt", "subAccountId" '
                'FROM "Contact" '
                'WHERE "subAccountId" = :sub_account_id '
                'ORDER BY "createdAt" DESC '
                "LIMIT :limit OFFSET :offset"
            )
            result = session.execute(
                query,
                {
                    "sub_account_id": sub_account_id,
                    "limit": max(1, min(limit, 200)),
                    "offset": max(0, offset),
                },
            )
            contacts = self._rows_to_dicts(result)
            return {"data": contacts, "count": len(contacts)}
        except Exception as e:
            logger.error("Failed to fetch contacts: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def get_contact(self, contact_id: str) -> Optional[dict] | dict:
        """Get a single contact by ID."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            query = text(
                'SELECT id, name, email, "createdAt", "updatedAt", "subAccountId" '
                'FROM "Contact" WHERE id = :contact_id LIMIT 1'
            )
            row = session.execute(query, {"contact_id": contact_id}).mappings().first()
            return {k: self._serialize(v) for k, v in dict(row).items()} if row else None
        except Exception as e:
            logger.error("Failed to fetch contact %s: %s", contact_id, e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def search_contacts(self, sub_account_id: str, query: str, limit: int = 20) -> dict:
        """Search contacts by name or email."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT id, name, email, "createdAt", "updatedAt", "subAccountId" '
                'FROM "Contact" '
                'WHERE "subAccountId" = :sub_account_id '
                'AND (name ILIKE :q OR email ILIKE :q) '
                'ORDER BY "createdAt" DESC LIMIT :limit'
            )
            result = session.execute(
                sql,
                {
                    "sub_account_id": sub_account_id,
                    "q": f"%{query}%",
                    "limit": max(1, min(limit, 100)),
                },
            )
            contacts = self._rows_to_dicts(result)
            return {"data": contacts, "count": len(contacts), "query": query}
        except Exception as e:
            logger.error("Failed to search contacts: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    # ── Pipelines & Deals ─────────────────────────────────

    async def get_pipelines(self, sub_account_id: str) -> dict:
        """Get all pipelines with lane counts."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT p.id, p.name, p."createdAt", p."updatedAt", p."subAccountId", '
                'COUNT(DISTINCT l.id) AS lane_count, COUNT(t.id) AS ticket_count '
                'FROM "Pipeline" p '
                'LEFT JOIN "Lane" l ON l."pipelineId" = p.id '
                'LEFT JOIN "Ticket" t ON t."laneId" = l.id '
                'WHERE p."subAccountId" = :sub_account_id '
                'GROUP BY p.id, p.name, p."createdAt", p."updatedAt", p."subAccountId" '
                'ORDER BY p."createdAt" DESC'
            )
            pipelines = self._rows_to_dicts(session.execute(sql, {"sub_account_id": sub_account_id}))
            return {"data": pipelines, "count": len(pipelines)}
        except Exception as e:
            logger.error("Failed to fetch pipelines: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def get_pipeline_detail(self, pipeline_id: str) -> dict:
        """Get pipeline with all lanes and ticket counts."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            pipeline_sql = text(
                'SELECT id, name, "createdAt", "updatedAt", "subAccountId" '
                'FROM "Pipeline" WHERE id = :pipeline_id LIMIT 1'
            )
            lane_sql = text(
                'SELECT l.id, l.name, l."createdAt", l."updatedAt", l."pipelineId", l."order", '
                'COUNT(t.id) AS ticket_count '
                'FROM "Lane" l '
                'LEFT JOIN "Ticket" t ON t."laneId" = l.id '
                'WHERE l."pipelineId" = :pipeline_id '
                'GROUP BY l.id, l.name, l."createdAt", l."updatedAt", l."pipelineId", l."order" '
                'ORDER BY l."order" ASC, l."createdAt" ASC'
            )
            pipeline_row = session.execute(pipeline_sql, {"pipeline_id": pipeline_id}).mappings().first()
            if not pipeline_row:
                return {"data": None}

            lanes = self._rows_to_dicts(session.execute(lane_sql, {"pipeline_id": pipeline_id}))
            return {
                "data": {
                    **{k: self._serialize(v) for k, v in dict(pipeline_row).items()},
                    "lanes": lanes,
                }
            }
        except Exception as e:
            logger.error("Failed to fetch pipeline detail %s: %s", pipeline_id, e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def get_tickets_in_lane(self, lane_id: str, limit: int = 50) -> dict:
        """Get tickets (deals) in a specific lane."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT t.id, t.name, t."createdAt", t."updatedAt", t."laneId", t."order", '
                't.value, t.description, t."customerId", t."assignedUserId", c.name AS customer_name, c.email AS customer_email '
                'FROM "Ticket" t '
                'LEFT JOIN "Contact" c ON c.id = t."customerId" '
                'WHERE t."laneId" = :lane_id '
                'ORDER BY t."order" ASC, t."createdAt" DESC '
                'LIMIT :limit'
            )
            tickets = self._rows_to_dicts(
                session.execute(sql, {"lane_id": lane_id, "limit": max(1, min(limit, 200))})
            )
            return {"data": tickets, "count": len(tickets)}
        except Exception as e:
            logger.error("Failed to fetch tickets in lane %s: %s", lane_id, e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def get_deal_summary(self, sub_account_id: str) -> dict:
        """Get aggregated deal stats: total value, count by stage, etc."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            totals_sql = text(
                'SELECT COUNT(t.id) AS total_deals, COALESCE(SUM(t.value), 0) AS total_value '
                'FROM "Ticket" t '
                'JOIN "Lane" l ON l.id = t."laneId" '
                'JOIN "Pipeline" p ON p.id = l."pipelineId" '
                'WHERE p."subAccountId" = :sub_account_id'
            )
            by_stage_sql = text(
                'SELECT p.name AS pipeline_name, l.name AS lane_name, COUNT(t.id) AS deal_count, '
                'COALESCE(SUM(t.value), 0) AS stage_value '
                'FROM "Lane" l '
                'JOIN "Pipeline" p ON p.id = l."pipelineId" '
                'LEFT JOIN "Ticket" t ON t."laneId" = l.id '
                'WHERE p."subAccountId" = :sub_account_id '
                'GROUP BY p.name, l.name, l."order" '
                'ORDER BY p.name ASC, l."order" ASC'
            )
            totals = session.execute(totals_sql, {"sub_account_id": sub_account_id}).mappings().first()
            stage_rows = self._rows_to_dicts(session.execute(by_stage_sql, {"sub_account_id": sub_account_id}))
            return {
                "data": {
                    "total_deals": int(totals.get("total_deals", 0)) if totals else 0,
                    "total_value": self._serialize(totals.get("total_value", 0)) if totals else 0,
                    "by_stage": stage_rows,
                }
            }
        except Exception as e:
            logger.error("Failed to fetch deal summary: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    # ── Tickets (Support) ─────────────────────────────────

    async def get_recent_tickets(self, sub_account_id: str, limit: int = 20) -> dict:
        """Get recent tickets across all pipelines."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT t.id, t.name, t."createdAt", t."updatedAt", t."laneId", t.value, t.description, '
                'l.name AS lane_name, p.name AS pipeline_name, t."customerId", c.name AS customer_name '
                'FROM "Ticket" t '
                'JOIN "Lane" l ON l.id = t."laneId" '
                'JOIN "Pipeline" p ON p.id = l."pipelineId" '
                'LEFT JOIN "Contact" c ON c.id = t."customerId" '
                'WHERE p."subAccountId" = :sub_account_id '
                'ORDER BY t."updatedAt" DESC '
                'LIMIT :limit'
            )
            tickets = self._rows_to_dicts(
                session.execute(sql, {"sub_account_id": sub_account_id, "limit": max(1, min(limit, 100))})
            )
            return {"data": tickets, "count": len(tickets)}
        except Exception as e:
            logger.error("Failed to fetch recent tickets: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    # ── Invoices ──────────────────────────────────────────

    async def get_invoices(self, sub_account_id: str, limit: int = 50) -> dict:
        """Get invoices for a sub-account."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT id, type, "dueDate", "totalDue", name, link, "subAccountId", "createdAt", "updatedAt", '
                '"netPaymentTerm", "subTotal", tax, discount '
                'FROM "Invoice" '
                'WHERE "subAccountId" = :sub_account_id '
                'ORDER BY "createdAt" DESC '
                'LIMIT :limit'
            )
            invoices = self._rows_to_dicts(
                session.execute(sql, {"sub_account_id": sub_account_id, "limit": max(1, min(limit, 200))})
            )
            return {"data": invoices, "count": len(invoices)}
        except Exception as e:
            logger.error("Failed to fetch invoices: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    async def get_invoice_summary(self, sub_account_id: str) -> dict:
        """Get aggregated invoice stats: total due, paid, overdue count."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT '
                'COUNT(*) AS total_invoices, '
                'COALESCE(SUM(CAST(NULLIF("totalDue", \'\') AS NUMERIC)), 0) AS total_due, '
                'COUNT(*) FILTER (WHERE "dueDate" < NOW()) AS overdue_count '
                'FROM "Invoice" '
                'WHERE "subAccountId" = :sub_account_id'
            )
            row = session.execute(sql, {"sub_account_id": sub_account_id}).mappings().first()
            data = {
                "total_invoices": int(row.get("total_invoices", 0)) if row else 0,
                "total_due": self._serialize(row.get("total_due", 0)) if row else 0,
                "overdue_count": int(row.get("overdue_count", 0)) if row else 0,
            }
            return {"data": data}
        except Exception as e:
            logger.error("Failed to fetch invoice summary: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()

    # ── Calendar ──────────────────────────────────────────

    async def get_upcoming_events(self, sub_account_id: str, limit: int = 10) -> dict:
        """Get upcoming calendar events."""
        if not self.is_connected:
            return self._not_configured()

        session = self._get_session()
        if session is None:
            return self._not_configured()

        try:
            sql = text(
                'SELECT e.id, e.title, e.description, e."startTime", e."endTime", e."subAccountId", e."contactId", '
                'c.name AS contact_name, c.email AS contact_email '
                'FROM "CalendarEvent" e '
                'LEFT JOIN "Contact" c ON c.id = e."contactId" '
                'WHERE e."subAccountId" = :sub_account_id AND e."startTime" >= NOW() '
                'ORDER BY e."startTime" ASC '
                'LIMIT :limit'
            )
            events = self._rows_to_dicts(
                session.execute(sql, {"sub_account_id": sub_account_id, "limit": max(1, min(limit, 100))})
            )
            return {"data": events, "count": len(events)}
        except Exception as e:
            logger.error("Failed to fetch upcoming events: %s", e)
            return {"error": str(e), "data": []}
        finally:
            session.close()
