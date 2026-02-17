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

import logging
import yaml
from pathlib import Path
from typing import Optional

from ..models.department import Department
from ..models.proposal import ActionProposal, ProposalCreate, ProposalStatus
from .model_router import ModelRouter

logger = logging.getLogger("agencyos.orchestrator")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class Orchestrator:
    """
    Central orchestration engine for AgencyOS.
    
    Responsibilities:
    - Route user messages to appropriate department
    - Enforce department data boundaries
    - Coordinate cross-department requests via Chief AI
    - Create action proposals (delegated mode)
    - Manage conversation context per department
    """

    def __init__(self):
        self.model_router = ModelRouter()
        self.departments = self._load_department_config()
        self.permissions = self._load_permissions()
        logger.info(
            f"Orchestrator initialized with {len(self.departments)} departments"
        )

    def _load_department_config(self) -> dict:
        """Load department definitions from YAML config."""
        config_path = CONFIG_DIR / "departments.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get("departments", {})
        logger.warning("No departments.yaml found, using defaults")
        return {}

    def _load_permissions(self) -> dict:
        """Load permission matrix from YAML config."""
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
    ) -> dict:
        """
        Route an incoming message to the appropriate department.
        
        If department_slug is provided, route directly.
        If None (Chief AI chat), analyze intent and delegate.
        """
        if department_slug:
            return await self._handle_department_message(
                message=message,
                org_id=org_id,
                user_id=user_id,
                department_slug=department_slug,
                chat_id=chat_id,
            )
        else:
            return await self._handle_chief_message(
                message=message,
                org_id=org_id,
                user_id=user_id,
                chat_id=chat_id,
            )

    async def _handle_department_message(
        self,
        message: str,
        org_id: str,
        user_id: str,
        department_slug: str,
        chat_id: Optional[str] = None,
    ) -> dict:
        """Process a message within a specific department's scope."""
        dept_config = self.departments.get(department_slug)
        if not dept_config:
            return {"error": f"Unknown department: {department_slug}"}

        # Get the right model for this department's tier
        model_tier = dept_config.get("model_tier", "mid")
        model = self.model_router.get_model(model_tier)

        # Build department-scoped context
        system_prompt = self._build_department_prompt(dept_config)

        # TODO: Add RAG retrieval from department knowledge base
        # TODO: Add WorkPipe module data injection
        # TODO: Send to model and get response
        # TODO: Parse response for action proposals

        logger.info(
            f"[{org_id}] Message routed to {department_slug} using {model_tier} tier"
        )

        return {
            "department": department_slug,
            "model_tier": model_tier,
            "model": model,
            "system_prompt": system_prompt,
            "status": "processed",
        }

    async def _handle_chief_message(
        self,
        message: str,
        org_id: str,
        user_id: str,
        chat_id: Optional[str] = None,
    ) -> dict:
        """
        Chief AI handles cross-department reasoning.
        Analyzes intent, may delegate to one or more departments.
        """
        model = self.model_router.get_model("premium")

        # TODO: Intent analysis — which department(s) does this touch?
        # TODO: If single dept → delegate to that dept engine
        # TODO: If multi-dept → coordinate responses, synthesize
        # TODO: Strategic summaries and cross-dept insights

        logger.info(f"[{org_id}] Chief AI processing cross-department request")

        return {
            "department": "chief",
            "model_tier": "premium",
            "model": model,
            "status": "processed",
        }

    async def create_proposal(
        self,
        org_id: str,
        proposal_data: ProposalCreate,
    ) -> ActionProposal:
        """
        Create an action proposal (delegated mode).
        The AI suggests an action; humans must approve before execution.
        """
        proposal = ActionProposal(
            org_id=org_id,
            **proposal_data.model_dump(),
        )

        # TODO: Persist to database
        # TODO: Notify relevant approvers
        # TODO: Add to approval inbox

        logger.info(
            f"[{org_id}] Proposal created: {proposal.title} "
            f"(risk: {proposal.risk_level}, dept: {proposal.department_id})"
        )

        return proposal

    async def execute_proposal(
        self,
        proposal: ActionProposal,
    ) -> dict:
        """
        Execute an approved proposal.
        Only called after human approval.
        """
        if proposal.status != ProposalStatus.APPROVED:
            return {"error": "Proposal must be approved before execution"}

        # TODO: Route to appropriate tool/integration based on action_type
        # TODO: Connect to WorkPipe API for CRM actions
        # TODO: Log execution result
        # TODO: Update proposal status

        logger.info(
            f"[{proposal.org_id}] Executing proposal: {proposal.title}"
        )

        return {"status": "executed", "proposal_id": proposal.id}

    def _build_department_prompt(self, dept_config: dict) -> str:
        """Build a system prompt scoped to a department's role and capabilities."""
        name = dept_config.get("name", "Department")
        description = dept_config.get("description", "")
        capabilities = dept_config.get("capabilities", [])

        prompt = f"""You are the {name} AI for this organization.

Role: {description}

Your capabilities:
{chr(10).join(f'- {cap}' for cap in capabilities)}

IMPORTANT RULES:
1. You can ONLY access data within your department's scope.
2. You CANNOT directly execute actions. All actions must be submitted as proposals.
3. If a request involves another department, escalate to the Chief AI.
4. Always explain your reasoning before proposing actions.
5. Assess risk level for every proposal (low/medium/high/critical).
"""
        return prompt
