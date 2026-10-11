import {
  createElement,
  Atom,
  Folder,
  FolderOpen,
  FileText,
  Search,
  Save,
  RotateCcw,
  ShieldCheck,
  ArrowRight,
  ArrowLeft,
  Pencil,
  Check,
  Globe,
  X,
  Info,
  Download,
  Sun,
  Moon,
  Monitor,
  Undo2,
  Redo2,
  ListChecks,
  Gamepad2,
} from 'lucide';

const icons = {
  atom: Atom,
  folder: Folder,
  'folder-open': FolderOpen,
  file: FileText,
  search: Search,
  save: Save,
  refresh: RotateCcw,
  shield: ShieldCheck,
  arrow: ArrowRight,
  back: ArrowLeft,
  edit: Pencil,
  check: Check,
  globe: Globe,
  close: X,
  info: Info,
  download: Download,
  light: Sun,
  dark: Moon,
  system: Monitor,
  undo: Undo2,
  redo: Redo2,
  changes: ListChecks,
  game: Gamepad2,
};

const cache = new Map<string, string>();

export function icon(name: string, cls = '') {
  const key = `${name}:${cls}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const node = icons[name as keyof typeof icons] ?? FileText;
  const markup = createElement(node, {
    class: `icon ${cls}`,
    'stroke-width': 1.6,
    'aria-hidden': 'true',
  }).outerHTML;
  cache.set(key, markup);
  return markup;
}
