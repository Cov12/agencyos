import { describe, expect, it } from 'vitest';

import {
	agencyMessagesToOpenWebUIChat,
	createAgencyOSChatPayload,
	generateAgencyOSChatTitle,
	isAgencyOSChatForScope,
	openWebUIChatToAgencyMessages,
	type AgencyOSChatMessage,
	type AgencyOSChatMetadata
} from './agencyosChatHistory';

const metadata: AgencyOSChatMetadata = {
	agencyos: true,
	source: 'agencyos',
	org_id: 'org-1',
	sub_account_id: 'sub-1',
	department_slug: 'chief',
	target_type: 'chief',
	target_id: 'chief',
	employee_tab_id: null,
	agent_id: null,
	agent_name: 'WBIT Assistant'
};

const agencyMessages: AgencyOSChatMessage[] = [
	{
		id: 'user-1',
		role: 'user',
		content: 'Build a lead follow-up sequence',
		time: '2026-09-09T19:00:00.000Z'
	},
	{
		id: 'assistant-1',
		role: 'ai',
		persona: 'WBIT Assistant',
		content: 'I can draft that sequence.',
		time: '2026-09-09T19:01:00.000Z'
	}
];

describe('agencyosChatHistory', () => {
	it('converts AgencyOS messages into the Open WebUI chat shape', () => {
		const payload = agencyMessagesToOpenWebUIChat(agencyMessages, metadata);

		expect(payload.title).toBe('Build a lead follow-up sequence');
		expect(payload.models).toEqual(['agencyos']);
		expect(payload.agencyos).toEqual(metadata);
		expect(payload.history.currentId).toBe('assistant-1');
		expect(payload.history.messages['user-1']).toMatchObject({
			id: 'user-1',
			parentId: null,
			childrenIds: ['assistant-1'],
			role: 'user',
			content: 'Build a lead follow-up sequence'
		});
		expect(payload.history.messages['assistant-1']).toMatchObject({
			id: 'assistant-1',
			parentId: 'user-1',
			childrenIds: [],
			role: 'assistant',
			content: 'I can draft that sequence.',
			persona: 'WBIT Assistant'
		});
		expect(payload.messages.map((message) => message.id)).toEqual(['user-1', 'assistant-1']);
	});

	it('converts Open WebUI history back into AgencyOS messages in parent-child order', () => {
		const payload = agencyMessagesToOpenWebUIChat(agencyMessages, metadata);

		expect(openWebUIChatToAgencyMessages(payload)).toEqual([
			expect.objectContaining({
				id: 'user-1',
				role: 'user',
				content: 'Build a lead follow-up sequence'
			}),
			expect.objectContaining({
				id: 'assistant-1',
				role: 'ai',
				persona: 'WBIT Assistant',
				content: 'I can draft that sequence.'
			})
		]);
	});

	it('falls back to messages when history is absent', () => {
		const messages = openWebUIChatToAgencyMessages({
			messages: [
				{
					id: 'message-1',
					parentId: null,
					childrenIds: [],
					role: 'assistant',
					content: 'Hello',
					timestamp: 1788980460
				}
			]
		});

		expect(messages).toEqual([
			expect.objectContaining({ id: 'message-1', role: 'ai', content: 'Hello' })
		]);
	});

	it('generates a simple truncated title from the first user message', () => {
		expect(generateAgencyOSChatTitle(agencyMessages, 12)).toBe('Build a lea…');
		expect(generateAgencyOSChatTitle([{ id: 'ai-1', role: 'ai', content: 'Hi', time: '' }])).toBe(
			'AgencyOS Chat'
		);
	});

	it('creates payloads through the exported helper', () => {
		expect(createAgencyOSChatPayload(agencyMessages, metadata, { title: 'Custom' }).title).toBe(
			'Custom'
		);
	});

	it('filters AgencyOS chats by active org and sub-account scope', () => {
		expect(
			isAgencyOSChatForScope({ agencyos: metadata }, { org_id: 'org-1', sub_account_id: 'sub-1' })
		).toBe(true);
		expect(
			isAgencyOSChatForScope({ agencyos: metadata }, { org_id: 'org-2', sub_account_id: 'sub-1' })
		).toBe(false);
		expect(
			isAgencyOSChatForScope({ agencyos: metadata }, { org_id: 'org-1', sub_account_id: 'sub-2' })
		).toBe(false);
		expect(
			isAgencyOSChatForScope(
				{ agencyos: { ...metadata, source: 'agencyos_voice' } },
				{ org_id: 'org-1', sub_account_id: 'sub-1' }
			)
		).toBe(false);
	});
});
