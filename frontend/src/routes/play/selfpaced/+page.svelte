<!--
SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)

SPDX-License-Identifier: MPL-2.0
-->

<script lang="ts">
	import { socket } from '$lib/socket';
	import { navbarVisible } from '$lib/stores.svelte.ts';
	import { getLocalization } from '$lib/i18n';
	import Cookies from 'js-cookie';
	import BrownButton from '$lib/components/buttons/brown.svelte';

	const { t } = getLocalization();

	interface Props {
		data: any;
	}

	let { data }: Props = $props();
	let { game_pin } = $state(data);
	navbarVisible.visible = false;

	// --- State ---
	let phase: 'join' | 'title' | 'question' | 'result' | 'leaderboard' | 'finished' = $state('join');
	let username = $state('');
	let gameData: any = $state(null);
	let questions: any[] = $state([]);
	let currentQuestionIndex = $state(0);
	let timerEnabled = $state(true);
	let timerValue = $state(0);
	let timerInterval: any = $state(null);
	let selectedAnswer: string | null = $state(null);
	let answerSubmitted = $state(false);
	let lastResult: any = $state(null);
	let leaderboard: any = $state(null);
	let initialLeaderboard: any[] = $state([]);
	let finalResults: any = $state(null);
	let bg_color = $derived(gameData ? gameData.background_color : undefined);

	// --- Socket handlers ---
	socket.on('time_sync', (data) => {
		socket.emit('echo_time_sync', data);
	});

	socket.on('self_paced_start', (data) => {
		gameData = data;
		questions = data.questions;
		timerEnabled = data.timer_enabled;
		initialLeaderboard = data.leaderboard || [];
		phase = 'title';
	});

	socket.on('game_not_found', () => {
		alert('Jocul nu a fost găsit sau a expirat.');
		game_pin = '';
		phase = 'join';
	});

	socket.on('username_already_exists', () => {
		alert('Acest nume este deja utilizat! Alege alt nume.');
	});

	socket.on('sp_question_ready', (_data) => {
		if (timerEnabled && questions[currentQuestionIndex]) {
			timerValue = parseInt(questions[currentQuestionIndex].time);
			startTimer();
		}
	});

	socket.on('sp_answer_result', (data) => {
		lastResult = data;
		answerSubmitted = true;
		clearTimer();
		phase = 'result';
	});

	socket.on('sp_leaderboard', (data) => {
		leaderboard = data;
		phase = 'leaderboard';
	});

	socket.on('sp_final_results', (data) => {
		finalResults = data;
		phase = 'finished';
		Cookies.remove('joined_game');
	});

	socket.on('already_replied', () => {
		alert('Ai răspuns deja la această întrebare!');
	});

	// --- Timer ---
	function startTimer() {
		clearTimer();
		timerInterval = setInterval(() => {
			timerValue--;
			if (timerValue <= 0) {
				clearTimer();
				if (!answerSubmitted) {
					submitAnswer('');
				}
			}
		}, 1000);
	}

	function clearTimer() {
		if (timerInterval) {
			clearInterval(timerInterval);
			timerInterval = null;
		}
	}

	// --- Actions ---
	function joinGame() {
		if (username.trim().length < 3 || game_pin.length < 6) return;
		socket.emit('join_game', {
			username: username.trim(),
			game_pin,
			captcha: undefined,
			custom_field: undefined
		});
	}

	function startQuiz() {
		currentQuestionIndex = 0;
		selectedAnswer = null;
		answerSubmitted = false;
		lastResult = null;
		phase = 'question';
		socket.emit('sp_get_question', { question_index: 0 });
	}

	function submitAnswer(answer: string) {
		if (answerSubmitted) return;
		selectedAnswer = answer;
		socket.emit('sp_submit_answer', {
			question_index: currentQuestionIndex,
			answer: answer
		});
	}

	function requestLeaderboard() {
		socket.emit('sp_get_leaderboard', {});
	}

	function nextQuestion() {
		currentQuestionIndex++;
		selectedAnswer = null;
		answerSubmitted = false;
		lastResult = null;

		if (currentQuestionIndex >= questions.length) {
			socket.emit('sp_finish', {});
			return;
		}

		phase = 'question';
		socket.emit('sp_get_question', { question_index: currentQuestionIndex });
	}

	let preventReload = true;
	const confirmUnload = (event: Event) => {
		if (preventReload) {
			event.preventDefault();
			// @ts-ignore
			event.returnValue = '';
		}
	};
</script>

<svelte:window onbeforeunload={confirmUnload} />
<svelte:head>
	<title>ClassQuiz - Test în Ritm Propriu</title>
</svelte:head>

<div
	class="min-h-screen min-w-full"
	style="background: {bg_color ? bg_color : 'transparent'}"
	class:text-black={bg_color}
>
	<!-- JOIN PHASE -->
	{#if phase === 'join'}
		<div class="flex flex-col justify-center items-center w-screen h-screen gap-6 p-4">
			{#if game_pin === '' || game_pin.length < 6}
				<form class="flex flex-col items-center gap-3">
					<h1 class="text-2xl font-bold">🕐 Test în Ritm Propriu</h1>
					<p class="text-gray-400 text-sm">Introdu codul PIN al testului</p>
					<input
						class="border border-gray-400 text-center text-black ring-0 outline-hidden p-3 rounded-lg focus:shadow-2xl transition-all text-xl w-64"
						bind:value={game_pin}
						maxlength="6"
						inputmode="numeric"
						placeholder="PIN Joc"
					/>
				</form>
			{:else}
				<form
					onsubmit={(e) => { e.preventDefault(); joinGame(); }}
					class="flex flex-col items-center gap-3"
				>
					<h1 class="text-2xl font-bold">🕐 Test în Ritm Propriu</h1>
					<p class="text-gray-400 text-sm">PIN: <span class="font-mono font-bold text-purple-400">{game_pin}</span></p>
					<input
						class="border border-gray-400 text-center text-black ring-0 outline-hidden p-3 rounded-lg focus:shadow-2xl transition-all text-xl w-64"
						bind:value={username}
						maxlength="17"
						placeholder="Numele tău"
					/>
					<BrownButton disabled={username.trim().length < 3} onclick={joinGame}>
						Alătură-te Testului
					</BrownButton>
				</form>
			{/if}
		</div>

	<!-- TITLE PHASE -->
	{:else if phase === 'title'}
		<div class="flex flex-col justify-center items-center w-screen min-h-screen gap-5 p-6 max-w-2xl mx-auto">
			<h1 class="text-4xl md:text-5xl font-bold text-center">{@html gameData.title}</h1>
			{#if gameData.description}
				<p class="text-lg text-center text-gray-300">{@html gameData.description}</p>
			{/if}
			{#if gameData.cover_image}
				<img
					src="/api/v1/storage/download/{gameData.cover_image}"
					alt="Copertă quiz"
					class="max-h-[22vh] rounded-lg shadow-lg"
				/>
			{/if}
			<div class="flex flex-wrap justify-center gap-4 text-sm text-gray-300">
				<span class="bg-gray-800/80 px-3 py-1.5 rounded-full border border-gray-700">
					📝 {questions.length} întrebări
				</span>
				{#if timerEnabled}
					<span class="bg-gray-800/80 px-3 py-1.5 rounded-full border border-gray-700">
						⏱️ Cu cronometru
					</span>
				{:else}
					<span class="bg-gray-800/80 px-3 py-1.5 rounded-full border border-gray-700">
						📝 Fără limită de timp
					</span>
				{/if}
				{#if gameData.deadline}
					<span class="bg-gray-800/80 px-3 py-1.5 rounded-full border border-gray-700">
						📅 Deadline: {new Date(gameData.deadline).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
					</span>
				{/if}
			</div>

			<!-- Jucători care au parcurs deja testul -->
			{#if initialLeaderboard && initialLeaderboard.length > 0}
				<div class="w-full bg-gray-800/90 border border-purple-500/40 rounded-xl p-4 shadow mt-1">
					<p class="text-xs font-bold uppercase tracking-wider text-purple-300 mb-2">
						🏆 Clasament actual ({initialLeaderboard.length} {initialLeaderboard.length === 1 ? 'jucător' : 'jucători'}):
					</p>
					<div class="space-y-1.5 max-h-36 overflow-y-auto pr-1">
						{#each initialLeaderboard as p, i}
							<div class="flex items-center justify-between text-sm bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-700/50">
								<div class="flex items-center gap-2">
									<span class="font-mono text-xs text-gray-400 w-5">
										{#if i === 0}🥇{:else if i === 1}🥈{:else if i === 2}🥉{:else}#{i + 1}{/if}
									</span>
									<span class="font-bold text-white">{p.username}</span>
									{#if p.finished}
										<span class="text-[10px] bg-green-900/60 text-green-300 px-1.5 py-0.2 rounded font-bold">finalizat</span>
									{/if}
								</div>
								<span class="font-mono font-bold text-purple-300">{p.score} pct</span>
							</div>
						{/each}
					</div>
				</div>
			{:else}
				<p class="text-sm text-gray-400 italic bg-gray-800/40 px-4 py-2 rounded-full">
					⭐ Fii primul care parcurge acest test!
				</p>
			{/if}

			<button
				class="mt-2 bg-purple-600 hover:bg-purple-500 text-white px-8 py-3.5 rounded-xl text-xl font-bold shadow-lg transition-all hover:scale-105"
				onclick={startQuiz}
			>
				Începe Testul →
			</button>
		</div>

	<!-- QUESTION PHASE -->
	{:else if phase === 'question' && questions[currentQuestionIndex]}
		{@const q = questions[currentQuestionIndex]}
		<div class="flex flex-col min-h-screen p-4">
			<!-- Header -->
			<div class="flex justify-between items-center mb-4">
				<span class="text-lg font-bold">
					Întrebarea {currentQuestionIndex + 1} din {questions.length}
				</span>
				{#if timerEnabled && timerValue > 0}
					<span
						class="text-2xl font-mono font-bold px-4 py-1 rounded-full"
						class:bg-red-500={timerValue <= 5}
						class:text-white={timerValue <= 5}
						class:bg-yellow-400={timerValue > 5 && timerValue <= 10}
						class:bg-gray-200={timerValue > 10}
						class:text-black={timerValue > 5}
					>
						{timerValue}s
					</span>
				{/if}
			</div>

			{#if timerEnabled}
				<div class="w-full bg-gray-700 rounded-full h-2 mb-4">
					<div
						class="bg-purple-500 h-2 rounded-full transition-all duration-1000"
						style="width: {(timerValue / parseInt(q.time)) * 100}%"
					></div>
				</div>
			{/if}

			<!-- Question text -->
			<div class="text-center mb-6">
				<h2 class="text-3xl font-bold">{@html q.question}</h2>
				{#if q.image}
					<div class="flex justify-center mt-4">
						<img
							src="/api/v1/storage/download/{q.image}"
							alt="Imagine întrebare"
							class="max-h-[25vh] rounded-lg"
						/>
					</div>
				{/if}
			</div>

			<!-- Answers -->
			{#if q.type === 'RANGE'}
				<div class="flex flex-col items-center gap-4 mt-auto mb-auto">
					<p class="text-gray-400">Minim: {q.answers.min} — Maxim: {q.answers.max}</p>
					<input
						type="number"
						class="border-2 border-gray-400 text-center text-black p-3 rounded-lg text-xl w-48"
						min={q.answers.min}
						max={q.answers.max}
						bind:value={selectedAnswer}
						disabled={answerSubmitted}
					/>
					<BrownButton
						disabled={answerSubmitted || selectedAnswer === null}
						onclick={() => submitAnswer(selectedAnswer ?? '')}
					>
						Trimite Răspunsul
					</BrownButton>
				</div>
			{:else if q.type === 'SLIDE'}
				<div class="flex flex-col items-center gap-4 mt-auto mb-auto">
					<div class="prose dark:prose-invert max-w-3xl">
						{@html q.answers}
					</div>
					<button
						class="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-xl text-lg font-bold shadow transition-all"
						onclick={nextQuestion}
					>
						Continuă →
					</button>
				</div>
			{:else}
				<!-- ABCD / TEXT / VOTING / ORDER / CHECK -->
				{@const colors = ['#e21b3c', '#1368ce', '#d89e00', '#26890c', '#0aa3a3', '#864cbf']}
				<div class="grid grid-cols-2 gap-3 mt-auto mb-4">
					{#each q.answers as answer, i}
						<button
							class="p-4 rounded-xl text-white text-lg font-bold shadow-lg transition-all hover:scale-[1.02] disabled:opacity-60"
							style="background-color: {colors[i % colors.length]}"
							class:ring-4={selectedAnswer === answer.answer}
							class:ring-white={selectedAnswer === answer.answer}
							disabled={answerSubmitted}
							onclick={() => submitAnswer(answer.answer)}
						>
							{answer.answer}
						</button>
					{/each}
				</div>
			{/if}
		</div>

	<!-- RESULT PHASE -->
	{:else if phase === 'result' && lastResult}
		<div class="flex flex-col justify-center items-center w-screen h-screen gap-6 p-8">
			{#if lastResult.right}
				<div class="text-8xl animate-bounce">✅</div>
				<h2 class="text-4xl font-bold text-green-400">Corect!</h2>
			{:else}
				<div class="text-8xl">❌</div>
				<h2 class="text-4xl font-bold text-red-400">Greșit</h2>
			{/if}
			<p class="text-2xl font-bold">
				+{lastResult.score} puncte
			</p>
			{#if lastResult.correct_answer && !lastResult.right}
				<div class="bg-gray-800 rounded-xl p-4 mt-2 max-w-md w-full text-center">
					<p class="text-gray-400 text-sm mb-1">Răspunsul corect:</p>
					{#if Array.isArray(lastResult.correct_answer)}
						{#each lastResult.correct_answer as ca}
							<p class="text-green-400 font-bold text-lg">{ca.answer}</p>
						{/each}
					{:else if lastResult.correct_answer.min_correct !== undefined}
						<p class="text-green-400 font-bold text-lg">
							{lastResult.correct_answer.min_correct} — {lastResult.correct_answer.max_correct}
						</p>
					{/if}
				</div>
			{/if}

			<div class="flex gap-4 mt-6">
				<button
					class="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl text-lg font-bold shadow transition-all"
					onclick={requestLeaderboard}
				>
					🏆 Clasament
				</button>
				<button
					class="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-xl text-lg font-bold shadow transition-all"
					onclick={nextQuestion}
				>
					{currentQuestionIndex + 1 >= questions.length ? '🏁 Finalizează' : 'Următoarea întrebare →'}
				</button>
			</div>
		</div>

	<!-- LEADERBOARD PHASE -->
	{:else if phase === 'leaderboard' && leaderboard}
		<div class="flex flex-col justify-center items-center w-screen h-screen gap-4 p-8">
			<h2 class="text-3xl font-bold mb-4">🏆 Clasament</h2>

			<div class="w-full max-w-lg">
				{#each leaderboard.top as entry, i}
					<div
						class="flex items-center justify-between p-3 rounded-lg mb-2 transition-all"
						class:bg-yellow-500={i === 0}
						class:text-black={i <= 2}
						class:bg-gray-300={i === 1}
						class:bg-amber-600={i === 2}
						class:bg-gray-700={i > 2}
						class:text-white={i > 2}
					>
						<div class="flex items-center gap-3">
							<span class="text-2xl font-bold w-8">
								{#if i === 0}🥇{:else if i === 1}🥈{:else if i === 2}🥉{:else}{i + 1}{/if}
							</span>
							<span class="font-bold text-lg"
								class:underline={entry.username === username}
							>
								{entry.username}
							</span>
						</div>
						<span class="font-mono font-bold">{entry.score} pct</span>
					</div>
				{/each}
			</div>

			{#if leaderboard.my_rank > 5}
				<div class="text-center mt-2 text-gray-400">
					<p>···</p>
					<p class="font-bold text-lg text-white">
						Locul #{leaderboard.my_rank} • {username} — {leaderboard.my_score} pct
					</p>
				</div>
			{/if}

			<p class="text-gray-400 text-sm mt-2">
				{leaderboard.total_players} {leaderboard.total_players === 1 ? 'jucător în total' : 'jucători în total'}
			</p>

			<button
				class="mt-4 bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-xl text-lg font-bold shadow transition-all"
				onclick={nextQuestion}
			>
				{currentQuestionIndex + 1 >= questions.length ? '🏁 Finalizează' : 'Următoarea întrebare →'}
			</button>
		</div>

	<!-- FINISHED PHASE -->
	{:else if phase === 'finished' && finalResults}
		<div class="flex flex-col justify-center items-center w-screen min-h-screen gap-4 p-8">
			<h1 class="text-4xl font-bold">🎉 Test Finalizat!</h1>
			<div class="text-center mt-2">
				<p class="text-5xl font-bold text-purple-400">{finalResults.my_score}</p>
				<p class="text-gray-400 mt-1">puncte acumulate</p>
			</div>
			<p class="text-2xl mt-2">
				Locul tău: <span class="font-bold text-yellow-400">#{finalResults.my_rank}</span>
				<span class="text-gray-400">din {finalResults.total_players}</span>
			</p>

			<h2 class="text-2xl font-bold mt-6 mb-2">🏆 Clasament Final</h2>
			<div class="w-full max-w-lg">
				{#each finalResults.leaderboard as entry, i}
					<div
						class="flex items-center justify-between p-3 rounded-lg mb-2 transition-all"
						class:bg-yellow-500={i === 0}
						class:text-black={i <= 2}
						class:bg-gray-300={i === 1}
						class:bg-amber-600={i === 2}
						class:bg-gray-700={i > 2}
						class:text-white={i > 2}
					>
						<div class="flex items-center gap-3">
							<span class="text-2xl font-bold w-8">
								{#if i === 0}🥇{:else if i === 1}🥈{:else if i === 2}🥉{:else}{i + 1}{/if}
							</span>
							<span class="font-bold text-lg"
								class:underline={entry.username === username}
							>
								{entry.username}
							</span>
						</div>
						<span class="font-mono font-bold">{entry.score} pct</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
