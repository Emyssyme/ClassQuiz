// SPDX-FileCopyrightText: 2023 Marlon W (Mawoka)
//
// SPDX-License-Identifier: MPL-2.0

import { signedIn } from '$lib/stores';

export async function load({ url, parent }) {
	const { email } = await parent();
	if (email) {
		signedIn.set(true);
	}
	const pin = url.searchParams.get('pin');
	return {
		game_pin: pin === null ? '' : pin
	};
}
