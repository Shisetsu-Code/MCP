export function waitBudget(value, fallback) {
  const number=Number(value ?? fallback);
  return Number.isFinite(number) ? Math.max(0,Math.min(25000,number)) : fallback;
}

export function pollDelay(attempt, remaining) {
  return Math.min(100 * 2 ** attempt,2000,Math.max(0,remaining));
}
