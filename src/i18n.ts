import zh from './locales/zh-CN.json';
import en from './locales/en-US.json';

type Catalog = { [key: string]: string | Catalog };
export type Locale = 'zh-CN' | 'en-US';
const saved = localStorage.getItem('cts.locale');
let locale: Locale =
  saved === 'zh-CN' || saved === 'en-US'
    ? saved
    : navigator.language.startsWith('zh')
      ? 'zh-CN'
      : 'en-US';
export function getLocale() {
  return locale;
}
export function setLocale(value: Locale) {
  locale = value;
  localStorage.setItem('cts.locale', value);
  document.documentElement.lang = value;
}
function lookup(catalog: Catalog, key: string): string | undefined {
  let current: string | Catalog = catalog;
  for (const part of key.split('.')) {
    if (typeof current === 'string') return undefined;
    current = current[part];
    if (current === undefined) return undefined;
  }
  return typeof current === 'string' ? current : undefined;
}
export function t(key: string, args: Record<string, string | number> = {}): string {
  const value =
    lookup((locale === 'zh-CN' ? zh : en) as Catalog, key) ?? lookup(en as Catalog, key) ?? key;
  return value.replace(/\{(\w+)\}/g, (_, name: string) => String(args[name] ?? `{${name}}`));
}
setLocale(locale);
