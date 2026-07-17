export const FORM_SELECT_CLASS =
  'qmp-select-field w-full p-2 border rounded-dm focus:outline-none text-dm-text text-sm';

export const FORM_SELECT_COMPACT_CLASS = `${FORM_SELECT_CLASS} h-10 min-w-0 text-sm`;

export const FORM_SELECT_COMPACT_TRIGGER_CLASS = 'h-10 min-w-0 text-sm';

export const FORM_SELECT_DISABLED_CLASS =
  'disabled:bg-[#f5f5f5] disabled:text-dm-text-tertiary disabled:cursor-not-allowed';

export function getFormComboboxClass(hasError = false): string {
  return `qmp-combobox-field w-full p-2 border rounded-dm focus:outline-none text-dm-text text-sm ${
    hasError ? 'border-dm-error bg-dm-error-bg/30' : 'border-dm-border bg-white'
  }`;
}
