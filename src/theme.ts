import { isTauri } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';

export type Theme = 'light' | 'dark' | 'system';
const system = matchMedia('(prefers-color-scheme: dark)');
const saved = localStorage.getItem('cts.theme');
let preference: Theme = saved === 'light' || saved === 'dark' ? saved : 'system';

function apply() {
  const dark = preference === 'dark' || (preference === 'system' && system.matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
}
export function getTheme() {
  return preference;
}
export function setTheme(value: Theme) {
  preference = value;
  localStorage.setItem('cts.theme', value);
  apply();
  syncWindowTheme();
}
function syncWindowTheme() {
  if (isTauri()) {
    void getCurrentWindow()
      .setTheme(preference === 'system' ? null : preference)
      .catch(console.error);
  }
}
system.addEventListener('change', apply);
apply();
syncWindowTheme();
