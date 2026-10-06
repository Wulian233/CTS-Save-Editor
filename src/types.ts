export interface Entry {
  id: number;
  section: 'custom' | 'meta';
  key: string;
  value: string;
  category: string;
  note: string;
  description: string;
}
export interface SaveFile {
  path: string;
  name: string;
  exists: boolean;
  size: number;
  modified: number;
}
export interface View {
  path: string;
  entries: Entry[];
  files: SaveFile[];
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  changedIds: number[];
  originalValues: Record<number, string>;
}
export interface Location {
  label: string;
  path: string;
  files: SaveFile[];
}
export interface Update {
  version: string;
  title: string;
  url: string;
  changelog: string;
}
