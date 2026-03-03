"""
AgencyOS Orchestrator

The Chief AI's brain — routes messages to the right department,
handles cross-department reasoning, and enforces delegated mode.

Flow:
1. User sends message in a department chat (or Chief chat)
2. Orchestrator determines intent and target department
3. Department engine processes with scoped knowledge + tools
4. If action needed → create ActionProposal (no direct execution)
5. Response returned to user
6. If cross-department → Chief coordinates between departments
"""

import json
import logging
import re
import yaml
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..models.db import AgencyOSDepartment, AgencyOSKnowledge, AgencyOSOrganization
from .model_router import ModelRouter
from .proposals import ProposalsService
from .workpipe import WorkPipeService
from .crm_adapter import get_crm_adapter, CRMAdapterError
from .engines.sales_admin import SalesAdminEngine

logger = logging.getLogger("agencyos.orchestrator")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# Proposal detection: if the AI response contains this JSON structure,
# we extract it as a proposal
PROPOSAL_MARKER = '"action_proposal"'


class Orchestrator:
    """
    Central orchestration engine for AgencyOS.
    """

    def __init__(self):
        self.model_router = ModelRouter()
        self.workpipe = WorkPipeService()
        self.dept_config = self._load_department_config()
        self.permissions = self._load_permissions()
        self.routing_stats = {
            "local": 0,
            "mid": 0,
            "premium": 0,
            "classification_failures": 0,
        }
        logger.info(
            f"Orchestrator initialized with {len(self.dept_config)} department configs"
        )

    def _load_department_config(self) -> dict:
        config_path = CONFIG_DIR / "departments.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get("departments", {})
        return {}

    def _load_permissions(self) -> dict:
        config_path = CONFIG_DIR / "permissions.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}

    async def route_message(
        self,
        message: str,
        org_id: str,
        user_id: str,
        department_slug: Optional[str] = None,
        chat_id: Optional[str] = None,
        db: Optional[Session] = None,
        conversation_history: list[dict] = None,
    ) -> dict:
        """
        Route an incoming message to the appropriate department or Chief AI.
        """
        if department_slug:
            return await self._handle_department_message(
                message=message,
                org_id=org_id,
                user_id=user_id,
                department_slug=department_slug,
                chat_id=chat_id,
                db=db,
                conversation_history=conversation_history or [],
            )
        else:
            return await self._handle_chief_message(
                message=message,
                org_id=org_id,
                user_id=user_id,
                chat_id=chat_id,
                db=db,
                conversation_history=conversation_history or [],
            )

    async def classify_intent(
        self,
        message: str,
        department_slug: str,
        conversation_history: list[dict] = None,
    ) -> dict:
        """
        Use local model (Gemma 9B) to classify intent and complexity.

        Returns:
            Dict containing intent, complexity, needs_tool, department,
            can_handle, suggested_response, and internal classification status.
        """
        classification_prompt = """You are an intent classifier for an AI department system.
Analyze the user message and output ONLY a JSON object (no other text):
{
    "intent": "brief intent label",
    "complexity": <1-5 integer>,
    "needs_tool": <true/false>,
    "department": "<relevant department slug>",
    "can_handle": <true/false>,
    "suggested_response": "<if can_handle is true, provide a helpful response>"
}

Complexity guide:
1 = greeting, simple yes/no, status check
2 = single fact lookup, simple Q&A
3 = multi-step reasoning, comparison, analysis
4 = proposal drafting, document analysis, cross-reference
5 = strategic planning, cross-department coordination

Set can_handle=true ONLY for complexity 1-2 (simple queries you can answer directly).
Set can_handle=false for complexity 3+ (needs a more capable model).
Set needs_tool=true if the query needs CRM data, calendar, or external system access."""

        messages = [{"role": "user", "content": message}]

        result = await self.model_router.generate(
            tier="local",
            messages=messages,
            system_prompt=classification_prompt,
        )

        content = result.get("content", "")

        # Attempt robust parsing from potentially messy local model output
        candidates: list[str] = []
        stripped = content.strip()
        if stripped:
            candidates.append(stripped)

        fenced_json = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        candidates.extend(fenced_json)

        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(content[first_brace : last_brace + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    parsed.setdefault("intent", "unknown")
                    parsed.setdefault("complexity", 3)
                    parsed.setdefault("needs_tool", False)
                    parsed.setdefault("department", department_slug)
                    parsed.setdefault("can_handle", False)
                    parsed.setdefault("suggested_response", "")
                    parsed["complexity"] = max(1, min(5, int(parsed.get("complexity", 3))))
                    parsed["_classification_failed"] = False
                    return parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        self.routing_stats["classification_failures"] += 1
        logger.info(
            "Intent classification failed; defaulting to escalation path",
            extra={"department": department_slug},
        )

        # Default: escalate to mid-tier if classification fails
        return {
            "intent": "unknown",
            "complexity": 3,
            "needs_tool": False,
            "department": department_slug,
            "can_handle": False,
            "suggested_response": "",
            "_classification_failed": True,
        }

    def get_routing_stats(self) -> dict:
        """Return in-memory model routing counters."""
        total = sum(self.routing_stats.values())
        return {**self.routing_stats, "total": total}

    async def _handle_department_message(
        self,
        message: str,
        org_id: str,
        user_id: str,
        department_slug: str,
        chat_id: Optional[str] = None,
        db: Optional[Session] = None,
        conversation_history: list[dict] = None,
    ) -> dict:
        """Process a message within a specific department's scope."""
        # Get department config (from YAML for now, DB later)
        dept_config = self.dept_config.get(department_slug)
        if not dept_config:
            return {"error": f"Unknown department: {department_slug}", "content": ""}

        system_prompt = self._build_department_prompt(dept_config, org_id)

        # Build message list with conversation history
        messages = list(conversation_history or [])
        messages.append({"role": "user", "content": message})

        # Retrieve department knowledge for RAG context
        knowledge_context = ""
        if db:
            knowledge_context = await self._get_department_knowledge(
                db, org_id, department_slug, message
            )
            if knowledge_context:
                system_prompt += f"\n\n## Department Knowledge Base\n{knowledge_context}"

        # Classify with local model before routing
        intent = await self.classify_intent(
            message=message,
            department_slug=department_slug,
            conversation_history=conversation_history or [],
        )

        # Inject CRM context via department engine (Phase 2B) or legacy bridge
        if db:
            try:
                org_row = db.query(AgencyOSOrganization).filter_by(id=org_id).first()
                sub_account_id = org_row.workpipe_account_id if org_row else None

                if sub_account_id:
                    crm_context_str = ""

                    # Use department-specific engine when available
                    if department_slug == "sales_admin":
                        try:
                            # Try CRM adapter (Phase 2B — calls WorkPipe Internal API)
                            # auth_token would come from request context in production
                            crm = get_crm_adapter(auth_token="")
                            engine = SalesAdminEngine(crm=crm)
                            crm_context_str = await engine.build_crm_context(sub_account_id)
                        except (CRMAdapterError, Exception) as adapter_err:
                            logger.info("CRM adapter unavailable, falling back to SQL bridge: %s", adapter_err)
                            # Fall back to legacy read-only SQL bridge
                            if self.workpipe.is_connected:
                                crm_context_str = await self._legacy_crm_context(department_slug, dept_config, sub_account_id)

                    elif self.workpipe.is_connected:
                        # Other departments: use legacy SQL bridge for now
                        crm_context_str = await self._legacy_crm_context(department_slug, dept_config, sub_account_id)

                    if crm_context_str:
                        system_prompt += f"\n\n{crm_context_str}"

            except Exception as e:
                logger.warning("Failed to inject CRM context for %s: %s", department_slug, e)

        if intent.get("needs_tool"):
            system_prompt += (
                "\n\n## Tooling Note\n"
                "The user request likely needs external tools/systems (CRM, calendar, or related integrations). "
                "If an action is needed, provide a structured action proposal."
            )

        # Local-first direct response path
        suggested_response = (intent.get("suggested_response") or "").strip()
        if intent.get("can_handle") and suggested_response:
            selected_tier = "local"
            self.routing_stats[selected_tier] += 1
            logger.info(
                f"[{org_id}] Routing decision for {department_slug}: {selected_tier} "
                f"(intent={intent.get('intent')}, complexity={intent.get('complexity')}, "
                f"needs_tool={intent.get('needs_tool')})"
            )

            result = {
                "model": "gemma-9b-classifier",
                "content": suggested_response,
                "usage": {},
            }
        else:
            complexity = int(intent.get("complexity", 3))
            selected_tier = "mid" if complexity <= 3 else "premium"
            self.routing_stats[selected_tier] += 1

            logger.info(
                f"[{org_id}] Routing decision for {department_slug}: {selected_tier} "
                f"(intent={intent.get('intent')}, complexity={complexity}, "
                f"needs_tool={intent.get('needs_tool')}, "
                f"classification_failed={intent.get('_classification_failed', False)})"
            )

            result = await self.model_router.generate(
                tier=selected_tier,
                messages=messages,
                system_prompt=system_prompt,
            )

        # Check if the AI wants to propose an action
        proposals = []
        if not result.get("error") and PROPOSAL_MARKER in result.get("content", ""):
            proposals = self._extract_proposals(result["content"], org_id, department_slug, chat_id, db)

        return {
            "department": department_slug,
            "model_tier": selected_tier,
            "model": result.get("model", ""),
            "content": result.get("content", ""),
            "proposals": proposals,
            "usage": result.get("usage", {}),
            "status": "error" if result.get("error") else "ok",
        }

    async def _handle_chief_message(
        self,
        message: str,
        org_id: str,
        user_id: str,
        chat_id: Optional[str] = None,
        db: Optional[Session] = None,
        conversation_history: list[dict] = None,
    ) -> dict:
        """
        Chief AI handles cross-department reasoning.
        Analyzes intent, may delegate to one or more departments.
        """
        system_prompt = self._build_chief_prompt(org_id)

        messages = list(conversation_history or [])
        messages.append({"role": "user", "content": message})

        logger.info(f"[{org_id}] Chief AI processing request")
        result = await self.model_router.generate(
            tier="premium",
            messages=messages,
            system_prompt=system_prompt,
        )

        # Check for delegation instructions in Chief's response
        # TODO: Parse structured delegation format and route to departments

        proposals = []
        if not result.get("error") and PROPOSAL_MARKER in result.get("content", ""):
            proposals = self._extract_proposals(result["content"], org_id, "chief", chat_id, db)

        return {
            "department": "chief",
            "model_tier": "premium",
            "model": result.get("model", ""),
            "content": result.get("content", ""),
            "proposals": proposals,
            "usage": result.get("usage", {}),
            "status": "error" if result.get("error") else "ok",
        }

    def _extract_proposals(
        self,
        content: str,
        org_id: str,
        department_slug: str,
        chat_id: Optional[str],
        db: Optional[Session],
    ) -> list[dict]:
        """
        Extract action proposals from AI response.

        The AI is instructed to output proposals in a specific JSON format:
        ```json
        {"action_proposal": {
            "title": "...",
            "description": "...",
            "action_type": "...",
            "action_payload": {...},
            "risk_level": "low|medium|high|critical",
            "risk_reasoning": "..."
        }}
        ```
        """
        proposals = []
        try:
            # Find JSON blocks in the response
            json_blocks = re.findall(r'\{[^{}]*"action_proposal"[^{}]*\{[^}]*\}[^}]*\}', content)

            for block in json_blocks:
                try:
                    parsed = json.loads(block)
                    proposal_data = parsed.get("action_proposal", {})
                    if proposal_data and db:
                        proposal = ProposalsService.create_proposal(
                            db=db,
                            org_id=org_id,
                            department_id=department_slug,
                            title=proposal_data.get("title", "Untitled Action"),
                            description=proposal_data.get("description", ""),
                            action_type=proposal_data.get("action_type", "unknown"),
                            action_payload=proposal_data.get("action_payload", {}),
                            risk_level=proposal_data.get("risk_level", "low"),
                            risk_reasoning=proposal_data.get("risk_reasoning", ""),
                            created_by_ai=f"agencyos/{department_slug}",
                            chat_id=chat_id,
                        )
                        proposals.append({
                            "id": proposal.id,
                            "title": proposal.title,
                            "action_type": proposal.action_type,
                            "risk_level": proposal.risk_level,
                            "status": "pending",
                        })
                    elif proposal_data:
                        # No DB session, return raw proposal data
                        proposals.append(proposal_data)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.warning(f"Failed to extract proposals: {e}")

        return proposals

    async def _get_department_knowledge(
        self,
        db: Session,
        org_id: str,
        department_slug: str,
        query: str,
    ) -> str:
        """
        Retrieve relevant knowledge base entries for the department.
        TODO: Replace with proper vector search (pgvector) once embeddings are set up.
        For now, returns the most recent knowledge entries.
        """
        try:
            # Get department ID from slug
            dept = db.query(AgencyOSDepartment).filter_by(
                org_id=org_id, slug=department_slug
            ).first()
            if not dept:
                return ""

            entries = db.query(AgencyOSKnowledge).filter_by(
                org_id=org_id, department_id=dept.id
            ).order_by(AgencyOSKnowledge.updated_at.desc()).limit(5).all()

            if not entries:
                return ""

            context_parts = []
            for entry in entries:
                context_parts.append(f"### {entry.title}\n{entry.content}")

            return "\n\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Knowledge retrieval failed: {e}")
            return ""

    async def _legacy_crm_context(
        self, department_slug: str, dept_config: dict, sub_account_id: str
    ) -> str:
        """Legacy CRM context via direct SQL bridge (read-only). Used as fallback."""
        workpipe_modules = dept_config.get("workpipe_modules", [])
        module_set = set(workpipe_modules)
        crm_context: dict = {}

        if {"contacts", "pipelines", "deals"}.intersection(module_set):
            if "deals" in module_set or "pipelines" in module_set:
                crm_context["deal_summary"] = await self.workpipe.get_deal_summary(sub_account_id)
            if "contacts" in module_set:
                crm_context["recent_contacts"] = await self.workpipe.get_contacts(
                    sub_account_id=sub_account_id, limit=10, offset=0,
                )

        if "tickets" in module_set:
            crm_context["recent_tickets"] = await self.workpipe.get_recent_tickets(
                sub_account_id=sub_account_id, limit=10,
            )

        if "invoices" in module_set:
            crm_context["invoice_summary"] = await self.workpipe.get_invoice_summary(sub_account_id)

        if crm_context:
            return f"## Current CRM Data\n{json.dumps(crm_context, indent=2, default=str)}"
        return ""

    def _build_department_prompt(self, dept_config: dict, org_id: str) -> str:
        """Build a system prompt scoped to a department's role and capabilities."""
        name = dept_config.get("name", "Department")
        description = dept_config.get("description", "")
        capabilities = dept_config.get("capabilities", [])

        return f"""You are the {name} AI department head for this organization.

## Your Role
{description}

## Your Capabilities
{chr(10).join(f'- {cap.replace("_", " ").title()}' for cap in capabilities)}

## Rules (STRICT)
1. You can ONLY access data within your department's scope. Never reference other departments' data.
2. You CANNOT directly execute actions. If you need to take action (send email, update record, etc.), 
   output a structured proposal in this exact JSON format:
   ```json
   {{"action_proposal": {{
       "title": "Brief action title",
       "description": "What this action does and why",
       "action_type": "send_email|update_contact|create_task|update_pipeline|etc",
       "action_payload": {{"key": "value"}},
       "risk_level": "low|medium|high|critical",
       "risk_reasoning": "Why this risk level"
   }}}}
   ```
3. If a request involves another department, say so and suggest the user ask the Chief AI.
4. Always explain your reasoning before proposing actions.
5. Be concise but thorough. You're a department head, not a chatbot.

## Response Format
- Answer the user's question directly
- If an action is needed, include the proposal JSON block in your response
- Multiple proposals can be included if multiple actions are needed"""

    def _build_chief_prompt(self, org_id: str) -> str:
        """Build the Chief AI's system prompt."""
        dept_names = [d.get("name", k) for k, d in self.dept_config.items() if k != "chief"]

        return f"""You are the Chief AI — the executive intelligence layer for this organization.

## Your Role
Cross-department reasoning, strategic summaries, and delegation across departments.

## Available Departments
{chr(10).join(f'- {name}' for name in dept_names)}

## Rules (STRICT)
1. You coordinate across departments but do NOT bypass the approval model.
2. For actions, output proposals in the same JSON format as department heads:
   ```json
   {{"action_proposal": {{
       "title": "...",
       "description": "...",
       "action_type": "...",
       "action_payload": {{}},
       "risk_level": "low|medium|high|critical",
       "risk_reasoning": "..."
   }}}}
   ```
3. When a request belongs to a specific department, indicate which one.
4. Provide strategic context — you see the big picture.
5. Summarize cross-department impacts when relevant.

## Response Format
- Analyze the request and identify which department(s) it touches
- Provide your executive perspective
- If delegation is needed, indicate the target department
- Include action proposals when actions are needed"""