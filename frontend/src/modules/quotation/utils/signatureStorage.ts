const SIGNATURE_STORAGE_PREFIX = 'qmp_user_signature_';
const SIGNATURE_GALLERY_PREFIX = 'qmp_user_signature_gallery_';
const MAX_SIGNATURE_GALLERY = 5;

export function getUserSignatureStorageKey(email: string): string {
  return `${SIGNATURE_STORAGE_PREFIX}${email.trim().toLowerCase()}`;
}

function getUserSignatureGalleryKey(email: string): string {
  return `${SIGNATURE_GALLERY_PREFIX}${email.trim().toLowerCase()}`;
}

export function getSavedUserSignature(email?: string): string {
  if (!email || typeof window === 'undefined') return '';
  try {
    return localStorage.getItem(getUserSignatureStorageKey(email)) || '';
  } catch {
    return '';
  }
}

export function getUserSignatureGallery(email?: string): string[] {
  if (!email || typeof window === 'undefined') return [];

  try {
    const saved = localStorage.getItem(getUserSignatureGalleryKey(email));
    const parsed = saved ? JSON.parse(saved) : [];
    if (!Array.isArray(parsed)) return [];

    return parsed.filter((item): item is string => typeof item === 'string' && item.startsWith('data:image/'));
  } catch {
    return [];
  }
}

export function saveUserSignature(email: string, dataUrl: string): void {
  if (typeof window === 'undefined') return;
  const key = getUserSignatureStorageKey(email);
  if (dataUrl) {
    localStorage.setItem(key, dataUrl);
  } else {
    localStorage.removeItem(key);
  }
}

/** Clear the auto-restore slot without removing saved gallery entries. */
export function clearCurrentUserSignature(email: string): void {
  saveUserSignature(email, '');
}

export function rememberUserSignature(email: string, dataUrl: string): string[] {
  if (!dataUrl) {
    saveUserSignature(email, '');
    return getUserSignatureGallery(email);
  }

  saveUserSignature(email, dataUrl);

  const gallery = getUserSignatureGallery(email).filter(item => item !== dataUrl);
  const nextGallery = [dataUrl, ...gallery].slice(0, MAX_SIGNATURE_GALLERY);

  if (typeof window !== 'undefined') {
    localStorage.setItem(getUserSignatureGalleryKey(email), JSON.stringify(nextGallery));
  }

  return nextGallery;
}

export function removeUserSignatureFromGallery(email: string, dataUrl: string): string[] {
  const nextGallery = getUserSignatureGallery(email).filter(item => item !== dataUrl);

  if (typeof window !== 'undefined') {
    localStorage.setItem(getUserSignatureGalleryKey(email), JSON.stringify(nextGallery));
  }

  if (getSavedUserSignature(email) === dataUrl) {
    saveUserSignature(email, nextGallery[0] || '');
  }

  return nextGallery;
}
