<!--
SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)

SPDX-License-Identifier: MPL-2.0
-->

<script lang="ts">
	// import { alertModal } from '$lib/stores';
	import { captcha_enabled } from '$lib/config';
	import StartGameBackground from './start_game_background.svg';
	import { fade } from 'svelte/transition';
	import Spinner from '$lib/Spinner.svelte';
	import { onMount } from 'svelte';
	import { createTippy } from 'svelte-tippy';
	import { getLocalization } from '$lib/i18n';

	const { t } = getLocalization();
	let { quiz_id = $bindable() } = $props();
	let captcha_selected = $state(false);
	let selected_game_mode = $state('kahoot');
	let loading = $state(false);
	let custom_field = $state('');
	let cqcs_enabled = $state(false);
	let randomized_answers = $state(false);

	// Self-paced specific
	let sp_deadline = $state('');
	let sp_timer_enabled = $state(true);

	const tippy = createTippy({
		arrow: true,
		animation: 'perspective-subtle',
		placement: 'top-start',
		allowHTML: true
	});

	onMount(() => {
		const ls_data = localStorage.getItem('custom_field');
		custom_field = ls_data ? ls_data : '';
		// Default deadline: 7 days from now
		const d = new Date();
		d.setDate(d.getDate() + 7);
		sp_deadline = d.toISOString().slice(0, 16);
	});

	const start_game = async (id: string) => {
		let res;
		loading = true;
		localStorage.setItem('custom_field', custom_field);

		if (selected_game_mode === 'self_paced') {
			// Self-paced: call assign endpoint
			const deadline_iso = new Date(sp_deadline).toISOString();
			const params = new URLSearchParams({
				deadline: deadline_iso,
				timer_enabled: sp_timer_enabled ? 'True' : 'False',
				captcha_enabled: captcha_selected ? 'True' : 'False',
				custom_field: custom_field,
				randomize_answers: randomized_answers ? 'True' : 'False'
			});
			res = await fetch(`/api/v1/quiz/assign/${id}?${params.toString()}`, {
				method: 'POST'
			});
			if (res.status !== 200) {
				alert('Creating assignment failed');
				loading = false;
				return;
			}
			const data = await res.json();
			window.location.assign(`/admin/assign?pin=${data.game_pin}`);
			return;
		}

		const cqcs_enabled_parsed = cqcs_enabled ? 'True' : 'False';
		const randomized_answers_parsed = randomized_answers ? 'True' : 'False';
		if (captcha_enabled && captcha_selected) {
			res = await fetch(
				`/api/v1/quiz/start/${id}?captcha_enabled=True&game_mode=${selected_game_mode}&custom_field=${custom_field}&cqcs_enabled=${cqcs_enabled_parsed}`,
				{
					method: 'POST'
				}
			);
		} else {
			res = await fetch(
				`/api/v1/quiz/start/${id}?captcha_enabled=False&game_mode=${selected_game_mode}&custom_field=${custom_field}&cqcs_enabled=${cqcs_enabled_parsed}&randomize_answers=${randomized_answers_parsed}`,
				{
					method: 'POST'
				}
			);
		}
		if (res.status !== 200) {
			alert('Starting game failed');
			window.location.assign('/account/login?returnTo=/dashboard');
		} else {
			const data = await res.json();
			// eslint-disable-next-line no-undef
			plausible('Started Game', { props: { quiz_id: id, game_id: data.game_id } });
			window.location.assign(
				`/admin?token=${data.game_id}&pin=${data.game_pin}&connect=1&cqc_code=${data.cqc_code}`
			);
		}
	};

	const on_parent_click = (e: Event) => {
		if (e.target !== e.currentTarget) {
			return;
		}
		quiz_id = null;
	};
	const close_start_game_if_esc_is_pressed = (key: KeyboardEvent) => {
		if (key.code === 'Escape') {
			quiz_id = null;
		}
	};
	onMount(() => {
		document.body.addEventListener('keydown', close_start_game_if_esc_is_pressed);
	});
</script>

<div
	class="fixed top-0 left-0 flex justify-center w-screen h-screen bg-black/60 z-50 text-black"
	transition:fade|global={{ duration: 100 }}
	onclick={on_parent_click}
>
	<div
		class="w-5/6 h-5/6 bg-black m-auto rounded-lg shadow-lg p-4 flex flex-col overflow-y-auto"
		style="background-image: url({StartGameBackground}); background-color: #DFDBE5;"
	>
		<div class="flex justify-center w-full">
			<label
				for="large-toggle"
				class="inline-flex relative items-center cursor-pointer"
				class:pointer-events-none={!captcha_enabled}
				class:opacity-50={!captcha_enabled}
			>
				<input
					type="checkbox"
					bind:checked={captcha_selected}
					id="large-toggle"
					class="sr-only peer"
				/>
				<span
					class="w-14 h-7 bg-gray-200 rounded-full
					peer-focus:outline-hidden peer-focus:ring-4 peer-focus:ring-blue-300
					dark:peer-focus:ring-blue-800 dark:bg-gray-700
					peer-checked:bg-blue-600
					relative
					after:content-['']
					after:absolute after:top-0.5 after:start-[4px]
					after:bg-white after:border-gray-300 after:border
					after:rounded-full after:h-6 after:w-6
					after:transition-all
					peer-checked:after:translate-x-full
					rtl:peer-checked:after:-translate-x-full"
				></span>
				<span class="ms-3 text-sm font-medium text-gray-900"
					>Captcha {captcha_selected ? 'enabled' : 'disabled'}</span
				>
			</label>
		</div>
		{#if captcha_selected}
			<div class="flex justify-center mt-2" in:fade|global>
				<p class="w-1/3">
					{$t('start_game.captcha_message')}
				</p>
			</div>
		{/if}

		<div class="grid grid-cols-3 gap-4 my-auto">
			<div
				class="rounded-lg bg-white shadow-lg cursor-pointer transition-all p-3"
				class:opacity-50={selected_game_mode !== 'kahoot'}
				class:ring-4={selected_game_mode === 'kahoot'}
				class:ring-blue-500={selected_game_mode === 'kahoot'}
				onclick={() => {
					selected_game_mode = 'kahoot';
				}}
			>
				<h2 class="text-center text-2xl">{$t('words.normal')}</h2>
				<p class="text-sm mt-1">
					{$t('start_game.normal_mode_description')}
				</p>
			</div>
			<div
				class="rounded-lg bg-white shadow-lg cursor-pointer transition-all p-3"
				class:opacity-50={selected_game_mode !== 'normal'}
				class:ring-4={selected_game_mode === 'normal'}
				class:ring-blue-500={selected_game_mode === 'normal'}
				onclick={() => {
					selected_game_mode = 'normal';
				}}
			>
				<h2 class="text-center text-2xl">{$t('start_game.old_school_mode')}</h2>
				<p class="text-sm mt-1">
					{$t('start_game.old_school_mode_description')}
				</p>
			</div>
			<div
				class="rounded-lg bg-white shadow-lg cursor-pointer transition-all p-3 border-2 border-purple-200"
				class:opacity-50={selected_game_mode !== 'self_paced'}
				class:ring-4={selected_game_mode === 'self_paced'}
				class:ring-purple-500={selected_game_mode === 'self_paced'}
				onclick={() => {
					selected_game_mode = 'self_paced';
				}}
			>
				<h2 class="text-center text-2xl">🕐 Self-Paced</h2>
				<p class="text-sm mt-1">
					Players complete the quiz at their own pace before a deadline. Ideal for homework or
					async learning.
				</p>
			</div>
		</div>

		{#if selected_game_mode === 'self_paced'}
			<div class="flex flex-col gap-3 items-center my-auto" transition:fade|global={{ duration: 150 }}>
				<div class="flex items-center gap-3">
					<label class="text-sm font-medium text-gray-900">Deadline:</label>
					<input
						type="datetime-local"
						bind:value={sp_deadline}
						class="rounded-lg p-2 outline-hidden border border-gray-300"
					/>
				</div>
				<label class="inline-flex relative items-center cursor-pointer">
					<input
						type="checkbox"
						bind:checked={sp_timer_enabled}
						class="sr-only peer"
					/>
					<span
						class="w-14 h-7 bg-gray-200 rounded-full
						peer-focus:outline-hidden peer-focus:ring-4 peer-focus:ring-purple-300
						peer-checked:bg-purple-600
						relative
						after:content-['']
						after:absolute after:top-0.5 after:start-[4px]
						after:bg-white after:border-gray-300 after:border
						after:rounded-full after:h-6 after:w-6
						after:transition-all
						peer-checked:after:translate-x-full
						rtl:peer-checked:after:-translate-x-full"
					></span>
					<span class="ms-3 text-sm font-medium text-gray-900">
						Question timer {sp_timer_enabled ? 'enabled' : 'disabled'}
					</span>
				</label>
			</div>
		{/if}

		<div class="flex justify-center items-center my-auto">
			<label class="mr-4">{$t('result_page.custom_field')}</label>
			<input
				bind:value={custom_field}
				class="rounded-lg p-2 outline-hidden placeholder:italic"
				placeholder="Phone Number or Email"
			/>
		</div>

		{#if selected_game_mode !== 'self_paced'}
			<div class="flex justify-center w-full my-auto">
				<label for="cqc-toggle" class="inline-flex relative items-center cursor-pointer">
					<input
						type="checkbox"
						bind:checked={cqcs_enabled}
						id="cqc-toggle"
						class="sr-only peer"
					/>
					<span
						class="w-14 h-7 bg-gray-200 rounded-full
						peer-focus:outline-hidden peer-focus:ring-4 peer-focus:ring-blue-300
						dark:peer-focus:ring-blue-800 dark:bg-gray-700
						peer-checked:bg-blue-600
						relative
						after:content-['']
						after:absolute after:top-0.5 after:start-[4px]
						after:bg-white after:border-gray-300 after:border
						after:rounded-full after:h-6 after:w-6
						after:transition-all
						peer-checked:after:translate-x-full
						rtl:peer-checked:after:-translate-x-full"
					></span>
					<span class="ms-3 text-sm font-medium text-gray-900"
						><a
							href="/controller"
							target="_blank"
							use:tippy={{
								content:
									'ClassQuizControllers are small physical devices to play ClassQuiz. Click to learn more.'
							}}
							class="decoration-dashed underline cursor-help">ClassQuizControllers</a
						>
						are {cqcs_enabled ? 'enabled' : 'disabled'}</span
					>
				</label>
			</div>
		{/if}
		<div class="flex justify-center w-full my-auto">
			<label
				for="randomized-answers-toggle"
				class="inline-flex relative items-center cursor-pointer"
			>
				<input
					type="checkbox"
					bind:checked={randomized_answers}
					id="randomized-answers-toggle"
					class="sr-only peer"
				/>
				<span
					class="w-14 h-7 bg-gray-200 rounded-full
					peer-focus:outline-hidden peer-focus:ring-4 peer-focus:ring-blue-300
					dark:peer-focus:ring-blue-800 dark:bg-gray-700
					peer-checked:bg-blue-600
					relative
					after:content-['']
					after:absolute after:top-0.5 after:start-[4px]
					after:bg-white after:border-gray-300 after:border
					after:rounded-full after:h-6 after:w-6
					after:transition-all
					peer-checked:after:translate-x-full
					rtl:peer-checked:after:-translate-x-full"
				></span>
				<span class="ms-3 text-sm font-medium text-gray-900"> Randomize answers</span>
			</label>
		</div>

		<button
			class="mt-auto mx-auto p-4 rounded-lg shadow-lg transition-all marck-script text-2xl {selected_game_mode === 'self_paced' ? 'bg-purple-500 hover:bg-purple-400 text-white' : 'bg-green-500 hover:bg-green-400'}"
			onclick={() => {
				start_game(quiz_id);
			}}
		>
			{#if loading}
				<Spinner my_20={false} />
			{:else if selected_game_mode === 'self_paced'}
				🕐 Create Assignment
			{:else}
				{$t('start_game.start_game')}
			{/if}
		</button>
	</div>
</div>
