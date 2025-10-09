import fetch from 'node-fetch';

export async function waitForEndpoint(url, { timeoutMs = 120000, intervalMs = 3000, expectedStatus = 200 } = {}) {
  const start = Date.now();
  let lastError;
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url, { timeout: intervalMs });
      if (response.status === expectedStatus) {
        return true;
      }
      lastError = new Error(`Unexpected status ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  if (lastError) {
    throw lastError;
  }
  throw new Error(`Timed out waiting for ${url}`);
}
