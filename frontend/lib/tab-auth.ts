/** Per-tab persistence plus a unique broadcast/lock channel for each page instance.
 * The adapter keeps a stable sessionStorage slot across reloads while remapping
 * the SDK's random storageKey. Duplicated tabs may start with a copied session,
 * but later sign-in/sign-out events cannot overwrite the original tab.
 */
export function tabAuthOptions(storage: Storage, pageId: string) {
  const storageKey = `karirfit:auth-channel:${pageId}`;
  const persistedKey = "karirfit:tab-auth:v1";
  const memory = new Map<string, string>();
  const keyFor = (key: string) => key.startsWith(storageKey)
    ? persistedKey + key.slice(storageKey.length) : key;
  return {
    storageKey,
    storage: {
      getItem(key: string): string | null {
        const mapped = keyFor(key);
        try { return storage.getItem(mapped) ?? memory.get(mapped) ?? null; }
        catch { return memory.get(mapped) ?? null; }
      },
      setItem(key: string, value: string) {
        const mapped = keyFor(key); memory.set(mapped, value);
        try { storage.setItem(mapped, value); } catch { /* memory-only if blocked */ }
      },
      removeItem(key: string) {
        const mapped = keyFor(key); memory.delete(mapped);
        try { storage.removeItem(mapped); } catch { /* memory-only if blocked */ }
      },
    },
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  };
}

/** Browser data must always include its account owner. Legacy unowned data is not adopted. */
export function accountKey(userId: string, item: string) {
  return `karirfit:v2:user:${encodeURIComponent(userId)}:${item}`;
}
