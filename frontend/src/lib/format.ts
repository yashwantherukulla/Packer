export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

export function formatPct(frac: number): string {
  return `${Math.round(frac * 100)}%`;
}

export function formatRatio(r: number): string {
  return `${r.toFixed(1)}×`;
}
