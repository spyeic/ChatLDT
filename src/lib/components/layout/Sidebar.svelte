<script lang="ts">
	import type { Chat, Identity } from '$lib/apis/manual';
	import ActionIcon from '$lib/components/common/ActionIcon.svelte';
	import ResponsiveDrawer from '$lib/components/common/ResponsiveDrawer.svelte';
	export let identity: Identity | null = null;
	export let chats: Chat[] = [];
	export let selected = '';
	export let query = '';
	export let open = true;
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
	label={labels.chats}
	closeLabel={labels.close}
	{onClose}
>
	<aside class="sidebar flex flex-col h-full w-64 shrink-0 bg-gray-50 dark:bg-gray-950 p-3">
		<div class="px-2 py-3 flex items-center gap-2 brand-lockup">
			<img src="/chatldt-icon-v1.svg" class="size-8" alt="" /><span class="font-semibold text-lg"
				>ChatLDT</span
			>
			<button
				type="button"
				class="icon-button drawer-close ml-auto"
				aria-label={labels.close}
				on:click={onClose}><ActionIcon name="close" /></button
			>
		</div>
		<button
			class="flex items-center gap-2 text-left rounded-xl hover:bg-gray-200 dark:hover:bg-gray-850 p-3"
			on:click={onNew}><ActionIcon name="plus" /> {labels.new}</button
		>
		<label class="sr-only" for="chat-search">{labels.search}</label><input
			id="chat-search"
			type="search"
			class="bg-transparent border rounded-xl p-2 my-2 w-full"
			bind:value={query}
			placeholder={labels.search}
		/>
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
							<div class="flex items-center ml-3 rounded-lg" class:active={selected === chat.id}>
								<button class="p-2 flex-1 min-w-0 text-left" on:click={() => onSelect(chat.id)}
									><div class="truncate">{chat.title}</div>
									{#if chat.snippet}<div class="text-xs text-gray-500 truncate">
											{chat.snippet}
										</div>{/if}</button
								>{#if chat.unread}<span class="badge">{chat.unread}</span>{/if}<button
									class="icon-button compact"
									aria-label={labels.rename + ' ' + chat.title}
									on:click={() => onRename(chat.id)}><ActionIcon name="edit" /></button
								><button
									class="icon-button compact"
									aria-label={labels.delete + ' ' + chat.title}
									on:click={() => onDelete(chat.id)}><ActionIcon name="close" /></button
								>
							</div>
						{/each}
					{/if}
				{/each}
			{:else}
				{#each chats as chat (chat.id)}
					<div class="flex items-center rounded-lg" class:active={selected === chat.id}>
						<button class="p-2 flex-1 min-w-0 text-left" on:click={() => onSelect(chat.id)}
							><div class="truncate">{chat.title}</div>
							{#if chat.snippet}<div class="text-xs text-gray-500 truncate">
									{chat.snippet}
								</div>{/if}</button
						>{#if chat.unread}<span class="badge">{chat.unread}</span>{/if}<button
							class="icon-button compact"
							aria-label={labels.rename + ' ' + chat.title}
							on:click={() => onRename(chat.id)}><ActionIcon name="edit" /></button
						><button
							class="icon-button compact"
							aria-label={labels.delete + ' ' + chat.title}
							on:click={() => onDelete(chat.id)}><ActionIcon name="close" /></button
						>
					</div>
				{/each}
			{/if}
		</nav>
		{#if identity}<button
				class="flex gap-2 items-center rounded-xl p-3 hover:bg-gray-200 dark:hover:bg-gray-850"
				on:click={onSettings}
				><img class="size-7 rounded-full" src={identity.avatar} alt="" /><span class="truncate"
					>{identity.admin ? 'admin' : identity.name}</span
				></button
			>{:else}<button
				class="rounded-xl p-3 hover:bg-gray-200 dark:hover:bg-gray-850"
				on:click={onLogin}>{labels.login}</button
			>{/if}
	</aside>
</ResponsiveDrawer>

<style>
	.sidebar {
		z-index: 20;
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
		.drawer-close {
			display: inline-flex;
		}
		.sidebar nav {
			overscroll-behavior: contain;
			min-height: 0;
		}
	}
</style>
