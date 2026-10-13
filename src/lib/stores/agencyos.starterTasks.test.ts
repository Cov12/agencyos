import { describe, expect, it } from 'vitest';
import { STARTER_TASKS, starterTaskIssue, starterTasksFor } from './agencyos';

describe('starter tasks: selected departments → opt-in checklist', () => {
	it('maps each selected department to its starter tasks, in order', () => {
		const groups = starterTasksFor([
			{ id: 'marketing', name: 'Marketing' },
			{ id: 'finance', name: 'Finance' }
		]);
		expect(groups).toEqual([
			{
				deptId: 'marketing',
				deptName: 'Marketing',
				tasks: STARTER_TASKS.marketing
			},
			{
				deptId: 'finance',
				deptName: 'Finance',
				tasks: STARTER_TASKS.finance
			}
		]);
	});

	it('is empty when no department is selected', () => {
		expect(starterTasksFor([])).toEqual([]);
	});

	it('skips departments without a template', () => {
		expect(starterTasksFor([{ id: 'api-loaded', name: 'Custom' }])).toEqual([]);
	});

	it('offers two tasks for every onboarding department', () => {
		for (const id of ['marketing', 'sales', 'customer-success', 'finance', 'design', 'content', 'operations', 'engineering']) {
			expect(STARTER_TASKS[id]).toHaveLength(2);
		}
	});

	it('gives every task a title and a description', () => {
		for (const tasks of Object.values(STARTER_TASKS)) {
			for (const task of tasks) {
				expect(task.title.trim()).not.toBe('');
				expect(task.description.trim()).not.toBe('');
			}
		}
	});

	it('returns copies, so the checklist cannot mutate the templates', () => {
		const [group] = starterTasksFor([{ id: 'sales', name: 'Sales' }]);
		group.tasks[0].title = 'changed';
		expect(STARTER_TASKS.sales[0].title).toBe('Set up your first pipeline');
	});

	it('files the description with the department context', () => {
		expect(starterTaskIssue(STARTER_TASKS.sales[0], 'Sales')).toEqual({
			title: 'Set up your first pipeline',
			description:
				'Proposed stages and what moves a deal forward, ready to create in WorkPipe. ' +
				'Starter task for the Sales department, picked during onboarding.'
		});
	});
});
