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

	interface PlayerStatus {
		username: string;
		score: number;
		current_question: number;
		finished: boolean;
	}

	let status: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let pollInterval: any = $state(null);
	let copied = $state(false);

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
			pollInterval = setInterval(fetchStatus, 5000);
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
</script>

<svelte:head>
	<title>ClassQuiz - Assignment Dashboard</title>
</svelte:head>

<div class="min-h-screen p-6">
	<div class="max-w-5xl mx-auto">
		<!-- Header -->
		<div class="flex items-center justify-between mb-8">
			<div>
				<h1 class="text-3xl font-bold">🕐 Assignment Dashboard</h1>
				{#if status}
					<p class="text-xl text-gray-400 mt-1">{@html status.title}</p>
				{/if}
			</div>
			<a href="/dashboard">
				<BrownButton>← Back to Dashboard</BrownButton>
			</a>
		</div>

		{#if loading}
			<div class="flex justify-center mt-20">
				<Spinner />
			</div>
		{:else if error}
			<div class="bg-red-900/30 border border-red-500 rounded-xl p-6 text-center">
				<p class="text-xl text-red-400">{error}</p>
				<a href="/dashboard" class="text-blue-400 underline mt-2 block">Go back to Dashboard</a>
			</div>
		{:else if status}
			<!-- Share Section -->
			<div class="bg-gray-800 rounded-xl p-6 mb-6">
				<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
					<div class="text-center">
						<p class="text-sm text-gray-400 mb-1">Game PIN</p>
						<p class="text-4xl font-mono font-bold text-purple-400 select-all">{game_pin}</p>
					</div>
					<div class="text-center">
						<p class="text-sm text-gray-400 mb-1">Share Link</p>
						<button
							onclick={copyLink}
							class="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg transition-all text-sm"
						>
							{copied ? '✅ Copied!' : '📋 Copy Link'}
						</button>
					</div>
					<div class="text-center">
						<p class="text-sm text-gray-400 mb-1">QR Code</p>
						<img
							src="/api/v1/utils/qr/{game_pin}"
							alt="QR code"
							class="w-24 h-24 mx-auto dark:bg-white rounded-sm"
						/>
					</div>
				</div>
			</div>

			<!-- Stats Cards -->
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
				<div class="bg-gray-800 rounded-xl p-4 text-center">
					<p class="text-3xl font-bold text-blue-400">{status.total_players}</p>
					<p class="text-sm text-gray-400">Players Joined</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center">
					<p class="text-3xl font-bold text-green-400">{status.finished_count}</p>
					<p class="text-sm text-gray-400">Completed</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center">
					<p class="text-3xl font-bold text-yellow-400">{status.total_players - status.finished_count}</p>
					<p class="text-sm text-gray-400">In Progress</p>
				</div>
				<div class="bg-gray-800 rounded-xl p-4 text-center">
					<p class="text-3xl font-bold text-purple-400">
						{status.deadline ? getDeadlineCountdown(status.deadline) : '∞'}
					</p>
					<p class="text-sm text-gray-400">Time Left</p>
				</div>
			</div>

			<!-- Progress -->
			{#if status.total_players > 0}
				<div class="bg-gray-800 rounded-xl p-4 mb-6">
					<div class="flex justify-between text-sm text-gray-400 mb-1">
						<span>Completion</span>
						<span>{Math.round((status.finished_count / status.total_players) * 100)}%</span>
					</div>
					<div class="w-full bg-gray-700 rounded-full h-3">
						<div
							class="bg-gradient-to-r from-purple-500 to-green-400 h-3 rounded-full transition-all duration-500"
							style="width: {(status.finished_count / status.total_players) * 100}%"
						></div>
					</div>
				</div>
			{/if}

			<!-- Players Table -->
			<div class="bg-gray-800 rounded-xl overflow-hidden">
				<div class="p-4 border-b border-gray-700">
					<h2 class="text-xl font-bold">Players ({status.players.length})</h2>
				</div>
				{#if status.players.length === 0}
					<div class="p-8 text-center text-gray-400">
						<p class="text-5xl mb-4">👥</p>
						<p>No players have joined yet.</p>
						<p class="text-sm mt-2">Share the PIN or link with your students!</p>
					</div>
				{:else}
					<div class="overflow-x-auto">
						<table class="w-full">
							<thead>
								<tr class="text-left text-gray-400 text-sm border-b border-gray-700">
									<th class="p-3">#</th>
									<th class="p-3">Username</th>
									<th class="p-3">Progress</th>
									<th class="p-3">Score</th>
									<th class="p-3">Status</th>
								</tr>
							</thead>
							<tbody>
								{#each status.players as player, i}
									<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
										<td class="p-3 font-mono text-gray-400">{i + 1}</td>
										<td class="p-3 font-bold">{player.username}</td>
										<td class="p-3">
											<div class="flex items-center gap-2">
												<div class="w-24 bg-gray-700 rounded-full h-2">
													<div
														class="h-2 rounded-full transition-all duration-500"
														class:bg-green-400={player.finished}
														class:bg-purple-400={!player.finished}
														style="width: {player.finished ? 100 : ((player.current_question + 1) / status.question_count) * 100}%"
													></div>
												</div>
												<span class="text-xs text-gray-400">
													{player.finished ? status.question_count : player.current_question + 1}/{status.question_count}
												</span>
											</div>
										</td>
										<td class="p-3 font-mono font-bold">{player.score}</td>
										<td class="p-3">
											{#if player.finished}
												<span class="bg-green-500/20 text-green-400 px-2 py-1 rounded-full text-xs font-bold">
													✅ Done
												</span>
											{:else}
												<span class="bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded-full text-xs font-bold">
													⏳ Playing
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

			<!-- Footer info -->
			<div class="mt-4 text-center text-sm text-gray-500">
				<p>Auto-refreshing every 5 seconds</p>
				{#if status.deadline}
					<p>Deadline: {new Date(status.deadline).toLocaleString()}</p>
				{/if}
			</div>
		{/if}
	</div>
</div>
