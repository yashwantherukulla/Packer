import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { BehaviorPanel } from "@/components/BehaviorPanel";

test("renders behavior lists and the disagreement callout", () => {
  render(
    <BehaviorPanel
      behavior={{
        syscalls: ["connect", "execve"],
        fs_writes: ["/tmp/x"],
        blocked_net: ["1.2.3.4:443"],
        disagreement: "static flagged net; dynamic saw none",
      }}
    />,
  );
  expect(screen.getByText("execve")).toBeInTheDocument();
  expect(screen.getByTestId("disagreement")).toHaveTextContent(/static flagged net/);
  expect(screen.getByRole("alert")).toBeInTheDocument();
});
