<!--
SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)

SPDX-License-Identifier: MPL-2.0
-->

<script lang="ts">
	import DownloadQuiz from '$lib/components/DownloadQuiz.svelte';
	import type { QuizData } from '$lib/quiz_types';
	import { getLocalization } from '$lib/i18n';
	import Footer from '$lib/footer.svelte';
	import { signedIn } from '$lib/stores';
	import { navbarVisible } from '$lib/stores.svelte';
	import CommandpaletteNotice from '$lib/components/popover/commandpalettenotice.svelte';
	// import Spinner from "$lib/Spinner.svelte";
	import Fuse from 'fuse.js';
	import BrownButton from '$lib/components/buttons/brown.svelte';
	import type { PageData } from './$types';
	import { fly } from 'svelte/transition';
	import StartGamePopup from '$lib/dashboard/start_game.svelte';
	import Analytics from './Analytics.svelte';
	import MediaComponent from '$lib/editor/MediaComponent.svelte';
	import { createTippy } from 'svelte-tippy';
	import { onMount } from 'svelte';

	interface Props {
		// import GrayButton from "$lib/components/buttons/gray.svelte";
		data: PageData;
	}

	let { data }: Props = $props();
	let search_term = $state('');
	let start_game = $state(null);
	let download_id: string | null = $state(null);
	signedIn.set(true);
	navbarVisible.visible = true;
	const { t } = getLocalization();

	let items_to_show = $state([]);
	let all_items: Array<any> = $state();
	let fuse;
	const tippy = createTippy({
		arrow: true,
		animation: 'perspective-subtle',
		placement: 'bottom'
	});

	let id_to_position_map = {};

	const getData = async (): Promise<{ items: Array<QuizData>; fuse: Fuse<any> }> => {
		const items: any[] = [];

		for (const q of data.quizzes) items.push({ ...q, type: 'quiz' });
		for (const q of data.quiztivities) items.push({ ...q, type: 'quiztivity' });

		const f = new Fuse(items, {
			keys: ['title', 'description', 'questions.title'],
			findAllMatches: true
		});

		// return *all* derived data instead of mutating directly
		return { items, fuse: f };
	};

	const search = () => {
		if (search_term === '') {
			items_to_show = all_items;
			return;
		}

		const res = fuse.search(search_term);
		items_to_show = res.map((r) => r.item);
	};
	let active_assignments: Array<any> = $state([]);

	const fetchActiveAssignments = async () => {
		try {
			const res = await fetch('/api/v1/quiz/assign/list');
			if (res.ok) {
				active_assignments = await res.json();
			}
		} catch (e) {
			console.error('Failed to load active assignments', e);
		}
	};

	const copyAssignLink = (pin: string) => {
		const url = `${window.location.origin}/play/selfpaced?pin=${pin}`;
		navigator.clipboard.writeText(url);
		alert('Link copiat în clipboard!');
	};

	const endAssign = async (pin: string) => {
		if (!confirm('Sigur doriți să încheiați acest assignment?')) return;
		try {
			await fetch(`/api/v1/quiz/assign/${pin}`, { method: 'DELETE' });
			await fetchActiveAssignments();
		} catch (e) {
			alert('Eroare la ștergere');
		}
	};

	onMount(async () => {
		const { items, fuse: f } = await getData();
		all_items = items;
		items_to_show = items;
		fuse = f;

		// fill id_to_position_map
		id_to_position_map = {};
		for (let i = 0; i < items.length; i++) {
			id_to_position_map[items[i].id] = i;
		}
		search_term;
		search();
		fetchActiveAssignments();
	});

	const deleteQuiz = async (to_delete: string, type: 'quiz' | 'quiztivity') => {
		if (!confirm('Do you really want to delete this quiz?')) {
			return;
		}
		if (type === 'quiz') {
			await fetch(`/api/v1/quiz/delete/${to_delete}`, {
				method: 'DELETE'
			});
		} else {
			await fetch(`/api/v1/quiztivity/${to_delete}`, {
				method: 'DELETE'
			});
		}
		window.location.reload();
	};
	let create_button_clicked = $state(false);

	let analytics_quiz_selected: undefined | QuizData = $state(undefined);
</script>

<svelte:head>
	<title>ClassQuiz - Dashboard</title>
</svelte:head>
<Analytics bind:quiz={analytics_quiz_selected} />
<CommandpaletteNotice />
<div class="min-h-screen flex flex-col">
	{#if !all_items}
		<svg class="h-8 w-8 animate-spin mx-auto my-20" viewBox="3 3 18 18">
			<path
				class="fill-black"
				d="M12 5C8.13401 5 5 8.13401 5 12C5 15.866 8.13401 19 12 19C15.866 19 19 15.866 19 12C19 8.13401 15.866 5 12 5ZM3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12Z"
			/>
			<path
				class="fill-blue-100"
				d="M16.9497 7.05015C14.2161 4.31648 9.78392 4.31648 7.05025 7.05015C6.65973 7.44067 6.02656 7.44067 5.63604 7.05015C5.24551 6.65962 5.24551 6.02646 5.63604 5.63593C9.15076 2.12121 14.8492 2.12121 18.364 5.63593C18.7545 6.02646 18.7545 6.65962 18.364 7.05015C17.9734 7.44067 17.3403 7.44067 16.9497 7.05015Z"
			/>
		</svg>
	{:else}
		<div class="flex flex-col w-full mx-auto">
			<!--		<button
                    class='px-4 py-2 font-medium tracking-wide text-gray-500 whitespace-nowrap dark:text-gray-400 capitalize transition-colors dark:bg-gray-700 duration-200 transform bg-[#B07156] rounded-md hover:bg-green-600 focus:outline-hidden focus:ring focus:ring-blue-300 focus:ring-opacity-80'>
                    Primary
                </button>-->
			<div class="w-full grid lg:grid-cols-4 gap-2 grid-cols-2 px-4">
				<!-- {#if create_button_clicked}
					<div
						class="flex gap-2"
						transition:fly|global={{ y: 10 }}
						use:tippy={{ content: 'Unsure? Choose "Quiz".' }}
					>
						<BrownButton href="/create">{$t('words.quiz')}</BrownButton>
						<BrownButton href="/quiztivity/create">{$t('words.quiztivity')}</BrownButton
						>
					</div>
				{:else}
					<BrownButton
						onclick={() => {
							create_button_clicked = true;
						}}>{$t('words.create')}</BrownButton
					>
				{/if} -->
				<BrownButton href="/create">{$t('dashboard.create_quiz')}</BrownButton>
				<BrownButton href="/import">{$t('words.import')}</BrownButton>
				<BrownButton href="/results">{$t('words.results')}</BrownButton>
				<div class="flex gap-2">
					<BrownButton href="/edit/files">{$t('words.files_library')}</BrownButton>
					<BrownButton href="/account/settings">
						{$t('words.settings')}
					</BrownButton>
				</div>
			</div>
			{#if active_assignments && active_assignments.length > 0}
				<div class="mx-4 mt-6 bg-gray-800/90 border border-purple-500/40 rounded-xl p-5 shadow-lg">
					<div class="flex items-center justify-between mb-4">
						<div class="flex items-center gap-2">
							<span class="text-2xl">🕐</span>
							<h2 class="text-xl font-bold text-white">Teme în Derulare ({active_assignments.length})</h2>
							<span class="bg-purple-500/20 text-purple-300 text-xs px-2.5 py-0.5 rounded-full font-bold">
								Self-Paced Active
							</span>
						</div>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{#each active_assignments as a}
							<div class="bg-gray-900/80 border border-gray-700/80 rounded-xl p-4 flex flex-col justify-between hover:border-purple-500/60 transition-all shadow">
								<div>
									<div class="flex items-start justify-between gap-2">
										<h3 class="font-bold text-white text-lg truncate">{@html a.title}</h3>
										<span class="font-mono text-xs bg-purple-900/50 text-purple-300 px-2 py-1 rounded font-bold">
											PIN: {a.game_pin}
										</span>
									</div>
									<p class="text-xs text-gray-400 mt-1">
										📅 Deadline: {a.deadline ? new Date(a.deadline).toLocaleDateString() + ' ' + new Date(a.deadline).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'Fără limită'}
									</p>
									<div class="mt-3 flex items-center justify-between text-xs text-gray-300">
										<span>Elevi înscriși: <strong class="text-white">{a.total_players}</strong></span>
										<span>Finalizat: <strong class="text-green-400">{a.finished_players}</strong></span>
									</div>
									<div class="w-full bg-gray-700 rounded-full h-2 mt-1.5">
										<div class="bg-gradient-to-r from-purple-500 to-green-400 h-2 rounded-full transition-all" style="width: {a.total_players > 0 ? (a.finished_players / a.total_players) * 100 : 0}%"></div>
									</div>
								</div>
								<div class="flex items-center gap-2 mt-4 pt-3 border-t border-gray-800">
									<a href="/admin/assign?pin={a.game_pin}" class="flex-1 bg-purple-600 hover:bg-purple-500 text-white text-center py-2 px-3 rounded-lg text-xs font-bold transition-all shadow">
										📊 Monitorizează
									</a>
									<button onclick={() => copyAssignLink(a.game_pin)} class="bg-gray-700 hover:bg-gray-600 text-white py-2 px-3 rounded-lg text-xs font-bold transition-all" title="Copiază link-ul pentru elevi">
										📋
									</button>
									<button onclick={() => endAssign(a.game_pin)} class="bg-red-900/40 hover:bg-red-700 text-red-300 py-2 px-3 rounded-lg text-xs font-bold transition-all" title="Încheie assignment">
										🗑️
									</button>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
			{#if all_items.length !== 0}
				<div class="flex justify-center pt-4 w-full">
					<div>
						<div>
							<input
								bind:value={search_term}
								class="p-2 rounded-lg outline-hidden text-center w-96 dark:bg-gray-700"
								placeholder={$t('dashboard.search_for_own_quizzes')}
							/>
							<button
								onclick={() => {
									search_term = '';
									items_to_show = all_items;
								}}
							>
								<svg
									class="h-8 inline-block"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									xmlns="http://www.w3.org/2000/svg"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M6 18L18 6M6 6l12 12"
									/>
								</svg>
							</button>
						</div>
					</div>
				</div>
				<div class="flex flex-col gap-4 mt-4 px-2">
					{#each items_to_show as quiz}
						<div
							class="grid grid-cols-2 lg:grid-cols-3 w-full rounded-sm border-[#B07156] border-2 p-2 h-[20vh] overflow-hidden max-h-[20vh]"
						>
							<div class="hidden lg:flex w-auto h-full items-center relative">
								{#if quiz.cover_image}
									<!--									<img
										src="/api/v1/storage/download/{quiz.cover_image}"
										alt="user provided"
										loading="lazy"
										class="shrink-0 max-w-full max-h-full absolute rounded-sm"
									/>-->
									<MediaComponent
										src={quiz.cover_image}
										css_classes="shrink-0 max-w-full max-h-full absolute rounded-sm"
									/>
								{/if}
							</div>
							<div class="my-auto mx-auto max-h-full overflow-hidden">
								<p class="text-xl text-center">{@html quiz.title}</p>
								<p class="text-sm text-center text-clip overflow-hidden">
									{@html quiz.description ?? ''}
								</p>
							</div>
							<div
								class="grid grid-rows-2 ms-auto gap-2 w-fit self-end my-auto"
								class:grid-cols-3={quiz.type === 'quiz'}
								class:grid-cols-2={quiz.type !== 'quiztivity'}
							>
								<BrownButton
									flex={true}
									disabled={!quiz.public}
									href="/view/{quiz.id}"
								>
									<!-- heroicons/legacy-outline/Eye -->
									<svg
										class="w-5 h-5"
										aria-hidden="true"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										viewBox="0 0 24 24"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
											stroke-linecap="round"
											stroke-linejoin="round"
										/>
										<path
											d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
											stroke-linecap="round"
											stroke-linejoin="round"
										/>
									</svg>
								</BrownButton>
								<BrownButton
									flex={true}
									onclick={() => (analytics_quiz_selected = quiz)}
								>
									<!-- heroicons/legacy-outline/ChartBar -->
									<svg
										class="w-5 h-5"
										aria-hidden="true"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										viewBox="0 0 24 24"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
											stroke-linecap="round"
											stroke-linejoin="round"
										/>
									</svg>
								</BrownButton>
								<BrownButton
									href={quiz.type === 'quiz'
										? `/edit?quiz_id=${quiz.id}`
										: `/quiztivity/edit?id=${quiz.id}`}
									flex={true}
								>
									<!-- heroicons/legacy-outline/Pencil -->
									<svg
										class="w-5 h-5"
										aria-hidden="true"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										viewBox="0 0 24 24"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
											stroke-linecap="round"
											stroke-linejoin="round"
										/>
									</svg>
								</BrownButton>
								{#if quiz.type === 'quiz'}
									<BrownButton
										onclick={() => {
											start_game = quiz.id;
										}}
										flex={true}
									>
										<!-- heroicons/legacy-outline/Play -->
										<svg
											class="w-5 h-5"
											aria-hidden="true"
											fill="none"
											stroke="currentColor"
											stroke-width="2"
											viewBox="0 0 24 24"
											xmlns="http://www.w3.org/2000/svg"
										>
											<path
												d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
											<path
												d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
										</svg>
									</BrownButton>
								{:else}
									<BrownButton href="/quiztivity/play?id={quiz.id}" flex={true}>
										<!-- heroicons/legacy-outline/Play -->
										<svg
											class="w-5 h-5"
											aria-hidden="true"
											fill="none"
											stroke="currentColor"
											stroke-width="2"
											viewBox="0 0 24 24"
											xmlns="http://www.w3.org/2000/svg"
										>
											<path
												d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
											<path
												d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
										</svg>
									</BrownButton>
								{/if}

								<BrownButton
									onclick={() => {
										deleteQuiz(quiz.id, quiz.type);
									}}
									flex={true}
								>
									<!-- heroicons/trash -->
									<svg
										class="w-5 h-5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
										/>
									</svg>
								</BrownButton>
								<BrownButton
									onclick={() => (download_id = quiz.id)}
									flex={true}
									disabled={quiz.type !== 'quiz'}
									><!-- heroicons/download -->
									<svg
										class="w-5 h-5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										xmlns="http://www.w3.org/2000/svg"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
										/>
									</svg>
								</BrownButton>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p>
					{$t('overview_page.no_quizzes')}
				</p>
			{/if}
		</div>
	{/if}
</div>
<Footer />
{#if start_game !== null}
	<StartGamePopup bind:quiz_id={start_game} />
{/if}
<DownloadQuiz bind:quiz_id={download_id} />
