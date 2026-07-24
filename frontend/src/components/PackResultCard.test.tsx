import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { PackResultCard } from "@/components/PackResultCard";

test("shows honest original/gzip/artifact sizes + download link", () => {
  render(
    <MemoryRouter>
      <PackResultCard
        artifactId="a1"
        metrics={{
          original_bytes: 180_000,
          gzip_bytes: 48_000,
          artifact_bytes: 7_050_000,
          compression_ratio_vs_original: 39.2,
        }}
        downloadHref="/api/artifacts/a1?download=1"
        detectHref="/detect?model_ref=artifact%3Aa1"
      />
    </MemoryRouter>,
  );
  const card = screen.getByTestId("pack-result");
  expect(card).toHaveTextContent("175.8 KB"); // original
  expect(card).toHaveTextContent("46.9 KB"); // gzip
  expect(card).toHaveTextContent("6.7 MB"); // artifact
  expect(screen.getByTestId("download")).toHaveAttribute("href", "/api/artifacts/a1?download=1");
  expect(screen.getByTestId("download")).toHaveAttribute("download");
  expect(screen.getByTestId("detect-from-pack")).toHaveAttribute(
    "href",
    "/detect?model_ref=artifact%3Aa1",
  );
  expect(screen.getByTestId("artifact-id")).toHaveValue("a1");
});
