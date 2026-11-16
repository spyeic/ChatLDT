<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { io, type Socket } from 'socket.io-client';
	import Sidebar from '$lib/components/layout/Sidebar.svelte';
	import MessageInput from './MessageInput.svelte';
	import Markdown from './Messages/Markdown.svelte';
	import MessageActions from './Messages/MessageActions.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import ActionIcon from '$lib/components/common/ActionIcon.svelte';
	import { api, getCSRF, type Identity, type Chat, type Message } from '$lib/apis/manual';
	import { initI18n, t, locale } from '$lib/i18n';

	type DraftImage = { file: File; url: string; name: string; id?: string };
	let identity: Identity | null = null;
	let ready = false,
		loadedDraft = false,
		busy = false,
		sidebarOpen = false,
		google = false;
	let current: Chat | null = null,
		chatList: Chat[] = [],
		userList: { id: string; kind: string; name: string }[] = [];
	let currentId = '',
		routeSeen: string | undefined,
		text = '',
		query = '',
		error = '',
		connected = false;
	let expanded: Record<string, boolean> = {};
	let imageDrafts: Record<string, DraftImage[]> = {};
	let pending: Record<string, any> = {};
	let animations: Record<string, string> = {};
	let animationFrames: Record<string, number> = {};
	let targetUser: string | null = null;
	let socket: Socket | undefined, channel: BroadcastChannel | undefined;
	let dialog: Modal;
	let sidebar: Sidebar;
	let welcomeShown = false;
	let desktopCollapsed = false;
	let following = true,
		awayFromBottom = false;
	let scrollFrame = 0;
	$: hasMessages = !!current?.messages?.length;
	$: needsRecipient = !!identity?.admin && !targetUser && !current;
	function trackScroll() {
		if (!mainScroll || !hasMessages) return;
		awayFromBottom = mainScroll.scrollHeight - mainScroll.clientHeight - mainScroll.scrollTop > 64;
		following = !awayFromBottom;
	}
	function scrollToBottom() {
		following = true;
		awayFromBottom = false;
		if (mainScroll) mainScroll.scrollTop = mainScroll.scrollHeight;
	}
	function observeMessages(node: HTMLElement) {
		const observer = new ResizeObserver(() => {
			cancelAnimationFrame(scrollFrame);
			scrollFrame = requestAnimationFrame(() => {
				if (following) scrollToBottom();
				else trackScroll();
			});
		});
		observer.observe(node);
		return { destroy: () => observer.disconnect() };
	}
	async function collapseSidebar() {
		desktopCollapsed = true;
		localStorage.setItem('ldt:sidebar-collapsed', 'true');
		await tick();
		document
			.querySelector<HTMLButtonElement>('.desktop-sidebar-trigger')
			?.focus({ preventScroll: true });
	}
	function expandSidebar() {
		desktopCollapsed = false;
		localStorage.setItem('ldt:sidebar-collapsed', 'false');
	}
	function welcomeEntrance(node: HTMLElement) {
		if (!welcomeShown) {
			welcomeShown = true;
			node.classList.add('welcome-enter');
		}
	}
	let modal = '',
		modalChat = '',
		modalUser = '',
		modalMessage: Message | null = null;
	let field = '',
		email = '',
		password = '',
		oldPassword = '',
		language = 'en-US',
		theme = 'system';
	let mainScroll: HTMLElement;
	let listGeneration = 0,
		selectGeneration = 0;
	let lastVisit = 0,
		searchTimer: ReturnType<typeof setTimeout>;
	$: routeId = $page.params.id || '';
	$: prefix = `ldt:${identity?.id || 'anonymous'}:`;
	$: images = imageDrafts[currentId] || [];
	$: ownSide = identity?.admin ? 'admin' : 'user';
	$: canSend = current ? current.can_send : !identity?.admin || !!targetUser;
	$: canCancel = !!(
		current &&
		!identity?.admin &&
		current.next_side === 'admin' &&
		current.current_round_id
	);
	$: translate = makeTranslator($locale);
	function makeTranslator(_language: string) {
		return (key: string) => t(key);
	}
	$: labels = {
		new: translate('New Chat'),
		search: translate('Search'),
		chats: translate('Chats'),
		guest: translate('Guest'),
		user: translate('User'),
		rename: translate('Rename'),
		delete: translate('Delete'),
		login: translate('Sign in'),
		close: translate('Close sidebar'),
		dismiss: translate('Dismiss')
	};
	$: if (ready && routeSeen !== routeId) {
		routeSeen = routeId;
		void select(routeId);
	}
	$: if (ready && loadedDraft && currentId) {
		localStorage.setItem(prefix + 'draft:' + currentId, text);
	}
	$: if (ready) {
		clearTimeout(searchTimer);
		const q = query;
		searchTimer = setTimeout(() => void refreshList(q), 180);
	}

	function fail(e: any) {
		error = e.message || String(e);
		if (e.status === 401) void refreshIdentity();
	}
	function localMeta(id = currentId) {
		try {
			return JSON.parse(localStorage.getItem(prefix + 'local:' + id) || 'null');
		} catch {
			return null;
		}
	}
	function migrateDrafts(from: string, to: string) {
		const old = `ldt:${from}:`,
			next = `ldt:${to}:`;
		for (const key of Object.keys(localStorage))
			if (key.startsWith(old)) {
				const dest = next + key.slice(old.length);
				if (!localStorage.getItem(dest))
					localStorage.setItem(dest, localStorage.getItem(key) || '');
				localStorage.removeItem(key);
			}
	}
	function clearNamespace(id: string) {
		for (const key of Object.keys(localStorage))
			if (key.startsWith(`ldt:${id}:`)) localStorage.removeItem(key);
	}
	function saveGuestDrafts() {
		if (identity?.kind !== 'guest') return;
		const source = `ldt:${identity.id}:`;
		const values: Record<string, string> = {};
		for (const key of Object.keys(localStorage))
			if (key.startsWith(source + 'draft:') || key.startsWith(source + 'local:'))
				values[key.slice(source.length)] = localStorage.getItem(key) || '';
		localStorage.setItem(
			'ldt:guest-transition:' + identity.id,
			JSON.stringify({ from: identity.id, at: Date.now(), values })
		);
	}
	function restoreGuestDrafts(data: any) {
		for (const key of Object.keys(localStorage))
			if (key.startsWith('ldt:guest-transition:')) {
				try {
					const saved = JSON.parse(localStorage.getItem(key) || 'null');
					if (data.identity && data.merged_guest_ids?.includes(saved.from)) {
						for (const [suffix, value] of Object.entries(saved.values))
							if (suffix.startsWith('draft:') || suffix.startsWith('local:')) {
								const destination = `ldt:${data.identity.id}:${suffix}`;
								if (!localStorage.getItem(destination))
									localStorage.setItem(destination, String(value));
							}
						localStorage.removeItem(key);
					} else if (
						Date.now() - saved.at > 600000 ||
						(data.identity && data.identity.id !== saved.from)
					)
						localStorage.removeItem(key);
				} catch {
					localStorage.removeItem(key);
				}
			}
	}
	async function refreshIdentity(merged?: string) {
		const old = identity?.id || localStorage.getItem('ldt:lastIdentity');
		const data = await api('/session');
		restoreGuestDrafts(data);
		if (merged && data.identity) migrateDrafts(merged, data.identity.id);
		if (!identity && data.identity?.kind === 'guest') migrateDrafts('anonymous', data.identity.id);
		if (old && data.identity && old !== data.identity.id && data.merged_guest_ids?.includes(old))
			migrateDrafts(old, data.identity.id);
		if (old && !data.identity) {
			clearNamespace(old);
			clearNamespace('anonymous');
		}
		if (!identity && data.identity?.kind === 'user') clearNamespace('anonymous');
		const changed = identity?.id !== data.identity?.id;
		if (changed) {
			loadedDraft = false;
			const preserve =
				(!identity && data.identity?.kind === 'guest') ||
				data.merged_guest_ids?.includes(identity?.id);
			if (!preserve) {
				for (const list of Object.values(imageDrafts))
					for (const image of list) URL.revokeObjectURL(image.url);
				imageDrafts = {};
			}
		}
		identity = data.identity;
		google = data.google;
		if (identity) localStorage.setItem('ldt:lastIdentity', identity.id);
		else localStorage.removeItem('ldt:lastIdentity');
		language =
			identity?.preferences.language || (navigator.language.startsWith('zh') ? 'zh-CN' : 'en-US');
		theme = identity?.preferences.theme || 'system';
		await initI18n(language);
		applyTheme();
		if (changed) {
			loadedDraft = false;
			current = null;
			chatList = [];
			userList = [];
			pending = {};
			try {
				expanded = JSON.parse(localStorage.getItem(`ldt:${identity?.id}:expanded`) || '{}');
			} catch {
				expanded = {};
			}
			await select(routeId);
			connectSocket();
		}
		await refreshList();
		if (identity?.admin) userList = await api('/users');
	}
	function applyTheme() {
		const dark =
			theme === 'dark' ||
			(theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
		document.documentElement.classList.toggle('dark', dark);
		document.documentElement.style.removeProperty('background-color');
		localStorage.setItem('ldt:theme', theme);
		document
			.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
			?.setAttribute('content', dark ? '#171717' : '#ffffff');
	}
	function connectSocket() {
		socket?.disconnect();
		connected = false;
		if (!identity) return;
		socket = io({
			path: '/ws/socket.io',
			auth: { csrf: getCSRF() },
			transports: ['websocket', 'polling']
		});
		socket.on('connect', () => {
			connected = true;
			void refreshList();
			if (current) void refreshCurrent(false);
		});
		socket.on('disconnect', (reason) => {
			connected = false;
			if (reason === 'io server disconnect') void refreshIdentity().then(() => connectSocket());
		});
		socket.on('ldt:changed', async (event) => {
			if (event.event === 'deleted') {
				localStorage.removeItem(prefix + 'draft:' + event.chat_id);
				localStorage.removeItem(prefix + 'intent:' + event.chat_id);
				if (currentId === event.chat_id) {
					current = null;
					text = '';
					delete imageDrafts[currentId];
					await goto('/');
				}
			} else if (currentId === event.chat_id) {
				await refreshCurrent(event.event === 'message' ? event.message_id : false);
			}
			await refreshList();
		});
	}
	async function refreshList(q = query) {
		const generation = ++listGeneration;
		if (!identity) {
			chatList = [];
			return;
		}
		try {
			const list = await api('/chats?q=' + encodeURIComponent(q));
			if (generation !== listGeneration) return;
			chatList = list;
			for (const key of Object.keys(localStorage))
				if (key.startsWith(prefix + 'local:')) {
					const id = key.slice((prefix + 'local:').length);
					if (list.some((c: Chat) => c.id === id)) continue;
					const meta = localMeta(id);
					const name = meta?.target_user_id
						? userList.find((u) => u.id === meta.target_user_id)?.name || ''
						: identity.name;
					const title =
						meta?.title ||
						localStorage.getItem(prefix + 'draft:' + id)?.slice(0, 40) ||
						translate('New Chat');
					if (!q || title.toLowerCase().includes(q.toLowerCase()))
						chatList = [
							...chatList,
							{
								id,
								owner_id: meta?.target_user_id || identity.id,
								owner_name: name,
								owner_kind: identity.kind,
								title,
								seq: 0,
								revision: 0,
								unread: 0,
								next_side: ownSide,
								current_round_id: null,
								turn_version: 0,
								last_message_at: 0,
								can_send: true,
								user_read: 0,
								admin_read: 0
							}
						];
				}
			if (!q) {
				const ids = new Set(list.map((c: Chat) => c.id));
				for (const key of Object.keys(localStorage))
					if (key.startsWith(prefix + 'draft:')) {
						const id = key.slice((prefix + 'draft:').length);
						if (id !== 'welcome' && !ids.has(id) && !localMeta(id)) localStorage.removeItem(key);
					}
			}
		} catch (e) {
			fail(e);
		}
	}
	async function select(id: string) {
		following = true;
		awayFromBottom = false;
		const generation = ++selectGeneration;
		loadedDraft = false;
		current = null;
		currentId = id || 'welcome';
		targetUser = localMeta()?.target_user_id || null;
		text = localStorage.getItem(prefix + 'draft:' + currentId) || '';
		try {
			pending[currentId] = JSON.parse(
				localStorage.getItem(prefix + 'intent:' + currentId) || 'null'
			);
		} catch {
			pending[currentId] = null;
		}
		if (id && !identity && !localMeta(id)) {
			await goto('/');
			return;
		}
		if (id && identity && !localMeta(id)) {
			try {
				const data = await api('/chats/' + id);
				if (generation !== selectGeneration) return;
				current = data;
			} catch (e: any) {
				if (generation !== selectGeneration) return;
				fail(e);
				if (e.status === 404 || e.status === 403) {
					localStorage.removeItem(prefix + 'draft:' + id);
					await goto('/');
				}
			}
		}
		if (generation === selectGeneration) {
			loadedDraft = true;
			await tick();
			scrollToBottom();
			await markRead();
		}
	}
	async function refreshCurrent(animate: string | false = false) {
		const id = currentId;
		if (!current || !identity) return;
		try {
			const next: Chat = await api('/chats/' + id);
			if (currentId !== id || (current && next.revision < current.revision)) return;
			const oldMessages = new Map((current?.messages || []).map((m) => [m.id, m]));
			for (const m of next.messages || []) {
				if (oldMessages.get(m.id)?.text_version !== m.text_version) stopAnimation(m.id);
			}
			current = next;
			if (animate && !identity.admin && document.visibilityState === 'visible') {
				const message = next.messages?.find((m) => m.id === animate);
				if (message?.side === 'admin' && !oldMessages.has(animate)) animateMessage(message);
			}
			await tick();
			await markRead();
		} catch (e: any) {
			if (e.status === 404) {
				localStorage.removeItem(prefix + 'draft:' + id);
				if (currentId === id) await goto('/');
			} else fail(e);
		}
	}
	function stopAnimation(id: string) {
		if (animationFrames[id]) cancelAnimationFrame(animationFrames[id]);
		delete animations[id];
		animations = { ...animations };
	}
	function animateMessage(message: Message) {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		const start = performance.now(),
			content = message.content;
		const frame = (at: number) => {
			const n = Math.floor(
				Math.min(1, (at - start) / Math.min(3000, 300 + content.length * 12)) * content.length
			);
			animations = { ...animations, [message.id]: content.slice(0, n) };
			if (n < content.length) animationFrames[message.id] = requestAnimationFrame(frame);
			else stopAnimation(message.id);
		};
		animations = { ...animations, [message.id]: '' };
		animationFrames[message.id] = requestAnimationFrame(frame);
	}
	async function markRead() {
		if (!current || document.visibilityState !== 'visible' || !mainScroll) return;
		const c = current;
		// Wait for the conversation's messages to have entered the DOM; expanding
		// a group or receiving a hidden-tab event never advances read state.
		if ((identity?.admin ? c.admin_read : c.user_read) >= c.seq) return;
		try {
			await api('/chats/' + c.id + '/read', 'POST', { seq: c.seq });
		} catch (e) {
			fail(e);
		}
	}
	async function newChat(target: string | null = null) {
		const id = crypto.randomUUID();
		localStorage.setItem(prefix + 'local:' + id, JSON.stringify({ target_user_id: target }));
		await goto('/c/' + id);
		await refreshList();
		sidebarOpen = false;
	}
	function addImages(files: File[]) {
		if (images.length + files.length > 8) {
			error = translate('Up to 8 images per message');
			return;
		}
		for (const file of files)
			if (
				!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
				file.size > 40 * 1024 * 1024
			) {
				error = translate('Use JPEG, PNG or WebP images up to 40 MB');
				return;
			}
		imageDrafts = {
			...imageDrafts,
			[currentId]: [
				...images,
				...files.map((file) => ({ file, url: URL.createObjectURL(file), name: file.name }))
			]
		};
	}
	function removeImage(index: number) {
		URL.revokeObjectURL(images[index].url);
		imageDrafts = { ...imageDrafts, [currentId]: images.filter((_, i) => i !== index) };
	}
	async function send(retry = false) {
		if (busy || (!retry && !canSend)) return;
		if (!retry && !text.trim() && !images.length) return;
		if (!identity) {
			openModal('nickname');
			return;
		}
		busy = true;
		error = '';
		let id = currentId;
		const sentText = text,
			sentState = current,
			sentTarget = targetUser;
		const sentImages = [...images];
		try {
			if (id === 'welcome') {
				id = crypto.randomUUID();
				localStorage.setItem(
					prefix + 'local:' + id,
					JSON.stringify({ target_user_id: targetUser })
				);
				localStorage.setItem(prefix + 'draft:' + id, text);
				imageDrafts[id] = images;
				delete imageDrafts.welcome;
				localStorage.removeItem(prefix + 'draft:welcome');
				await goto('/c/' + id);
				await tick();
			}
			let payload = retry ? pending[id] : null;
			if (!payload) {
				const attachments = [];
				for (const image of sentImages) {
					if (!image.id) {
						const form = new FormData();
						form.append('file', image.file);
						image.id = (await api('/files', 'POST', form)).id;
					}
					attachments.push(image.id);
				}
				payload = {
					key: crypto.randomUUID(),
					chat_id: id,
					round_id: sentState?.current_round_id || null,
					turn_version: sentState?.turn_version || 0,
					content: sentText,
					attachments,
					target_user_id: sentTarget,
					initial_title: localMeta(id)?.title || null
				};
				pending[id] = payload;
				localStorage.setItem(prefix + 'intent:' + id, JSON.stringify(payload));
			}
			await api('/send', 'POST', payload);
			delete pending[id];
			pending = { ...pending };
			localStorage.removeItem(prefix + 'intent:' + id);
			if (localStorage.getItem(prefix + 'draft:' + id) === payload.content)
				localStorage.removeItem(prefix + 'draft:' + id);
			localStorage.removeItem(prefix + 'local:' + id);
			const submitted = (imageDrafts[id] || []).filter(
				(image) => image.id && payload.attachments.includes(image.id)
			);
			for (const image of submitted) URL.revokeObjectURL(image.url);
			imageDrafts = {
				...imageDrafts,
				[id]: (imageDrafts[id] || []).filter((image) => !submitted.includes(image))
			};
			if (currentId === id) {
				if (text === payload.content) text = '';
				following = true;
				current = await api('/chats/' + id);
				await tick();
				await markRead();
			}
			await refreshList();
		} catch (e: any) {
			fail(e);
			if (e.status === 409 || e.status === 403 || e.status === 404) {
				delete pending[id];
				pending = { ...pending };
				localStorage.removeItem(prefix + 'intent:' + id);
				if (current) await refreshCurrent();
			}
		} finally {
			busy = false;
		}
	}
	async function cancel() {
		if (!current || !canCancel || busy) return;
		const c = current;
		busy = true;
		try {
			await api('/chats/' + c.id + '/cancel', 'POST', {
				key: crypto.randomUUID(),
				round_id: c.current_round_id,
				turn_version: c.turn_version
			});
			await refreshCurrent();
		} catch (e) {
			fail(e);
			await refreshCurrent();
		} finally {
			busy = false;
		}
	}
	async function openModal(type: string, id = currentId, message: Message | null = null) {
		if (identity?.admin && ['new', 'settings'].includes(type))
			void api('/users')
				.then((list) => (userList = list))
				.catch(fail);
		await sidebar?.close();
		error = '';
		modal = type;
		modalChat = id;
		modalMessage = message;
		field =
			type === 'edit'
				? message?.content || ''
				: type === 'rename'
					? chatList.find((c) => c.id === id)?.title || current?.title || ''
					: identity?.name || '';
		password = '';
		oldPassword = '';
		dialog.showModal();
	}
	async function googleLogin() {
		try {
			saveGuestDrafts();
			const result = await api('/oauth/google/start', 'POST');
			location.href = result.url;
		} catch (e) {
			fail(e);
		}
	}
	async function modalSubmit() {
		if (busy) return;
		busy = true;
		error = '';
		let autoSend = false;
		try {
			if (modal === 'nickname') {
				const draft = text,
					oldId = currentId;
				await api('/guest', 'POST', { name: field });
				await refreshIdentity();
				text = draft;
				localStorage.setItem(prefix + 'draft:' + oldId, draft);
				autoSend = true;
				channel?.postMessage('identity');
			} else if (modal === 'login' || modal === 'signup') {
				saveGuestDrafts();
				const result = await api(modal === 'login' ? '/signin' : '/signup', 'POST', {
					email,
					password,
					...(modal === 'signup' ? { name: field } : {})
				});
				await refreshIdentity(result.merged_guest);
				channel?.postMessage('identity');
				await goto('/');
			} else if (modal === 'settings') {
				await api('/profile', 'PATCH', { name: field, language, theme });
				if (password) {
					await api('/password', 'POST', { old_password: oldPassword, new_password: password });
					connectSocket();
				}
				await refreshIdentity();
				channel?.postMessage('identity');
			} else if (modal === 'rename') {
				if (localMeta(modalChat))
					localStorage.setItem(
						prefix + 'local:' + modalChat,
						JSON.stringify({ ...localMeta(modalChat), title: field })
					);
				else await api('/chats/' + modalChat + '/title', 'PATCH', { title: field });
				await refreshList();
				if (currentId === modalChat) await refreshCurrent();
			} else if (modal === 'delete-chat') {
				if (!localMeta(modalChat)) await api('/chats/' + modalChat, 'DELETE');
				localStorage.removeItem(prefix + 'draft:' + modalChat);
				localStorage.removeItem(prefix + 'local:' + modalChat);
				await refreshList();
				if (currentId === modalChat) await goto('/');
			} else if (modal === 'delete-user') {
				await api('/users/' + modalUser, 'DELETE');
				userList = await api('/users');
				await refreshList();
			} else if (modal === 'new') {
				if (!modalUser) throw new Error(translate('Choose a registered user'));
				await newChat(modalUser);
			} else if (modal === 'edit' && modalMessage) {
				await api('/chats/' + modalChat + '/messages/' + modalMessage.id, 'PATCH', {
					key: crypto.randomUUID(),
					text_version: modalMessage.text_version,
					content: field
				});
				await refreshCurrent();
			}
			await dialog.close();
		} catch (e) {
			fail(e);
		} finally {
			busy = false;
			if (autoSend) await send();
		}
	}
	async function signout() {
		try {
			await api('/signout', 'POST');
			await dialog.close();
			await refreshIdentity();
			channel?.postMessage('identity');
			await goto('/');
		} catch (e) {
			fail(e);
		}
	}
	function toggleGroup(id: string) {
		expanded = { ...expanded, [id]: !expanded[id] };
		localStorage.setItem(prefix + 'expanded', JSON.stringify(expanded));
	}
	async function visit() {
		if (!identity || document.visibilityState !== 'visible' || Date.now() - lastVisit < 60000)
			return;
		lastVisit = Date.now();
		try {
			await api('/visit', 'POST');
		} catch (e) {
			fail(e);
		}
	}
	onMount(() => {
		desktopCollapsed = localStorage.getItem('ldt:sidebar-collapsed') === 'true';
		void (async () => {
			try {
				await refreshIdentity();
				ready = true;
				if ($page.url.searchParams.get('error')) error = $page.url.searchParams.get('error') || '';
				await visit();
			} catch (e) {
				fail(e);
			}
		})();
		channel = new BroadcastChannel('ldt-identity');
		channel.onmessage = () => void refreshIdentity();
		const visible = () => {
			if (document.visibilityState === 'visible') {
				void refreshIdentity().then(() => {
					void visit();
					return refreshCurrent(false);
				});
			}
		};
		const interact = () => void visit();
		const media = matchMedia('(prefers-color-scheme: dark)');
		document.addEventListener('visibilitychange', visible);
		document.addEventListener('pointerdown', interact);
		document.addEventListener('keydown', interact);
		media.addEventListener('change', applyTheme);
		return () => {
			socket?.disconnect();
			channel?.close();
			clearTimeout(searchTimer);
			cancelAnimationFrame(scrollFrame);
			document.removeEventListener('visibilitychange', visible);
			document.removeEventListener('pointerdown', interact);
			document.removeEventListener('keydown', interact);
			media.removeEventListener('change', applyTheme);
			for (const frame of Object.values(animationFrames)) cancelAnimationFrame(frame);
			for (const list of Object.values(imageDrafts))
				for (const image of list) URL.revokeObjectURL(image.url);
		};
	});
</script>

<svelte:head><title>{current?.title ? current.title + ' · ' : ''}ChatLDT</title></svelte:head>
<div class="app-shell flex w-full text-gray-900 dark:text-gray-100">
	<Sidebar
		bind:this={sidebar}
		collapsed={desktopCollapsed}
		onCollapse={collapseSidebar}
		onClose={() => (sidebarOpen = false)}
		{identity}
		chats={chatList}
		selected={currentId}
		bind:query
		open={sidebarOpen}
		{labels}
		{expanded}
		onToggle={toggleGroup}
		onSelect={async (id) => {
			await goto('/c/' + id);
			sidebarOpen = false;
		}}
		onNew={() => (identity?.admin ? openModal('new') : newChat())}
		onSettings={() => openModal('settings')}
		onLogin={() => openModal('login')}
		onRename={(id) => openModal('rename', id)}
		onDelete={(id) => openModal('delete-chat', id)}
	/>
	<div class="chat-pane flex flex-col flex-1 min-w-0 h-full">
		<header class="chat-header flex items-center gap-3 px-4 py-3">
			<button
				class="icon-button mobile-sidebar-trigger"
				aria-label={translate('Toggle sidebar')}
				aria-expanded={sidebarOpen}
				aria-controls="chat-sidebar"
				on:click={() => (sidebarOpen = !sidebarOpen)}><ActionIcon name="sidebar" /></button
			>
			{#if desktopCollapsed}<button
					class="icon-button desktop-sidebar-trigger"
					aria-label={translate('Open sidebar')}
					title={translate('Open sidebar')}
					aria-controls="chat-sidebar"
					aria-expanded="false"
					on:click={expandSidebar}><ActionIcon name="sidebar" /></button
				>{/if}
			<span class="header-title truncate"
				>{current?.title ||
					(targetUser
						? userList.find((u) => u.id === targetUser)?.name
						: translate('New Chat'))}</span
			>{#if identity && !connected}<span class="text-xs text-gray-500"
					>{translate('Reconnecting…')}</span
				>{/if}
		</header>
		{#if error}<p
				role="alert"
				class="mx-4 p-3 rounded-xl bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-200"
			>
				{error}<button
					class="icon-button ml-3"
					aria-label={translate('Dismiss')}
					on:click={() => (error = '')}><ActionIcon name="close" /></button
				>
			</p>{/if}
		<div class="conversation-workspace" class:welcome-workspace={!hasMessages}>
			<main
				bind:this={mainScroll}
				class:welcome-scroll={!hasMessages}
				on:scroll={trackScroll}
				class="chat-scroll flex-1 min-h-0 overflow-y-auto"
			>
				{#if current?.messages?.length}
					<div class="message-list conversation-width" use:observeMessages>
						{#each current.messages as message (message.id)}
							<article
								class="message-row flex"
								class:justify-end={message.side === ownSide}
								data-message-id={message.id}
								aria-label={translate(message.side === ownSide ? 'Your message' : 'Their message')}
							>
								<div class="message-column" class:own={message.side === ownSide}>
									<div class="message-bubble">
										{#if message.attachments.length}<div
												class="flex flex-wrap gap-2"
												class:mb-3={!!message.content}
											>
												{#each message.attachments as fid}<a
														href={'/api/v1/ldt/files/' + fid}
														target="_blank"
														rel="noopener noreferrer"
														><img
															src={'/api/v1/ldt/files/' + fid}
															alt={translate('Attached image')}
															class="max-h-72 max-w-full rounded-xl"
															loading="lazy"
														/></a
													>{/each}
											</div>{/if}
										<Markdown content={animations[message.id] ?? message.content} />
										{#if message.cancelled}<span class="text-xs text-gray-500"
												>{translate('Cancelled')}</span
											>{/if}
									</div>
									<MessageActions
										content={message.content}
										own={message.side === ownSide}
										editable={message.side === ownSide &&
											message.seq === current.seq &&
											!message.locked &&
											!message.cancelled}
										onEdit={() => openModal('edit', currentId, message)}
									/>
								</div>
							</article>
						{/each}
						{#if canCancel}<div class="thinking text-gray-500 pb-3">
								{translate('Thinking…')}
							</div>{/if}
					</div>
				{/if}
			</main>
			<div class="composer-region">
				{#if hasMessages && awayFromBottom}
					<button
						class="jump-bottom icon-button"
						aria-label={translate('Back to bottom')}
						title={translate('Back to bottom')}
						on:click={scrollToBottom}><ActionIcon name="down" /></button
					>
				{/if}
				{#if !hasMessages}
					<div class="welcome-group conversation-width" use:welcomeEntrance>
						<img src="/chatldt-icon-v1.svg" alt="ChatLDT" />
						<h1 class="welcome-title">
							{translate(
								needsRecipient
									? 'Choose a user to start a conversation'
									: 'How can I help you today?'
							)}
						</h1>
						{#if needsRecipient}<button class="recipient-button" on:click={() => openModal('new')}
								><ActionIcon name="plus" />{translate('Choose a registered user')}</button
							>{/if}
					</div>
				{/if}
				{#if pending[currentId]}<button
						class="text-sm underline p-2"
						disabled={busy}
						on:click={() => send(true)}>{translate('Retry previous send')}</button
					>{/if}
				<div class="editor-slot" hidden={needsRecipient} inert={needsRecipient}>
					<MessageInput
						bind:text
						disabled={!canSend}
						{busy}
						{canCancel}
						label={translate('Send a message')}
						sendLabel={translate('Send')}
						cancelLabel={translate('Stop generating')}
						{images}
						onSend={() => send()}
						onCancel={cancel}
						onFiles={addImages}
						onRemove={removeImage}
					/>
				</div>
			</div>
		</div>
	</div>
</div>
<Modal
	bind:this={dialog}
	labelledby="dialog-title"
	on:close={() => {
		password = '';
		oldPassword = '';
		modal = '';
	}}
>
	<h2 id="dialog-title" class="text-xl font-semibold mb-5">
		{t(
			(
				{
					nickname: 'Choose a nickname',
					login: 'Sign in',
					signup: 'Sign up',
					settings: 'Settings',
					rename: 'Rename',
					'delete-chat': 'Delete conversation?',
					'delete-user': 'Delete identity and all conversations?',
					new: 'Start a conversation',
					edit: 'Edit message'
				} as Record<string, string>
			)[modal] || 'ChatLDT'
		)}
	</h2>
	<form on:submit|preventDefault={modalSubmit} class="space-y-4">
		{#if ['nickname', 'signup', 'settings', 'rename', 'edit'].includes(modal)}
			<label class="block" for="modal-field"
				>{t(modal === 'edit' ? 'Message' : modal === 'rename' ? 'Title' : 'Nickname')}</label
			>
			{#if modal === 'edit'}<textarea
					id="modal-field"
					class="border rounded-xl w-full p-3 bg-transparent"
					rows="6"
					maxlength="32000"
					bind:value={field}
				></textarea>{:else}<input
					id="modal-field"
					readonly={modal === 'settings' && !!identity?.admin}
					class="border rounded-xl w-full p-3 bg-transparent"
					maxlength="80"
					required
					bind:value={field}
				/>{/if}
		{/if}
		{#if modal === 'login' || modal === 'signup'}
			<label class="block" for="auth-email">{translate('Email')}</label><input
				id="auth-email"
				type="email"
				autocomplete="email"
				class="border rounded-xl w-full p-3 bg-transparent"
				required
				bind:value={email}
			/>
			<label class="block" for="auth-password">{translate('Password')}</label><input
				id="auth-password"
				type="password"
				autocomplete={modal === 'signup' ? 'new-password' : 'current-password'}
				minlength={modal === 'signup' ? 12 : 1}
				class="border rounded-xl w-full p-3 bg-transparent"
				required
				bind:value={password}
			/>
			<button
				type="button"
				class="underline"
				on:click={() => {
					modal = modal === 'login' ? 'signup' : 'login';
					password = '';
				}}>{t(modal === 'login' ? 'Sign up' : 'Sign in')}</button
			>
			{#if google}<button type="button" class="border rounded-xl w-full p-3" on:click={googleLogin}
					>{translate('Continue with Google')}</button
				>{/if}
		{/if}
		{#if modal === 'settings'}
			<label class="block" for="language">{translate('Language')}</label><select
				id="language"
				class="border rounded-xl p-2 bg-transparent"
				bind:value={language}
				><option value="zh-CN">中文</option><option value="en-US">English</option></select
			>
			<label class="block" for="theme">{translate('Theme')}</label><select
				id="theme"
				class="border rounded-xl p-2 bg-transparent"
				bind:value={theme}
				><option value="system">{translate('System')}</option><option value="light"
					>{translate('Light')}</option
				><option value="dark">{translate('Dark')}</option></select
			>
			{#if identity?.kind === 'guest'}
				<div class="flex gap-4">
					<button type="button" class="underline" on:click={() => (modal = 'login')}
						>{translate('Sign in')}</button
					><button type="button" class="underline" on:click={() => (modal = 'signup')}
						>{translate('Sign up')}</button
					>
				</div>
			{/if}
			{#if identity?.kind === 'user'}
				<label class="block" for="avatar">{translate('Avatar')}</label><input
					id="avatar"
					type="file"
					accept="image/jpeg,image/png,image/webp"
					on:change={async (event) => {
						const file = event.currentTarget.files?.[0];
						if (file) {
							const form = new FormData();
							form.append('file', file);
							try {
								await api('/avatar', 'POST', form);
								await refreshIdentity();
							} catch (e) {
								fail(e);
							}
						}
					}}
				/>
				{#if identity.local_password}<label class="block" for="old-password"
						>{translate('Current password')}</label
					><input
						id="old-password"
						type="password"
						autocomplete="current-password"
						class="border rounded-xl p-2 bg-transparent w-full"
						bind:value={oldPassword}
					/><label class="block" for="new-password">{translate('New password (optional)')}</label
					><input
						id="new-password"
						type="password"
						autocomplete="new-password"
						minlength="12"
						class="border rounded-xl p-2 bg-transparent w-full"
						bind:value={password}
					/>{/if}
				{#if google}<button type="button" class="underline block" on:click={googleLogin}
						>{translate('Link Google account')}</button
					>{/if}
			{/if}
			{#if identity?.admin}<label class="block" for="delete-user"
					>{translate('Delete user or guest')}</label
				><select
					id="delete-user"
					class="border rounded-xl p-2 bg-transparent w-full"
					bind:value={modalUser}
					><option value="">{translate('Choose an identity')}</option>{#each userList as u}<option
							value={u.id}
							>{u.name} ({u.kind === 'guest' ? translate('Guest') : translate('User')})</option
						>{/each}</select
				><button
					type="button"
					class="text-red-600"
					disabled={!modalUser}
					on:click={() => (modal = 'delete-user')}>{translate('Delete')}</button
				>{/if}
			<button type="button" class="underline block" on:click={signout}
				>{translate('Sign out')}</button
			>
		{/if}
		{#if modal === 'new'}<label for="target-user">{translate('Registered user')}</label><select
				id="target-user"
				class="border rounded-xl p-2 bg-transparent w-full"
				required
				bind:value={modalUser}
				><option value="">{translate('Choose a registered user')}</option
				>{#each userList.filter((u) => u.kind === 'user') as u}<option value={u.id}>{u.name}</option
					>{/each}</select
			>{/if}
		{#if modal.startsWith('delete-')}<p>
				{translate('This permanently removes the selected data and revokes access.')}
			</p>{/if}
		{#if error}<p role="alert" class="text-red-600">{error}</p>{/if}
		<div class="flex justify-end gap-3 pt-3">
			<button type="button" class="border rounded-xl px-4 py-2" on:click={() => dialog.close()}
				>{translate('Cancel')}</button
			><button
				type="submit"
				class="primary-button rounded-xl px-4 py-2 bg-gray-900 text-white dark:bg-white dark:text-gray-900"
				disabled={busy}>{translate(modal.startsWith('delete-') ? 'Delete' : 'Confirm')}</button
			>
		</div>
	</form>
</Modal>

<style>
	.mobile-sidebar-trigger {
		display: none;
	}
	.app-shell {
		height: 100vh;
		height: 100dvh;
		background: var(--app-bg);
		overflow: hidden;
	}
	.chat-pane {
		min-height: 0;
	}
	.chat-header {
		flex-shrink: 0;
		min-height: 60px;
	}
	.header-title {
		font-size: 15px;
		font-weight: 500;
		color: var(--muted-text);
	}
	.conversation-workspace {
		position: relative;
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}
	.welcome-workspace {
		justify-content: center;
		padding-bottom: clamp(40px, 14dvh, 150px);
		overflow-y: auto;
	}
	.welcome-scroll {
		display: none;
	}
	.chat-scroll {
		overscroll-behavior: contain;
		overflow-x: hidden;
	}
	.message-list {
		padding-block: 24px 40px;
	}
	.message-row + .message-row {
		margin-top: 24px;
	}
	.composer-region {
		position: relative;
		flex-shrink: 0;
	}
	.welcome-group {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
		margin-bottom: 28px;
		text-align: center;
	}
	.welcome-group > img {
		width: 30px;
		height: 30px;
	}
	.welcome-title {
		font-size: clamp(1.75rem, 1.4rem + 0.7vw, 2rem);
		line-height: 1.3;
		font-weight: 450;
		letter-spacing: -0.025em;
		text-wrap: balance;
	}
	.recipient-button {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		margin-top: 8px;
		border-radius: 24px;
		padding: 12px 18px;
		background: var(--composer-bg);
		font-size: 14px;
	}
	.jump-bottom {
		position: absolute;
		z-index: 2;
		top: -48px;
		left: 50%;
		translate: -50% 0;
		width: 36px;
		height: 36px;
		border: 1px solid var(--subtle-border);
		border-radius: 50%;
		background: var(--panel-bg);
		box-shadow: 0 2px 6px #0001;
	}
	.message-column {
		min-width: 0;
		max-width: 100%;
		width: 100%;
	}
	.message-column.own {
		width: fit-content;
		max-width: 82%;
	}
	.message-bubble {
		min-width: 0;
		border: 0;
		box-shadow: none;
		padding: 4px 0;
	}
	.own .message-bubble {
		background: var(--bubble-bg);
		border-radius: 24px;
		padding: 12px 20px;
	}
	.message-bubble :global(img) {
		object-fit: contain;
		width: auto;
		height: auto;
		max-width: 100%;
		max-height: 288px;
	}
	.message-bubble :global(a:has(img)) {
		max-width: 100%;
	}
	.message-bubble :global(.markdown > :first-child) {
		margin-block-start: 0;
	}
	.message-bubble :global(.markdown > :last-child) {
		margin-block-end: 0;
	}
	.chat-scroll:focus:not(:focus-visible) {
		outline: none;
	}
	.thinking {
		color: var(--muted-text);
		font-size: 14px;
		padding-block: 16px;
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.mobile-sidebar-trigger {
			display: inline-flex;
		}
		.desktop-sidebar-trigger {
			display: none;
		}
		.app-shell {
			position: fixed;
			inset: var(--app-viewport-top, 0px) 0 auto;
			height: var(--app-viewport-height, var(--app-height));
		}
		.chat-pane {
			padding-block-start: env(safe-area-inset-top, 0px);
			padding-inline: env(safe-area-inset-left, 0px) env(safe-area-inset-right, 0px);
		}
		.chat-header {
			min-height: 56px;
			padding-block: 6px;
		}
		.welcome-workspace {
			padding-bottom: 0;
		}
		.welcome-workspace .composer-region {
			margin-block: auto;
			padding-block: 20px max(40px, calc(var(--app-viewport-height, var(--app-height)) * 0.12));
		}
		.welcome-group {
			gap: 14px;
			margin-bottom: 24px;
		}
		.welcome-title {
			max-inline-size: 22ch;
			font-size: clamp(1.625rem, 1.15rem + 2.4vw, 1.875rem);
		}
		.message-list {
			padding-top: 16px;
		}
		.message-column.own {
			max-width: 90%;
		}
		.own .message-bubble {
			padding-inline: 16px;
		}

		.welcome-workspace:focus-within .composer-region {
			padding-block: 12px;
		}
		:global(html[data-keyboard]) .welcome-workspace .welcome-group {
			display: none;
		}
		:global(html[data-keyboard]) .welcome-workspace .composer-region {
			margin-block: auto 0;
			padding-block: 0;
		}
	}
	@media (max-height: 500px) {
		.welcome-workspace {
			justify-content: flex-end;
			padding-bottom: 0;
		}
		.welcome-workspace .composer-region {
			padding-block: 8px;
		}
		.welcome-group {
			gap: 8px;
			margin-bottom: 16px;
		}
		.welcome-group > img {
			display: none;
		}
		.welcome-title {
			font-size: 1.5rem;
		}
	}
	@media (prefers-reduced-motion: no-preference) {
		.welcome-group:global(.welcome-enter) {
			animation: welcome-enter 200ms ease-out both;
		}
		@keyframes welcome-enter {
			from {
				opacity: 0;
				transform: translateY(4px);
			}
			to {
				opacity: 1;
				transform: none;
			}
		}
	}
</style>
