/**
 * Display helpers for money values. The API always sends money as decimal strings
 * (never floats); the UI only formats them and never does money arithmetic.
 */
const DECIMAL_RE = /^-?\d+(\.\d+)?$/;

export function formatUsd(amount: string): string {
  if (!DECIMAL_RE.test(amount)) {
    throw new Error(`invalid decimal string: ${amount}`);
  }
  const negative = amount.startsWith("-");
  const unsigned = negative ? amount.slice(1) : amount;
  const [whole, frac = ""] = unsigned.split(".");
  const cents = `${frac}00`.slice(0, 2);
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}$${grouped}.${cents}`;
}

/** Format an estimated range. Callers always label it as an estimate. */
export function formatRange(low: string, high: string): string {
  return low === high ? formatUsd(low) : `${formatUsd(low)} – ${formatUsd(high)}`;
}
