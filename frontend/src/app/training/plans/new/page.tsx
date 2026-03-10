"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const PHASE_TYPES = [
  { value: "base", label: "Base Building" },
  { value: "build", label: "Build" },
  { value: "peak", label: "Peak" },
  { value: "taper", label: "Taper" },
  { value: "recovery", label: "Recovery" },
  { value: "race", label: "Race Week" },
];

interface PhaseInput {
  name: string;
  phase_type: string;
  start_date: string;
  end_date: string;
  description: string;
}

export default function NewPlanPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [goalDate, setGoalDate] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [phases, setPhases] = useState<PhaseInput[]>([]);

  function addPhase() {
    const lastEnd = phases.length > 0 ? phases[phases.length - 1].end_date : startDate;
    const nextStart = lastEnd
      ? (() => { const d = new Date(lastEnd + "T00:00:00"); d.setDate(d.getDate() + 1); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; })()
      : "";
    setPhases([
      ...phases,
      { name: "", phase_type: "base", start_date: nextStart, end_date: "", description: "" },
    ]);
  }

  function updatePhase(index: number, field: keyof PhaseInput, value: string) {
    const updated = [...phases];
    updated[index] = { ...updated[index], [field]: value };
    // Auto-set name from phase type if name is empty
    if (field === "phase_type" && !updated[index].name) {
      updated[index].name = PHASE_TYPES.find((t) => t.value === value)?.label || value;
    }
    setPhases(updated);
  }

  function removePhase(index: number) {
    setPhases(phases.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !startDate || !endDate) return;

    setSaving(true);
    try {
      await api.createTrainingPlan({
        name,
        goal: goal || undefined,
        goal_date: goalDate || undefined,
        start_date: startDate,
        end_date: endDate,
        notes: notes || undefined,
        phases: phases
          .filter((p) => p.name && p.start_date && p.end_date)
          .map((p, i) => ({
            name: p.name,
            phase_type: p.phase_type,
            start_date: p.start_date,
            end_date: p.end_date,
            order_index: i,
            description: p.description || undefined,
          })),
      });
      router.push("/training");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create plan");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Create Training Plan</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Plan Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Plan Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Marathon Build 2027"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Goal</label>
              <input
                type="text"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. Complete first marathon"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1">Start Date *</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">End Date *</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Goal Date</label>
                <input
                  type="date"
                  value={goalDate}
                  onChange={(e) => setGoalDate(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder="General notes about this plan..."
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Phases</CardTitle>
            <Button type="button" size="sm" variant="outline" onClick={addPhase}>
              Add Phase
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {phases.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No phases yet. Phases are optional — you can add workouts directly to the plan.
              </p>
            )}

            {phases.map((phase, i) => (
              <div key={i} className="border border-border rounded-lg p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Phase {i + 1}</span>
                  <button
                    type="button"
                    onClick={() => removePhase(i)}
                    className="text-muted-foreground hover:text-red-500"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium mb-1">Name</label>
                    <input
                      type="text"
                      value={phase.name}
                      onChange={(e) => updatePhase(i, "name", e.target.value)}
                      placeholder="Phase name"
                      className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1">Type</label>
                    <select
                      value={phase.phase_type}
                      onChange={(e) => updatePhase(i, "phase_type", e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      {PHASE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium mb-1">Start</label>
                    <input
                      type="date"
                      value={phase.start_date}
                      onChange={(e) => updatePhase(i, "start_date", e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1">End</label>
                    <input
                      type="date"
                      value={phase.end_date}
                      onChange={(e) => updatePhase(i, "end_date", e.target.value)}
                      className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1">Description</label>
                  <input
                    type="text"
                    value={phase.description}
                    onChange={(e) => updatePhase(i, "description", e.target.value)}
                    placeholder="What this phase focuses on"
                    className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => router.push("/training")}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving || !name || !startDate || !endDate}>
            {saving ? "Creating..." : "Create Plan"}
          </Button>
        </div>
      </form>
    </div>
  );
}
