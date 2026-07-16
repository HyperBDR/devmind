import type { PaymentTermOption } from '../types';

export const DEFAULT_PAYMENT_TERM_OPTION: PaymentTermOption = 'CIA';

export const PAYMENT_TERM_OPTIONS: { value: PaymentTermOption; label: string }[] = [
  { value: 'CIA', label: 'CIA (Cash in Advance)' },
  { value: 'NET 30', label: 'NET 30' },
  { value: 'NET 45', label: 'NET 45' },
  { value: 'NET 60', label: 'NET 60' },
  { value: 'Mixed', label: 'Mixed' },
  { value: 'Others', label: 'Others' },
];

const FIXED_PAYMENT_TERMS = PAYMENT_TERM_OPTIONS
  .filter(option => option.value !== 'Others')
  .map(option => option.value);

export function getPaymentTermsValue(option: PaymentTermOption, customTerms: string): string {
  return option === 'Others' ? customTerms.trim() : option;
}

export function inferPaymentTermOption(value: string): PaymentTermOption {
  const trimmed = value.trim();
  if (!trimmed) return DEFAULT_PAYMENT_TERM_OPTION;
  if (trimmed === 'CIA (Cash in Advance)') return 'CIA';
  const fixed = FIXED_PAYMENT_TERMS.find(option => option === trimmed);
  return fixed || 'Others';
}

export function isPaymentTermValid(option: PaymentTermOption, customTerms: string): boolean {
  return option !== 'Others' || customTerms.trim().length > 0;
}
