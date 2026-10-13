/**
 * How the dashboard shows a widget whose load() threw.
 *
 * `apiCall` throws the backend's `detail` string (the HTTP status itself is not kept), so
 * classification reads the detail text:
 *   - 'unavailable': the app isn't enabled for this workspace (403 "App access denied: …",
 *     "Org access denied", "Org admin access required") — expected, shown muted.
 *   - 'not-set-up': WorkPipe doesn't know this org or sub-account yet. Both are created the
 *     first time someone opens WorkPipe, so a brand-new org hits this until then. The
 *     backend forwards WorkPipe's status as "WorkPipe API error 404: …"; an org with no
 *     WorkPipe link at all is a 409 "Organization is not linked to WorkPipe".
 *   - 'error': anything else (5xx, timeouts, bad payloads) — a real failure, shown red.
 */
export type WidgetErrorKind = 'unavailable' | 'not-set-up' | 'error';

function detailText(err: unknown): string {
	if (typeof err === 'string') return err;
	if (err && typeof err === 'object') {
		const o = err as { detail?: unknown; message?: unknown };
		if (o.detail != null) return String(o.detail);
		if (o.message != null) return String(o.message);
	}
	return String(err ?? '');
}

export function classifyWidgetError(err: unknown): WidgetErrorKind {
	const msg = detailText(err);
	if (/access denied|access required/i.test(msg)) return 'unavailable';
	if (/WorkPipe API error 404\b/i.test(msg) || /not linked to WorkPipe/i.test(msg)) {
		return 'not-set-up';
	}
	return 'error';
}
