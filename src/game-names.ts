import zhUrl from './data/game-zh-CN.txt?url';
import enUrl from './data/game-en-US.txt?url';
import { getLocale } from './i18n';

export interface GameName {
  zh: string;
  en: string;
}

const names = new Map<string, GameName>();
function romanNumeral(value: number): string {
  const digits: [number, string][] = [
    [1000, 'M'],
    [900, 'CM'],
    [500, 'D'],
    [400, 'CD'],
    [100, 'C'],
    [90, 'XC'],
    [50, 'L'],
    [40, 'XL'],
    [10, 'X'],
    [9, 'IX'],
    [5, 'V'],
    [4, 'IV'],
    [1, 'I'],
  ];
  let remaining = value;
  let numeral = '';
  for (const [amount, symbol] of digits) {
    while (remaining >= amount) {
      numeral += symbol;
      remaining -= amount;
    }
  }
  return numeral;
}
const aliases: Record<string, string> = {
  bank: 'd_entropy',
  bank_b: 'w_idea',
  bank_c: 'w_darwinium',
  bank_d: 'd_entrobit',
  bank_e: 'd_muta',
  bank_f: 'd_fossil',
  bank_g: 'd_ideabit',
  idle_darwin: 'w_darwinium',
  stat_doober: 'w_logits',
  beyond_bank_stardust: 'stat_stardust',
  beyond_bank_dark: 'd_darkmatter',
};
function parse(source: string): Map<string, string> {
  const result = new Map<string, string>();
  for (const record of source.split('[i2t]')) {
    const separator = record.indexOf('=');
    if (separator < 1) continue;
    const key = record.slice(0, separator).trim();
    if (key.startsWith('I2_') || !/^[\w.-]+$/.test(key)) continue;
    const value = record
      .slice(separator + 1)
      .replaceAll('[i2fb]', '')
      .replace(/<\/?[a-zA-Z][^>]*>/g, '')
      .replace(
        /&(amp|lt|gt|quot|apos);/g,
        (_, entity: string) => ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" })[entity]!,
      )
      .replace(/\s+/g, ' ')
      .trim();
    if (value) result.set(key, value);
  }
  return result;
}
export async function loadGameNames() {
  const [zh, en] = await Promise.all(
    [zhUrl, enUrl].map(async (url) => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Language file could not be loaded (${response.status})`);
      return parse(await response.text());
    }),
  );
  for (const [key, value] of en) {
    names.set(key, { zh: zh.get(key) ?? value, en: value });
  }
  for (const [key, value] of zh) {
    if (!names.has(key)) names.set(key, { zh: value, en: value });
  }
  for (const [key, target] of Object.entries(aliases)) {
    const name = names.get(target);
    if (name) names.set(key, name);
  }
}
export function gameName(key: string): GameName | undefined {
  const base = key.replace(/_(?:desc(?:ription)?|effect|body(?:_\d+)?)$/, '');
  const exact = names.get(base) ?? names.get(key);
  if (exact) return exact;
  const itemName = base.startsWith('stat_') ? names.get(`item_${base.slice(5)}`) : undefined;
  if (itemName) return itemName;
  const level = base.match(/_(\d+)$/);
  const levelName = names.get(base.replace(/_\d+$/, ''));
  const numeral = level ? romanNumeral(Number(level[1])) : '';
  return levelName && numeral
    ? {
        zh: `${levelName.zh} ${numeral}`,
        en: `${levelName.en} ${numeral}`,
      }
    : levelName;
}
export function primaryName(key: string): string | undefined {
  const name = gameName(key);
  return name && (getLocale() === 'zh-CN' ? name.zh : name.en);
}
export function alternateName(key: string): string | undefined {
  const name = gameName(key);
  return name && (getLocale() === 'zh-CN' ? name.en : name.zh);
}
