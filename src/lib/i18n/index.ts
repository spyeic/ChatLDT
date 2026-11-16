import i18next from 'i18next';
import { writable } from 'svelte/store';
import en from './locales/en-US/translation.json';
import zh from './locales/zh-CN/translation.json';
export const locale = writable('');
export async function initI18n(language = 'en-US') {
	if (!i18next.isInitialized)
		await i18next.init({
			lng: language,
			fallbackLng: 'en-US',
			keySeparator: false,
			resources: { 'en-US': { translation: en }, 'zh-CN': { translation: zh } },
			interpolation: { escapeValue: false }
		});
	else await i18next.changeLanguage(language);
	locale.set(language);
	document.documentElement.lang = language;
}
export function t(key: string) {
	return i18next.isInitialized ? i18next.t(key) : key;
}
