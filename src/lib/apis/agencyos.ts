import { WEBUI_BASE_URL } from '$lib/constants';

const AGENCYOS_API_BASE = `${WEBUI_BASE_URL}/api/agencyos`;

// ─── Types ────────────────────────────────────────────────────

export interface Organization {
	id: string;
	name: string;
	slug: string;
	plan: string;
	settings?: Record<string, unknown>;
}

export interface OrgMember {
	id: string;
	user_id: string;
	role: string;
	department_ids: string[];
}

export interface Department {
	id: string;
	slug: string;
	name: string;
	description: string;
	model_tier: string;
	capabilities: string[];
	workpipe_modules?: string[];
	system_prompt?: string;
}

export interface Proposal {
	id: string;
	title: string;
	description: string;
	action_type: string;
	action_payload?: Record<string, unknown>;
	risk_level: 'low' | 'medium' | 'high' | 'critical';
	risk_reasoning?: string;
	status: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';
	department_id: string;
	chat_id?: string;
	created_by_ai?: string;
	reviewed_by?: string;
	review_note?: string;
	execution_result?: Record<string, unknown>;
	created_at: number;
	updated_at?: number;
}

export interface ProposalStats {
	total: number;
	pending: number;
	approved: number;
	rejected: number;
	executed: number;
}

export interface ChatResponse {
	department: string;
	model_tier: string;
	model: string;
	content: string;
	proposals: Proposal[];
	usage: Record<string, unknown>;
	status: string;
}

// ─── Helpers ──────────────────────────────────────────────────

async function apiCall<T>(
	url: string,
	token: string,
	options: RequestInit = {}
): Promise<T> {
	let error = null;

	const res = await fetch(url, {
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		...options
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res as T;
}

// ─── Organizations ────────────────────────────────────────────

export const getOrganization = async (token: string, orgId: string) => {
	return apiCall<Organization>(`${AGENCYOS_API_BASE}/orgs/${orgId}`, token);
};

export const createOrganization = async (
	token: string,
	data: { name: string; slug: string; workpipe_account_id?: string; plan?: string }
) => {
	return apiCall<{ organization: Organization; departments: Department[] }>(
		`${AGENCYOS_API_BASE}/orgs/`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const getOrganizationForUser = async (token: string) => {
	// TODO: Backend endpoint to look up org by authenticated user membership
	// Try stored org first, then list all orgs and take the first one
	try {
		const storedOrgId = typeof localStorage !== 'undefined' ? localStorage.getItem('agencyos-org-id') : null;
		if (storedOrgId) {
			try {
				const org = await getOrganization(token, storedOrgId);
				return org;
			} catch {
				// Stored org no longer valid, clear and try listing
				localStorage.removeItem('agencyos-org-id');
			}
		}
		// Fallback: list orgs and use first available
		const orgs = await listOrganizations(token);
		if (orgs && orgs.length > 0) {
			localStorage.setItem('agencyos-org-id', orgs[0].id);
			return orgs[0];
		}
		return null;
	} catch {
		return null;
	}
};

export const listOrganizations = async (token: string) => {
	return apiCall<Organization[]>(`${AGENCYOS_API_BASE}/orgs/`, token);
};

export const getOrgMembers = async (token: string, orgId: string) => {
	return apiCall<{ members: OrgMember[]; total: number }>(
		`${AGENCYOS_API_BASE}/orgs/${orgId}/members`,
		token
	);
};

export const addOrgMember = async (
	token: string,
	orgId: string,
	data: { user_id: string; role?: string; department_ids?: string[] }
) => {
	return apiCall<OrgMember>(`${AGENCYOS_API_BASE}/orgs/${orgId}/members`, token, {
		method: 'POST',
		body: JSON.stringify(data)
	});
};

// ─── Departments ──────────────────────────────────────────────

export const getDepartments = async (token: string, orgId: string) => {
	return apiCall<{ departments: Department[]; total: number }>(
		`${AGENCYOS_API_BASE}/departments/?org_id=${orgId}`,
		token
	);
};

export const getDepartment = async (token: string, departmentId: string, orgId: string) => {
	return apiCall<Department>(
		`${AGENCYOS_API_BASE}/departments/${departmentId}?org_id=${orgId}`,
		token
	);
};

export const sendDepartmentChat = async (
	token: string,
	orgId: string,
	departmentSlug: string,
	data: {
		message: string;
		user_id: string;
		chat_id?: string;
		conversation_history?: { role: string; content: string }[];
	}
) => {
	return apiCall<ChatResponse>(
		`${AGENCYOS_API_BASE}/departments/${departmentSlug}/chat?org_id=${orgId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const sendChiefChat = async (
	token: string,
	orgId: string,
	data: {
		message: string;
		user_id: string;
		chat_id?: string;
		conversation_history?: { role: string; content: string }[];
	}
) => {
	return apiCall<ChatResponse>(
		`${AGENCYOS_API_BASE}/departments/chief/chat?org_id=${orgId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

// ─── Proposals ────────────────────────────────────────────────

export const getProposals = async (
	token: string,
	orgId: string,
	params?: { status?: string; department_id?: string; limit?: number; offset?: number }
) => {
	const searchParams = new URLSearchParams({ org_id: orgId });
	if (params?.status) searchParams.append('status', params.status);
	if (params?.department_id) searchParams.append('department_id', params.department_id);
	if (params?.limit) searchParams.append('limit', String(params.limit));
	if (params?.offset) searchParams.append('offset', String(params.offset));

	return apiCall<{ proposals: Proposal[]; total: number }>(
		`${AGENCYOS_API_BASE}/proposals/?${searchParams.toString()}`,
		token
	);
};

export const getProposal = async (token: string, proposalId: string, orgId: string) => {
	return apiCall<Proposal>(
		`${AGENCYOS_API_BASE}/proposals/${proposalId}?org_id=${orgId}`,
		token
	);
};

export const createProposal = async (
	token: string,
	orgId: string,
	data: {
		department_id: string;
		title: string;
		description: string;
		action_type: string;
		action_payload?: Record<string, unknown>;
		risk_level?: string;
		risk_reasoning?: string;
		chat_id?: string;
	}
) => {
	return apiCall<{ id: string; title: string; status: string }>(
		`${AGENCYOS_API_BASE}/proposals/?org_id=${orgId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const reviewProposal = async (
	token: string,
	proposalId: string,
	orgId: string,
	userId: string,
	data: { status: 'approved' | 'rejected'; review_note?: string }
) => {
	return apiCall<{ id: string; status: string }>(
		`${AGENCYOS_API_BASE}/proposals/${proposalId}/review?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const getProposalStats = async (token: string, orgId: string) => {
	return apiCall<ProposalStats>(
		`${AGENCYOS_API_BASE}/proposals/stats?org_id=${orgId}`,
		token
	);
};

// ─── Cortex Approvals ─────────────────────────────────────────

export interface CortexApproval {
	id: string;
	type: 'hire_agent' | 'custom';
	status: 'pending' | 'approved' | 'rejected' | 'revision_requested';
	payload: Record<string, unknown>;
	requested_by_agent_id?: string;
	requested_by_agent_name?: string;
	decision_note?: string;
	decided_by_user_id?: string;
	decided_at?: number;
	created_at: number;
	updated_at: number;
	synced_at: number;
}

export interface CortexApprovalStats {
	total: number;
	pending: number;
	approved: number;
	rejected: number;
	revision_requested: number;
	hire_agent: number;
}

export const getCortexApprovals = async (
	token: string,
	orgId: string,
	params?: { status?: string; approval_type?: string; limit?: number; offset?: number }
) => {
	const searchParams = new URLSearchParams({ org_id: orgId });
	if (params?.status) searchParams.append('status', params.status);
	if (params?.approval_type) searchParams.append('approval_type', params.approval_type);
	if (params?.limit) searchParams.append('limit', String(params.limit));
	if (params?.offset) searchParams.append('offset', String(params.offset));

	return apiCall<{ approvals: CortexApproval[]; total: number }>(
		`${AGENCYOS_API_BASE}/cortex-approvals/?${searchParams.toString()}`,
		token
	);
};

export const getCortexApproval = async (token: string, approvalId: string, orgId: string) => {
	return apiCall<CortexApproval>(
		`${AGENCYOS_API_BASE}/cortex-approvals/${approvalId}?org_id=${orgId}`,
		token
	);
};

export const getCortexApprovalStats = async (token: string, orgId: string) => {
	return apiCall<CortexApprovalStats>(
		`${AGENCYOS_API_BASE}/cortex-approvals/stats?org_id=${orgId}`,
		token
	);
};

export const getCortexPendingCount = async (token: string, orgId: string) => {
	return apiCall<{ count: number }>(
		`${AGENCYOS_API_BASE}/cortex-approvals/pending-count?org_id=${orgId}`,
		token
	);
};

export const approveCortexApproval = async (
	token: string,
	approvalId: string,
	orgId: string,
	userId: string,
	data: { decision_note?: string }
) => {
	return apiCall<{ id: string; status: string; message: string }>(
		`${AGENCYOS_API_BASE}/cortex-approvals/${approvalId}/approve?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const rejectCortexApproval = async (
	token: string,
	approvalId: string,
	orgId: string,
	userId: string,
	data: { decision_note?: string }
) => {
	return apiCall<{ id: string; status: string; message: string }>(
		`${AGENCYOS_API_BASE}/cortex-approvals/${approvalId}/reject?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(data)
		}
	);
};

export const syncCortexApprovals = async (
	token: string,
	orgId: string,
	cortexCompanyId: string
) => {
	return apiCall<{ success: boolean; stats: Record<string, number>; message: string }>(
		`${AGENCYOS_API_BASE}/cortex-approvals/sync?org_id=${orgId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ cortex_company_id: cortexCompanyId })
		}
	);
};

// ─── Employee Tabs ────────────────────────────────────────────

export interface EmployeeTab {
	id: string;
	agent_id: string;
	agent_name: string;
	agent_icon?: string;
	department: string;
	is_visible: boolean;
	is_pinned: boolean;
	sort_order: number;
	conversation_history?: Array<{ role: string; content: string; timestamp?: number }>;
	message_count?: number;
	last_interaction_at?: number;
	created_at: number;
	updated_at: number;
}

export const getEmployeeTabs = async (
	token: string,
	orgId: string,
	userId: string,
	visibleOnly: boolean = true
) => {
	const searchParams = new URLSearchParams({
		org_id: orgId,
		user_id: userId,
		visible_only: String(visibleOnly)
	});
	return apiCall<{ tabs: EmployeeTab[]; total: number }>(
		`${AGENCYOS_API_BASE}/employee-tabs/?${searchParams.toString()}`,
		token
	);
};

export const getEmployeeTab = async (
	token: string,
	tabId: string,
	orgId: string,
	userId: string
) => {
	return apiCall<EmployeeTab>(
		`${AGENCYOS_API_BASE}/employee-tabs/${tabId}?org_id=${orgId}&user_id=${userId}`,
		token
	);
};

export const getEmployeeTabByAgent = async (
	token: string,
	agentId: string,
	orgId: string,
	userId: string
) => {
	return apiCall<EmployeeTab>(
		`${AGENCYOS_API_BASE}/employee-tabs/by-agent/${agentId}?org_id=${orgId}&user_id=${userId}`,
		token
	);
};

export const toggleTabVisibility = async (
	token: string,
	tabId: string,
	orgId: string,
	userId: string,
	isVisible: boolean
) => {
	return apiCall<{ id: string; is_visible: boolean; message: string }>(
		`${AGENCYOS_API_BASE}/employee-tabs/${tabId}/visibility?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ is_visible: isVisible })
		}
	);
};

export const toggleTabPin = async (
	token: string,
	tabId: string,
	orgId: string,
	userId: string,
	isPinned: boolean
) => {
	return apiCall<{ id: string; is_pinned: boolean; message: string }>(
		`${AGENCYOS_API_BASE}/employee-tabs/${tabId}/pin?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ is_pinned: isPinned })
		}
	);
};

export const addTabMessage = async (
	token: string,
	tabId: string,
	orgId: string,
	userId: string,
	role: 'user' | 'assistant',
	content: string
) => {
	return apiCall<{ id: string; message_count: number; last_interaction_at: number }>(
		`${AGENCYOS_API_BASE}/employee-tabs/${tabId}/messages?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ role, content })
		}
	);
};

export const clearTabHistory = async (
	token: string,
	tabId: string,
	orgId: string,
	userId: string
) => {
	return apiCall<{ id: string; message: string }>(
		`${AGENCYOS_API_BASE}/employee-tabs/${tabId}/messages?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'DELETE'
		}
	);
};

export const syncEmployeeTabs = async (
	token: string,
	orgId: string,
	userId: string,
	cortexCompanyId: string
) => {
	return apiCall<{ success: boolean; stats: Record<string, number>; message: string }>(
		`${AGENCYOS_API_BASE}/employee-tabs/sync?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ cortex_company_id: cortexCompanyId })
		}
	);
};

export const reorderTabs = async (
	token: string,
	orgId: string,
	userId: string,
	tabIds: string[]
) => {
	return apiCall<{ success: boolean; message: string }>(
		`${AGENCYOS_API_BASE}/employee-tabs/reorder?org_id=${orgId}&user_id=${userId}`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ tab_ids: tabIds })
		}
	);
};
