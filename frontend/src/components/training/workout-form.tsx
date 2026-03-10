"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { PlannedWorkout, TrainingPhase } from "@/lib/api";

const WORKOUT_TYPES = [
  { value: "easy_run", label: "Easy Run" },
  { value: "long_run", label: "Long Run" },
  { value: "tempo_run", label: "Tempo Run" },
  { value: "interval_run", label: "Interval Run" },
  { value: "hill_repeats", label: "Hill Repeats" },
  { value: "cross_training", label: "Cross Training" },
  { value: "rest", label: "Rest Day" },
];

export function WorkoutForm({
  planId,
  phases,
  initialDate,
  workout,
  onSave,
  onDelete,
  onComplete,
  onSkip,
  onClose,
}: {
  planId: number;
  phases: TrainingPhase[];
  initialDate?: string;
  workout?: PlannedWorkout;
  onSave: (data: Record<string, unknown>) => void;
  onDelete?: () => void;
  onComplete?: () => void;
  onSkip?: () => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(workout?.title || "");
  const [workoutType, setWorkoutType] = useState(workout?.workout_type || "easy_run");
  const [date, setDate] = useState(workout?.scheduled_date || initialDate || "");
  const [phaseId, setPhaseId] = useState<number | "">(workout?.phase_id || "");
  const [description, setDescription] = useState(workout?.description || "");
  const [targetDistance, setTargetDistance] = useState(
    workout?.target_distance_meters ? String(workout.target_distance_meters / 1000) : ""
  );
  const [targetDuration, setTargetDuration] = useState(
    workout?.target_duration_seconds ? String(Math.round(workout.target_duration_seconds / 60)) : ""
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const data: Record<string, unknown> = {
      plan_id: planId,
      scheduled_date: date,
      workout_type: workoutType,
      title: title || WORKOUT_TYPES.find((t) => t.value === workoutType)?.label || workoutType,
    };
    if (phaseId) data.phase_id = phaseId;
    if (description) data.description = description;
    if (targetDistance) data.target_distance_meters = parseFloat(targetDistance) * 1000;
    if (targetDuration) data.target_duration_seconds = parseFloat(targetDuration) * 60;
    onSave(data);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-background rounded-xl border border-border shadow-lg w-full max-w-md p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">{workout ? "Edit Workout" : "Add Workout"}</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <div className="flex flex-wrap gap-1.5">
              {WORKOUT_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => {
                    setWorkoutType(t.value);
                    if (!title || WORKOUT_TYPES.some((wt) => wt.label === title)) {
                      setTitle(t.label);
                    }
                  }}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    workoutType === t.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="e.g. Easy 5K"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            {phases.length > 0 && (
              <div>
                <label className="block text-sm font-medium mb-1">Phase</label>
                <select
                  value={phaseId}
                  onChange={(e) => setPhaseId(e.target.value ? Number(e.target.value) : "")}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">None</option>
                  {phases.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Target Distance (km)</label>
              <input
                type="number"
                step="0.1"
                value={targetDistance}
                onChange={(e) => setTargetDistance(e.target.value)}
                placeholder="e.g. 5.0"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Target Duration (min)</label>
              <input
                type="number"
                value={targetDuration}
                onChange={(e) => setTargetDuration(e.target.value)}
                placeholder="e.g. 30"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Notes</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="Workout instructions or notes..."
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary resize-y"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="flex gap-2">
              {workout && onComplete && workout.status === "planned" && (
                <Button type="button" size="sm" variant="outline" onClick={onComplete}>
                  Complete
                </Button>
              )}
              {workout && onSkip && workout.status === "planned" && (
                <Button type="button" size="sm" variant="outline" onClick={onSkip}>
                  Skip
                </Button>
              )}
              {workout && onDelete && (
                <Button type="button" size="sm" variant="outline" onClick={onDelete} className="text-red-500 hover:text-red-600">
                  Delete
                </Button>
              )}
            </div>
            <Button type="submit" size="sm">
              {workout ? "Update" : "Add Workout"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
