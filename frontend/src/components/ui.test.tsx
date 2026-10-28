import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CaseStamp, ProgressStrip, RuleTag, SlaChip, caseStamp } from "./ui";

const base = { status: "UNDER_PROCESS", status_label: "Under process", has_overlap: false, transfer_to: null,
  sla: { overdue: false, days_left: 10, label: "", stage: 0 } };

test("overdue beats overlap beats status", () => {
  expect(caseStamp({ ...base, has_overlap: true, sla: { ...base.sla, overdue: true, days_left: -4 } })).toMatchObject({ label: "4 days overdue", kind: "act" });
  expect(caseStamp({ ...base, has_overlap: true }).label).toBe("Overlap");
  expect(caseStamp({ ...base, status: "DISPOSED", status_label: "Disposed" }).kind).toBe("done");
  expect(caseStamp({ ...base, transfer_to: "PGRC" })).toMatchObject({ label: "Transfer to PGRC", kind: "wait" });
});

test("only one filled stamp per group: quiet turns act into outlined", () => {
  const r = { ...base, sla: { ...base.sla, overdue: true, days_left: -2 } };
  const { container } = render(<><CaseStamp r={r} /><CaseStamp r={r} quiet /></>);
  const stamps = container.querySelectorAll(".stamp");
  expect(stamps[0].className).toContain("act");
  expect(stamps[1].className).toContain("wait");
});

test("SLA chip words", () => {
  render(<><SlaChip sla={{ days_left: -3, pct_used: 110, overdue: true }} /><SlaChip sla={{ days_left: 0, pct_used: 100, overdue: false }} /></>);
  expect(screen.getByText(/3 days past due/)).toBeInTheDocument();
  expect(screen.getByText(/Due today/)).toBeInTheDocument();
});

test("score is labelled rule-based, never AI", () => {
  render(<RuleTag />);
  expect(screen.getByText("Rule-based matching")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\bAI\b/);
});

test("progress strip marks the current step", () => {
  render(<MemoryRouter><ProgressStrip now="With RB · 3 days" steps={[
    { n: 1, label: "Received", state: "done" }, { n: 2, label: "Assigned", state: "current" },
    { n: 3, label: "Under process", state: "upcoming" }, { n: 4, label: "Action taken", state: "upcoming" }, { n: 5, label: "Disposed", state: "upcoming" }]} /></MemoryRouter>);
  expect(screen.getByRole("img", { name: /Step 2 of 5: Assigned$/ })).toHaveAttribute("aria-current", "step");
});
