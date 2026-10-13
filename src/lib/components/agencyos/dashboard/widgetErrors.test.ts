import { describe, expect, it } from 'vitest';
import { classifyWidgetError } from './widgetErrors';

describe('classifyWidgetError', () => {
	it('treats a WorkPipe 404 as not set up yet', () => {
		expect(classifyWidgetError('WorkPipe API error 404: SubAccount not found')).toBe('not-set-up');
		expect(
			classifyWidgetError('WorkPipe API error 404: Business not set up in WorkPipe')
		).toBe('not-set-up');
	});

	it('treats an org with no WorkPipe link as not set up yet', () => {
		expect(classifyWidgetError('Organization is not linked to WorkPipe')).toBe('not-set-up');
	});

	it('keeps entitlement denials as unavailable', () => {
		expect(classifyWidgetError('App access denied: WORKPIPE')).toBe('unavailable');
		expect(classifyWidgetError({ detail: 'Org admin access required' })).toBe('unavailable');
	});

	it('keeps real failures as errors', () => {
		expect(classifyWidgetError('WorkPipe API error 500: Internal server error')).toBe('error');
		expect(classifyWidgetError('WorkPipe request timed out')).toBe('error');
		expect(classifyWidgetError('WorkPipe API error 403: Forbidden')).toBe('error');
		expect(classifyWidgetError(new Error('network down'))).toBe('error');
		expect(classifyWidgetError(undefined)).toBe('error');
	});

	it('does not mistake a non-WorkPipe 404 for a WorkPipe one', () => {
		expect(classifyWidgetError('Organization not found')).toBe('error');
	});
});
