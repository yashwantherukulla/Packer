export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "pending";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, "0");
  return [
    parsed.getUTCFullYear(),
    pad(parsed.getUTCMonth() + 1),
    pad(parsed.getUTCDate()),
  ].join("-")
    .concat(
      ` ${pad(parsed.getUTCHours())}:${pad(parsed.getUTCMinutes())}:${pad(parsed.getUTCSeconds())} UTC`,
    );
}
