import { lazy, type ComponentType } from "react";

type LazyModule<T extends ComponentType<any>> = { default: T };

function wait(delay: number) {
  return new Promise((resolve) => window.setTimeout(resolve, delay));
}

export function lazyWithRetry<T extends ComponentType<any>>(
  loader: () => Promise<LazyModule<T>>,
  retryCount = 2,
) {
  return lazy(async () => {
    let lastError: unknown;
    for (let attempt = 0; attempt <= retryCount; attempt += 1) {
      try {
        return await loader();
      } catch (error) {
        lastError = error;
        if (attempt < retryCount) await wait(250 * (attempt + 1));
      }
    }
    throw lastError;
  });
}
