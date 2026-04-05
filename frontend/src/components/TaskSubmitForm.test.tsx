import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TaskSubmitForm } from "./TaskSubmitForm";

describe("TaskSubmitForm", () => {
  it("renders form inputs", () => {
    render(<TaskSubmitForm onSubmitted={vi.fn()} />);
    expect(screen.getByLabelText("Task Description")).toBeInTheDocument();
    expect(screen.getByLabelText("Team Preset (optional)")).toBeInTheDocument();
    expect(screen.getByLabelText("Target Repo (optional)")).toBeInTheDocument();
    expect(screen.getByText("Submit Task")).toBeInTheDocument();
  });

  it("submit button is disabled when task is empty", () => {
    render(<TaskSubmitForm onSubmitted={vi.fn()} />);
    const button = screen.getByText("Submit Task");
    expect(button).toBeDisabled();
  });
});
