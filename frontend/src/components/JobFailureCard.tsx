type JobFailureCardProps = {
  error?: string | null;
  errorCode?: string | null;
};

export function JobFailureCard({ error, errorCode }: JobFailureCardProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-900" role="alert">
      <h3 className="font-semibold">Job failed</h3>
      {error && <p className="mt-2 text-sm">{error}</p>}
      {errorCode && (
        <p className="mt-2 text-xs font-mono text-red-700" data-testid="job-error-code">
          {errorCode}
        </p>
      )}
    </div>
  );
}
