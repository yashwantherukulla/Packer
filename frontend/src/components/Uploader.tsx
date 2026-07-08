import { useState } from "react";

export type UploaderProps = {
  accept: string; // e.g. ".zip" or ".safetensors,.pak"
  label: string;
  maxBytes?: number;
  onFile: (file: File) => void;
};

export function Uploader({ accept, label, maxBytes, onFile }: UploaderProps) {
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);
  const accepts = accept.split(",").map((s) => s.trim().toLowerCase());

  const validate = (file: File): string | null => {
    if (!accepts.some((a) => file.name.toLowerCase().endsWith(a))) return `Expected ${accept}`;
    if (maxBytes && file.size > maxBytes) return `File exceeds ${maxBytes} bytes`;
    return null;
  };

  const handle = (file: File | undefined) => {
    if (!file) return;
    const err = validate(file);
    if (err) {
      setError(err);
      setName(null);
      return;
    }
    setError(null);
    setName(file.name);
    onFile(file);
  };

  return (
    <div className="rounded-lg border border-dashed p-6">
      <label className="block text-sm font-medium">
        {label}
        <input
          type="file"
          accept={accept}
          aria-label={label}
          className="mt-2 block w-full text-sm"
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </label>
      {name && (
        <p className="mt-2 text-sm text-emerald-700" role="status">
          {name}
        </p>
      )}
      {error && (
        <p className="mt-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
