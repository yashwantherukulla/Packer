import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Home } from "@/pages/Home";

test("home renders the three engine entry points", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Layout>
        <Home />
      </Layout>
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: /packer console/i })).toBeInTheDocument();
  // Scope to the main content region: the Layout nav also links to /pack, /detect,
  // /scan (and a "Packer" brand link), so query the Home cards inside <main>.
  const main = within(screen.getByRole("main"));
  expect(main.getByRole("link", { name: /pack/i })).toHaveAttribute("href", "/pack");
  expect(main.getByRole("link", { name: /detect/i })).toHaveAttribute("href", "/detect");
  expect(main.getByRole("link", { name: /extract \+ scan/i })).toHaveAttribute("href", "/scan");
});
