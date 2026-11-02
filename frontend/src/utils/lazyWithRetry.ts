import React, { ComponentType, lazy } from 'react';

/**
 * Enhanced React.lazy with automatic exponential retry and chunk load recovery.
 */
export function lazyWithRetry<T extends ComponentType<any>>(
  factory: () => Promise<any>,
  exportName?: string
): React.LazyExoticComponent<T> {
  return lazy(async () => {
    let attempts = 0;
    const maxAttempts = 2;

    while (attempts < maxAttempts) {
      try {
        const module = await factory();
        // Clear previous chunk reload guard on success
        if (typeof window !== 'undefined') {
          sessionStorage.removeItem('pravision_chunk_reload');
        }

        if (exportName && module[exportName]) {
          return { default: module[exportName] };
        }
        if (module.default) {
          return { default: module.default };
        }
        const firstExport = Object.values(module)[0];
        if (firstExport) {
          return { default: firstExport as T };
        }
        throw new Error(`Component export '${exportName || 'default'}' not found in loaded module.`);
      } catch (error) {
        attempts++;
        if (attempts >= maxAttempts) {
          // If in browser and hasn't forced reload yet, try single cache-bust reload
          if (typeof window !== 'undefined') {
            const alreadyReloaded = sessionStorage.getItem('pravision_chunk_reload') === 'true';
            if (!alreadyReloaded) {
              sessionStorage.setItem('pravision_chunk_reload', 'true');
              window.location.reload();
              return new Promise(() => {}); // never resolves, reload is happening
            }
          }
          throw error;
        }
        // Wait 500ms before retry
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    }
    throw new Error(`Failed to load component chunk after ${maxAttempts} attempts.`);
  });
}

