import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import Login from "./Login";
import Signup, { LocationConfirm, strength } from "./Signup";
import { stepProblems } from "./Complain";

const t = (k: string, p?: any) => k.replace(/\{(\w+)\}/g, (_, x) => String(p?.[x] ?? ""));

function mockApi(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(routes).find((k) => String(url).includes(k));
    return new Response(JSON.stringify(key ? routes[key] : {}), { status: 200, headers: { "content-type": "application/json" } });
  }));
}
afterEach(() => vi.unstubAllGlobals());

test("login card: sign in first, then create-account link, then demo dropdown", async () => {
  mockApi({ "/auth/demo-accounts": [{ username: "officer", name: "A. Kulkarni", title: "", role: "desk_officer", unit: "RB", sees: "your unit's cases" },
    { username: "student", name: "R. Verma", title: "", role: "college", unit: null, sees: "filing a complaint" }] });
  const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
  const select = await screen.findByLabelText("Try a demo account");
  const form = container.querySelector("[data-testid=signin]")!;
  const create = screen.getByRole("link", { name: "Create an account" });
  const order = (a: Node, b: Node) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
  expect(order(form, create)).toBeTruthy();
  expect(order(create, select)).toBeTruthy();
  expect(screen.getByText("Officers are added by the AICTE admin.")).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Desk Officer, A. Kulkarni, RB" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "College user, R. Verma" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue as this role" })).toBeDisabled();
  fireEvent.change(select, { target: { value: "officer" } });
  expect(screen.getByText(/You will see:/)).toHaveTextContent("your unit's cases");
  expect(screen.getByRole("button", { name: "Continue as this role" })).toBeEnabled();
});

test("password show/hide", () => {
  mockApi({});
  render(<MemoryRouter><Login /></MemoryRouter>);
  const pw = screen.getByLabelText("Password");
  expect(pw).toHaveAttribute("type", "password");
  fireEvent.click(screen.getByRole("button", { name: "Show" }));
  expect(pw).toHaveAttribute("type", "text");
});

test("create account: step 1 validates in plain words, then step 2", () => {
  mockApi({});
  render(<MemoryRouter><Signup /></MemoryRouter>);
  expect(screen.getByText("Step 1 of 2")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("Please write your full name.")).toBeInTheDocument();
  expect(screen.getByText("Tell us who you are.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Asha Patil" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "asha@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "college2026" } });
  fireEvent.click(screen.getByLabelText("Student"));
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("Step 2 of 2")).toBeInTheDocument();
  expect(screen.getByLabelText("College name")).toBeInTheDocument();
  expect(screen.getByText("Where do I find this?")).toBeInTheDocument();
  expect(strength("abc").label).toBe("Too short");
  expect(strength("college2026!x").score).toBeGreaterThanOrEqual(3);
});

test("location: confirm line with Yes, Change opens State and District", async () => {
  mockApi({ "/public/location": { status: "matched", source: "matched", city: "Pune", district: "Pune", state: "Maharashtra", region: "Western",
    sub_region: "", line: "Pune, Pune district, Maharashtra, Western region", choices: [], pin: "" },
    "/public/states": ["Goa", "Maharashtra"], "/public/districts": ["Pune", "Satara"] });
  const seen: any[] = [];
  render(<LocationConfirm city="Poona" pin="" onChange={(x) => seen.push(x)} />);
  expect(await screen.findByText("Pune, Pune district, Maharashtra, Western region.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Yes" }));
  expect(seen.at(-1)).toMatchObject({ ok: true, picked: null });
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  const st = await screen.findByLabelText("State");
  await waitFor(() => expect(screen.getByRole("option", { name: "Maharashtra" })).toBeInTheDocument());
  fireEvent.change(st, { target: { value: "Maharashtra" } });
  await waitFor(() => expect(screen.getByRole("option", { name: "Satara" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("District"), { target: { value: "Satara" } });
  expect(seen.at(-1)).toMatchObject({ ok: true, picked: { district: "Satara", state: "Maharashtra", source: "manual" } });
});

test("location: ambiguous city offers choices", async () => {
  mockApi({ "/public/location": { status: "ambiguous", source: "matched", choices: [
    { city: "Aurangabad", district: "Aurangabad", state: "Bihar", line: "a" }, { city: "Aurangabad", district: "Aurangabad", state: "Maharashtra", line: "b" }] } });
  const seen: any[] = [];
  render(<LocationConfirm city="Aurangabad" pin="" onChange={(x) => seen.push(x)} />);
  fireEvent.click(await screen.findByRole("button", { name: "Aurangabad, Maharashtra" }));
  expect(seen.at(-1)).toMatchObject({ picked: { state: "Maharashtra", source: "picked" } });
});

test("complaint wizard checks, in plain words", () => {
  const d = { category_key: "", description: "too short", happened_on: "" };
  expect(stepProblems(1, d, [], t)).toEqual(["Choose what the complaint is about.",
    "Please write at least 20 characters so the officer understands the problem."]);
  expect(stepProblems(1, { ...d, category_key: "fees", description: "x".repeat(20) }, [], t)).toEqual([]);
  const exe = new File(["MZ"], "virus.exe");
  const big = new File([new Uint8Array(6 * 1024 * 1024)], "scan.pdf");
  expect(stepProblems(2, d, [exe, big], t)).toEqual(["'virus.exe': only PDF, JPG and PNG files can be added.", "'scan.pdf' is larger than 5 MB."]);
  expect(stepProblems(1, { ...d, category_key: "fees", description: "x".repeat(25), happened_on: "2999-01-01" }, [], t)).toEqual(["The date cannot be in the future."]);
  // no jargon for complainants
  expect(JSON.stringify(stepProblems(1, d, [], t))).not.toMatch(/overlap|SLA|lien/i);
});
