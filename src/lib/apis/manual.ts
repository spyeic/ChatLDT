export type Identity = {
	id: string;
	kind: 'guest' | 'user';
	name: string;
	admin: boolean;
	avatar: string;
	local_password: boolean;
	preferences: { language?: string; theme?: string };
	email?: string;
};
export type Message = {
	id: string;
	seq: number;
	author_id: string;
	side: 'user' | 'admin';
	content: string;
	attachments: string[];
	locked: boolean;
	cancelled: boolean;
	text_version: number;
};
export type Chat = {
	id: string;
	owner_id: string;
	owner_name: string;
	owner_kind: string;
	title: string;
	seq: number;
	revision: number;
	unread: number;
	next_side: string;
	current_round_id: string | null;
	turn_version: number;
	last_message_at: number;
	can_send: boolean;
	messages?: Message[];
	snippet?: string;
	user_read: number;
	admin_read: number;
};
let csrf = '';
export function setCSRF(value: string) {
	csrf = value;
}
export function getCSRF() {
	return csrf;
}
export async function api(path: string, method = 'GET', body?: unknown): Promise<any> {
	const multipart = body instanceof FormData;
	const response = await fetch('/api/v1/ldt' + path, {
		method,
		credentials: 'same-origin',
		headers: {
			...(method === 'GET' ? {} : { 'X-LDT-CSRF': csrf }),
			...(body && !multipart ? { 'Content-Type': 'application/json' } : {})
		},
		body: body ? ((multipart ? body : JSON.stringify(body)) as BodyInit) : undefined
	});
	const data = await response.json();
	if (!response.ok) {
		const error = new Error(
			typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
		);
		Object.assign(error, { status: response.status });
		throw error;
	}
	if (data.csrf) csrf = data.csrf;
	return data;
}
