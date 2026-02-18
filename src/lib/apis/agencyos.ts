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
