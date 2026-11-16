<script lang="ts">
	import { tick } from 'svelte';
	import type { Chat, Identity } from '$lib/apis/manual';
	import ActionIcon from '$lib/components/common/ActionIcon.svelte';
	import ResponsiveDrawer from '$lib/components/common/ResponsiveDrawer.svelte';
	export let identity: Identity | null = null;
	export let chats: Chat[] = [];
	export let selected = '';
	export let query = '';
	export let open = true;
	export let collapsed = false;
	export let onCollapse = () => {};
	let searching = false;
	let searchInput: HTMLInputElement;
	let searchButton: HTMLButtonElement;
	async function toggleSearch() {
		searching = !searching;
		if (!searching) query = '';
		await tick();
		if (searching) searchInput?.focus();
		else searchButton?.focus();
	}
	export let labels: Record<string, string> = {};
	export let onSelect = (id: string) => {};
	export let onNew = () => {};
	export let onSettings = () => {};
	export let onLogin = () => {};
	export let onRename = (id: string) => {};
	export let onDelete = (id: string) => {};
	export let expanded: Record<string, boolean> = {};
	export let onToggle = (id: string) => {};
	export let onClose = () => {};
	let drawer: ResponsiveDrawer;
	export async function close() {
		onClose();
		await drawer?.close();
	}
	$: groups = Array.from(
		chats
			.reduce((map, c) => {
				const group = map.get(c.owner_id) || {
					id: c.owner_id,
					name: c.owner_name,
					kind: c.owner_kind,
					chats: [],
					unread: 0
				};
				group.chats.push(c);
				group.unread += c.unread;
				map.set(c.owner_id, group);
				return map;
			}, new Map<string, any>())
			.values()
	);
</script>

<ResponsiveDrawer
	bind:this={drawer}
	{open}
	{collapsed}
	label={labels.chats}
	closeLabel={labels.close}
	{onClose}
>
	<aside class="sidebar flex flex-col h-full shrink-0">
		<div class="brand-lockup flex items-center gap-2">
			<img src="/chatldt-icon-v1.svg" class="size-7" alt="" />
			<span class="font-semibold flex-1">ChatLDT</span>
			<button
				bind:this={searchButton}
				type="button"
				class="icon-button"
				aria-label={labels.search}
				title={labels.search}
				aria-expanded={searching}
				on:click={toggleSearch}><ActionIcon name="search" /></button
			>
			<button
				type="button"
				class="icon-button desktop-collapse"
				aria-label={labels.close}
				title={labels.close}
				on:click={onCollapse}><ActionIcon name="sidebar" /></button
			>
			<button
				type="button"
				class="icon-button drawer-close"
				aria-label={labels.close}
				on:click={onClose}><ActionIcon name="close" /></button
			>
		</div>
		<button class="new-chat flex items-center gap-3 text-left rounded-lg" on:click={onNew}
			><ActionIcon name="edit" /> {labels.new}</button
		>
		{#if searching}
			<div class="search-panel flex items-center">
				<label class="sr-only" for="chat-search">{labels.search}</label>
				<input
					bind:this={searchInput}
					id="chat-search"
					type="search"
					bind:value={query}
					placeholder={labels.search}
					on:keydown={(event) => {
						if (event.key === 'Escape') {
							event.preventDefault();
							event.stopPropagation();
							void toggleSearch();
						}
					}}
				/>
				<button
					class="icon-button"
					type="button"
					aria-label={labels.dismiss}
					on:click={toggleSearch}><ActionIcon name="close" /></button
				>
			</div>
		{/if}
		<div class="list-label">{labels.chats}</div>
		<nav aria-label={labels.chats} class="flex-1 overflow-y-auto">
			{#if identity?.admin}
				{#each groups as group (group.id)}
					<button
						class="w-full flex gap-2 items-center text-left rounded-lg p-2 hover:bg-gray-200 dark:hover:bg-gray-850"
						aria-expanded={!!expanded[group.id]}
						on:click={() => onToggle(group.id)}
						><span>{expanded[group.id] ? '⌄' : '›'}</span><span class="truncate flex-1"
							>{group.name}</span
						><span class="text-xs text-gray-500"
							>{group.kind === 'guest' ? labels.guest : labels.user}</span
						>{#if group.unread}<span class="badge">{group.unread}</span>{/if}</button
					>
					{#if expanded[group.id]}
						{#each group.chats as chat (chat.id)}
							<div
								class="chat-item flex items-center ml-3 rounded-lg"
								class:active={selected === chat.id}
							>
								<button
									class="p-2 flex-1 min-w-0 text-left"
									aria-current={selected === chat.id ? 'page' : undefined}
									on:click={() => onSelect(chat.id)}
									><div class="truncate" title={chat.title}>{chat.title}</div>
									{#if chat.snippet}<div class="text-xs text-gray-500 truncate">
											{chat.snippet}
										</div>{/if}</button
								>{#if chat.unread}<span class="badge">{chat.unread}</span>{/if}<button
									class="icon-button compact chat-action"
									aria-label={labels.rename + ' ' + chat.title}
									on:click={() => onRename(chat.id)}><ActionIcon name="edit" /></button
								><button
									class="icon-button compact chat-action"
									aria-label={labels.delete + ' ' + chat.title}
									on:click={() => onDelete(chat.id)}><ActionIcon name="close" /></button
								>
							</div>
						{/each}
					{/if}
				{/each}
			{:else}
				{#each chats as chat (chat.id)}
					<div class="chat-item flex items-center rounded-lg" class:active={selected === chat.id}>
						<button
							class="p-2 flex-1 min-w-0 text-left"
							aria-current={selected === chat.id ? 'page' : undefined}
							on:click={() => onSelect(chat.id)}
							><div class="truncate" title={chat.title}>{chat.title}</div>
							{#if chat.snippet}<div class="text-xs text-gray-500 truncate">
									{chat.snippet}
								</div>{/if}</button
						>{#if chat.unread}<span class="badge">{chat.unread}</span>{/if}<button
							class="icon-button compact chat-action"
							aria-label={labels.rename + ' ' + chat.title}
							on:click={() => onRename(chat.id)}><ActionIcon name="edit" /></button
						><button
							class="icon-button compact chat-action"
							aria-label={labels.delete + ' ' + chat.title}
							on:click={() => onDelete(chat.id)}><ActionIcon name="close" /></button
						>
					</div>
				{/each}
			{/if}
		</nav>
		<div class="account-area flex items-center">
			{#if identity}<button
					class="account-button flex gap-2 items-center rounded-xl"
					on:click={onSettings}
					><img class="size-7 rounded-full" src={identity.avatar} alt="" /><span class="truncate"
						>{identity.admin ? 'admin' : identity.name}</span
					></button
				>{:else}<button class="account-button rounded-xl text-left" on:click={onLogin}
					>{labels.login}</button
				>{/if}
			{#if identity?.kind === 'guest'}<button type="button" class="guest-login" on:click={onLogin}
					>{labels.login}</button
				>{/if}
		</div>
	</aside>
</ResponsiveDrawer>

<style>
	.sidebar {
		z-index: 20;
		width: var(--sidebar-width);
		padding: 12px 10px;
		background: var(--sidebar-bg);
		font-size: 14px;
	}
	.brand-lockup {
		padding: 4px 4px 16px;
		gap: 6px;
	}
	.new-chat {
		min-height: 42px;
		padding: 8px 10px;
	}
	.list-label {
		color: var(--muted-text);
		padding: 26px 10px 10px;
		font-size: 12px;
	}
	.sidebar nav {
		min-height: 0;
		overscroll-behavior: contain;
	}
	.chat-item {
		min-height: 38px;
		position: relative;
	}
	.chat-item > button:first-child {
		padding: 9px 10px;
		line-height: 20px;
	}
	.chat-item:hover {
		background: var(--action-hover);
	}
	.chat-action {
		color: var(--muted-text);
	}
	.account-area {
		flex-shrink: 0;
		margin-top: 8px;
	}
	.guest-login {
		color: var(--muted-text);
		padding: 8px;
		border-radius: 8px;
		font-size: 12px;
	}
	.account-button {
		flex: 1;
		min-width: 0;
		min-height: 52px;
		padding: 10px;
		flex-shrink: 0;
	}
	.search-panel {
		background: var(--composer-bg);
		border-radius: 12px;
		margin-top: 8px;
		padding: 4px;
	}
	.search-panel input {
		min-width: 0;
		width: 100%;
		background: transparent;
		padding: 8px;
		border: 0;
		border-radius: 8px;
	}
	@media (hover: hover) and (pointer: fine) {
		.chat-action {
			opacity: 0;
			pointer-events: none;
			transition: opacity 150ms ease;
		}
		.chat-item:hover .chat-action,
		.chat-item:focus-within .chat-action {
			opacity: 1;
			pointer-events: auto;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.chat-action {
			transition: none;
		}
	}
	.active {
		background: rgb(127 127 127 / 0.15);
	}
	.badge {
		font-size: 0.7rem;
		min-width: 1.2rem;
		border-radius: 1rem;
		padding: 0.1rem 0.3rem;
		background: #525252;
		color: white;
		text-align: center;
	}
	.drawer-close {
		display: none;
	}
	@media (max-width: 767px), (max-height: 500px) and (pointer: coarse) {
		.desktop-collapse {
			display: none;
		}
		.drawer-close {
			display: inline-flex;
		}
		.sidebar nav {
			overscroll-behavior: contain;
			min-height: 0;
		}
	}
</style>
