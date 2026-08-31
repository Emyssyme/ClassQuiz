<!--
SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)

SPDX-License-Identifier: MPL-2.0
-->

<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { navbarVisible } from '$lib/stores.svelte.ts';
	import Spinner from '$lib/Spinner.svelte';
	import BrownButton from '$lib/components/buttons/brown.svelte';
	import { getLocalization } from '$lib/i18n';

	const { t } = getLocalization();

	interface Props {
		data: any;
	}

	let { data }: Props = $props();
	let game_pin = $state(data.game_pin);
	navbarVisible.visible = true;

	let status: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let pollInterval: any = $state(null);
	let copied = $state(false);
	let activeTab: 'players' | 'questions' | 'matrix' = $state('players');
	let saving = $state(false);
	let saveMessage = $state('');

	const fetchStatus = async () => {
		try {
			const res = await fetch(`/api/v1/quiz/assign/${game_pin}/status`);
			if (res.ok) {
				status = await res.json();
				error = '';
			} else if (res.status === 404) {
				error = 'Assignment expired or not found.';
				clearInterval(pollInterval);
			} else {
				error = 'Failed to fetch status.';
			}
		} catch {
			error = 'Network error.';
		}
		loading = false;
	};

	onMount(() => {
		if (game_pin) {
			fetchStatus();
			pollInterval = setInterval(fetchStatus, 4000);
		}
	});

	onDestroy(() => {
		if (pollInterval) clearInterval(pollInterval);
	});

	function copyLink() {
		const url = `${window.location.origin}/play/selfpaced?pin=${game_pin}`;
		navigator.clipboard.writeText(url);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}

	function getDeadlineCountdown(deadline: string): string {
		const diff = new Date(deadline).getTime() - Date.now();
		if (diff <= 0) return 'Expired';
		const hours = Math.floor(diff / 3600000);
		const minutes = Math.floor((diff % 3600000) / 60000);
		if (hours > 24) {
			const days = Math.floor(hours / 24);
			return `${days}d ${hours % 24}h`;
		}
		return `${hours}h ${minutes}m`;
	}

	async function saveResults() {
		saving = true;
		try {
			const res = await fetch(`/api/v1/quiz/assign/${game_pin}/save`, { method: 'POST' });
			if (res.ok) {
				saveMessage = '✅ Rezultate salvate în istoric!';
			} else {
				saveMessage = '❌ Eroare la salvare!';
			}
		} catch {
			saveMessage = '❌ Eroare de rețea!';
		}
		saving = false;
		setTimeout(() => (saveMessage = ''), 3000);
	}

	async function deleteAssignment() {
		if (!confirm('Sigur doriți să încheiați acest assignment? Nu se vor mai putea trimite răspunsuri.')) return;
		try {
			await fetch(`/api/v1/quiz/assign/${game_pin}`, { method: 'DELETE' });
			window.location.assign('/dashboard');
		} catch {
			alert('Eroare la ștergerea assignment-ului');
		}
	}
</script>

<svelte:head>
	<title>ClassQuiz - Monitorizare Assignment</title>
</svelte:head>

<div class="min-h-screen p-6">
	<div class="max-w-6xl mx-auto">
		<!-- Header -->
		<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
			<div>
				<div class="flex items-center gap-3">
					<h1 class="text-3xl font-bold">🕐 Monitorizare Assignment</h1>
					<span class="bg-purple-600/30 text-purple-300 text-xs font-bold px-3 py-1 rounded-full border border-purple-500/40">
						Self-Paced
					</span>
				</div>
				{#if status}
					<p class="text-xl text-gray-400 mt-1">{@html status.title}</p>
				{/if}
			</div>
			<div class="flex items-center gap-3">
				<button
					onclick={saveResults}
					disabled={saving}
					class="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-bold text-sm shadow transition-all"
				>
					{saving ? 'Se salvează...' : '💾 Salvează Rezultate'}
				</button>
				<button
					onclick={deleteAssignment}
					class="bg-red-600/80 hover:bg-red-600 text-white px-4 py-2 rounded-lg font-bold text-sm shadow transition-all"
				>
					⏹️ Încheie
				</button>
				<a href="/dashboard">
					<BrownButton>← Dashboard</BrownButton>
				</a>
			</div>
		</div>

		{#if saveMessage}
			<div class="bg-green-900/40 border border-green-500 text-green-300 p-3 rounded-lg text-center mb-6 font-bold">
				{saveMessage}
			</div>
		{/if}

		{#if loading}
			<div class="flex justify-center mt-20">
				<Spinner />
			</div>
		{:else if error}
			<div class="bg-red-900/30 border border-red-500 rounded-xl p-6 text-center">
				<p class="text-xl text-red-400">{error}</p>
				<a href="/dashboard" class="text-blue-400 underline mt-2 block">Înapoi la Dashboard</a>
			</div>
		{:else if status}
			<!-- Share Section -->
			<div class="bg-gray-800 rounded-xl p-6 mb-6">
				<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
					<div class="text-center">
						<p class="text-sm text-gray-400 mb-1">Game PIN</p>
						<p class="text-4xl font-mono font-bold text-purple-400 select-all">{game_pin}</p>
					</div>
					<div class="text-center flex flex-col justify-center items-center">
						<p class="text-sm text-gray-400 mb-2">Link pentru elevi</p>
						<button
							onclick={copyLink}
							class="bg-purple-600 hover:bg-purple-500 text-white px-5 py-2.5 rounded-lg transition-all text-sm font-bold shadow"
						>
							{copied ? '✅ Copiat în clipboard!' : '📋 Copiază Link'}
						</button>
					</div>
					<div class="text-center">
						<p class="text-sm text-gray-400 mb-1">QR Code</p>
						<img
							src="/api/v1/utils/qr/{game_pin}"
							alt="QR code"
							class="w-20 h-20 mx-auto dark:bg-white rounded p-1"
						/>
					</div>
				</div>
			</div>

			<!-- Stats Cards -->
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
				<div class="bg-gray-800 rounded-xl p-4 text-center border border-gray-700/50">
					<p class="text-3xl font-bold text-blue-400">{status.total_players}</p>
					<p class="text-sm text-gray-400 mt-1">Elevi Înscriși</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center border border-gray-700/50">
					<p class="text-3xl font-bold text-green-400">{status.finished_count}</p>
					<p class="text-sm text-gray-400 mt-1">Finalizat</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center border border-gray-700/50">
					<p class="text-3xl font-bold text-yellow-400">{status.total_players - status.finished_count}</p>
					<p class="text-sm text-gray-400 mt-1">În Curs</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center border border-gray-700/50">
					<p class="text-3xl font-bold text-purple-400">
						{status.deadline ? getDeadlineCountdown(status.deadline) : '∞'}
					</p>
					<p class="text-sm text-gray-400 mt-1">Timp Rămas</p>
				</div>
			</div>

			<!-- Progress Bar -->
			{#if status.total_players > 0}
				<div class="bg-gray-800 rounded-xl p-4 mb-6">
					<div class="flex justify-between text-sm text-gray-400 mb-1">
						<span>Rată de Finalizare</span>
						<span class="font-bold text-white">{Math.round((status.finished_count / status.total_players) * 100)}%</span>
					</div>
					<div class="w-full bg-gray-700 rounded-full h-3">
						<div
							class="bg-gradient-to-r from-purple-500 to-green-400 h-3 rounded-full transition-all duration-500"
							style="width: {(status.finished_count / status.total_players) * 100}%"
						></div>
					</div>
				</div>
			{/if}

			<!-- Navigation Tabs -->
			<div class="flex border-b border-gray-700 mb-6 gap-2">
				<button
					class="px-5 py-3 font-bold text-sm transition-all border-b-2"
					class:border-purple-500={activeTab === 'players'}
					class:text-purple-400={activeTab === 'players'}
					class:border-transparent={activeTab !== 'players'}
					class:text-gray-400={activeTab !== 'players'}
					onclick={() => (activeTab = 'players')}
				>
					👥 Clasament Jucători ({status.players.length})
				</button>
				<button
					class="px-5 py-3 font-bold text-sm transition-all border-b-2"
					class:border-purple-500={activeTab === 'questions'}
					class:text-purple-400={activeTab === 'questions'}
					class:border-transparent={activeTab !== 'questions'}
					class:text-gray-400={activeTab !== 'questions'}
					onclick={() => (activeTab = 'questions')}
				>
					📊 Rezultate pe Întrebări ({status.question_count})
				</button>
				<button
					class="px-5 py-3 font-bold text-sm transition-all border-b-2"
					class:border-purple-500={activeTab === 'matrix'}
					class:text-purple-400={activeTab === 'matrix'}
					class:border-transparent={activeTab !== 'matrix'}
					class:text-gray-400={activeTab !== 'matrix'}
					onclick={() => (activeTab = 'matrix')}
				>
					📋 Matrice Răspunsuri (Elevi x Întrebări)
				</button>
			</div>

			<!-- TAB 1: PLAYERS LEADERBOARD -->
			{#if activeTab === 'players'}
				<div class="bg-gray-800 rounded-xl overflow-hidden shadow">
					{#if status.players.length === 0}
						<div class="p-12 text-center text-gray-400">
							<p class="text-5xl mb-4">👥</p>
							<p class="text-lg">Niciun elev nu a început încă quiz-ul.</p>
							<p class="text-sm mt-2 text-gray-500">Trimite PIN-ul sau link-ul către elevi pentru a începe!</p>
						</div>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full">
								<thead>
									<tr class="text-left text-gray-400 text-sm border-b border-gray-700 bg-gray-900/40">
										<th class="p-4">Loc</th>
										<th class="p-4">Nume Elev</th>
										<th class="p-4">Progres</th>
										<th class="p-4">Scor Total</th>
										<th class="p-4">Status</th>
									</tr>
								</thead>
								<tbody>
									{#each status.players as player, i}
										<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
											<td class="p-4 font-mono font-bold">
												{#if i === 0}🥇 1{:else if i === 1}🥈 2{:else if i === 2}🥉 3{:else}{i + 1}{/if}
											</td>
											<td class="p-4 font-bold text-white text-base">{player.username}</td>
											<td class="p-4">
												<div class="flex items-center gap-3">
													<div class="w-32 bg-gray-700 rounded-full h-2.5">
														<div
															class="h-2.5 rounded-full transition-all duration-500"
															class:bg-green-400={player.finished}
															class:bg-purple-400={!player.finished}
															style="width: {player.finished ? 100 : ((player.current_question + 1) / status.question_count) * 100}%"
														></div>
													</div>
													<span class="text-xs font-mono text-gray-300">
														{player.finished ? status.question_count : player.current_question + 1}/{status.question_count}
													</span>
												</div>
											</td>
											<td class="p-4 font-mono font-bold text-purple-300 text-lg">{player.score}</td>
											<td class="p-4">
												{#if player.finished}
													<span class="bg-green-500/20 text-green-400 px-3 py-1 rounded-full text-xs font-bold border border-green-500/30">
														✅ Finalizat
													</span>
												{:else}
													<span class="bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full text-xs font-bold border border-yellow-500/30">
														⏳ În derulare
													</span>
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>

			<!-- TAB 2: QUESTION BREAKDOWN -->
			{:else if activeTab === 'questions'}
				<div class="space-y-4">
					{#each status.question_stats as q, i}
						<div class="bg-gray-800 rounded-xl p-5 border border-gray-700/50">
							<div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
								<div>
									<span class="text-xs font-bold uppercase tracking-wider text-purple-400 bg-purple-900/30 px-2.5 py-1 rounded">
										Întrebarea {i + 1} • {q.type}
									</span>
									<h3 class="text-xl font-bold text-white mt-2">{@html q.question}</h3>
								</div>
								<div class="flex items-center gap-4 bg-gray-900/60 px-4 py-2 rounded-xl border border-gray-700">
									<div class="text-center">
										<p class="text-xs text-gray-400">Răspunsuri</p>
										<p class="text-lg font-bold text-white">{q.total_answered}</p>
									</div>
									<div class="w-px h-8 bg-gray-700"></div>
									<div class="text-center">
										<p class="text-xs text-gray-400">Acuratețe</p>
										<p class="text-lg font-bold" class:text-green-400={q.accuracy >= 70} class:text-yellow-400={q.accuracy >= 40 && q.accuracy < 70} class:text-red-400={q.accuracy < 40}>
											{q.accuracy}%
										</p>
									</div>
									<div class="w-px h-8 bg-gray-700"></div>
									<div class="text-center">
										<p class="text-xs text-gray-400">Corecte / Greșite</p>
										<p class="text-sm font-bold text-gray-300">
											<span class="text-green-400">{q.correct_count}</span> / <span class="text-red-400">{q.wrong_count}</span>
										</p>
									</div>
								</div>
							</div>

							<!-- Accuracy progress bar -->
							<div class="w-full bg-gray-700 rounded-full h-2 mb-4">
								<div
									class="h-2 rounded-full transition-all"
									class:bg-green-500={q.accuracy >= 70}
									class:bg-yellow-500={q.accuracy >= 40 && q.accuracy < 70}
									class:bg-red-500={q.accuracy < 40}
									style="width: {q.accuracy}%"
								></div>
							</div>

							<!-- Individual student answers list -->
							{#if q.answers && q.answers.length > 0}
								<div class="mt-3">
									<p class="text-xs font-bold text-gray-400 uppercase mb-2">Răspunsuri trimise de elevi:</p>
									<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
										{#each q.answers as ans}
											<div
												class="p-2.5 rounded-lg text-xs flex items-center justify-between border"
												class:bg-green-950/30={ans.right}
												class:border-green-800/50={ans.right}
												class:text-green-200={ans.right}
												class:bg-red-950/30={!ans.right}
												class:border-red-800/50={!ans.right}
												class:text-red-200={!ans.right}
											>
												<span class="font-bold">{ans.username}:</span>
												<span class="truncate ml-1">{ans.answer || '(fără răspuns)'}</span>
												<span>{ans.right ? '✅' : '❌'}</span>
											</div>
										{/each}
									</div>
								</div>
							{:else}
								<p class="text-sm text-gray-500 italic">Niciun elev nu a răspuns încă la această întrebare.</p>
							{/if}
						</div>
					{/each}
				</div>

			<!-- TAB 3: LIVE MATRIX -->
			{:else if activeTab === 'matrix'}
				<div class="bg-gray-800 rounded-xl overflow-hidden shadow">
					{#if status.players.length === 0}
						<div class="p-12 text-center text-gray-400">
							<p class="text-5xl mb-4">📋</p>
							<p class="text-lg">Niciun elev nu a început încă quiz-ul.</p>
						</div>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full text-center text-sm">
								<thead>
									<tr class="text-gray-400 border-b border-gray-700 bg-gray-900/40">
										<th class="p-3 text-left">Elev</th>
										<th class="p-3">Scor</th>
										{#each status.questions as q, i}
											<th class="p-3 font-mono" title={q.question}>Q{i + 1}</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each status.players as player}
										<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
											<td class="p-3 text-left font-bold text-white">{player.username}</td>
											<td class="p-3 font-mono font-bold text-purple-300">{player.score}</td>
											{#each status.questions as _, qIndex}
												{@const ans = player.answers ? player.answers[String(qIndex)] : undefined}
												<td class="p-3 font-mono">
													{#if ans !== undefined}
														{#if ans.right}
															<span class="inline-block bg-green-500/20 text-green-400 p-1.5 rounded-md font-bold text-xs" title="Corect (+{ans.score}p)">
																✅
															</span>
														{:else}
															<span class="inline-block bg-red-500/20 text-red-400 p-1.5 rounded-md font-bold text-xs" title="Greșit (Răspuns: {ans.answer})">
																❌
															</span>
														{/if}
													{:else if player.current_question === qIndex && !player.finished}
														<span class="inline-block bg-yellow-500/20 text-yellow-300 p-1.5 rounded-md text-xs font-bold animate-pulse" title="Răspunde acum">
															⏳
														</span>
													{:else}
														<span class="text-gray-600 text-xs">—</span>
													{/if}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Footer info -->
			<div class="mt-6 text-center text-xs text-gray-500">
				<p>Se actualizează automat la fiecare 4 secunde • PIN: {game_pin}</p>
				{#if status.deadline}
					<p class="mt-1">Deadline: {new Date(status.deadline).toLocaleString()}</p>
				{/if}
			</div>
		{/if}
	</div>
</div>
