import {
  createElement,
  Atom,
  Folder,
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
} from 'lucide';

const icons = {
  atom: Atom,
  folder: Folder,
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
};

export function icon(name: string, cls = '') {
  const node = icons[name as keyof typeof icons] ?? FileText;
  return createElement(node, { class: `icon ${cls}`, 'stroke-width': 1.6, 'aria-hidden': 'true' })
    .outerHTML;
}
