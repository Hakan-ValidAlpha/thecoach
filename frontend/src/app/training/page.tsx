"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, TrainingPlan, PlannedWorkout, Activity, TrainingPhase } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { WeekCalendar } from "@/components/training/week-calendar";
import { WorkoutForm } from "@/components/training/workout-form";

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function dateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export default function TrainingPage() {
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [activePlan, setActivePlan] = useState<TrainingPlan | null>(null);
  const [workouts, setWorkouts] = useState<PlannedWorkout[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editWorkout, setEditWorkout] = useState<PlannedWorkout | undefined>();
  const [formDate, setFormDate] = useState<string>("");
  const [compliance, setCompliance] = useState<{ completed: number; total: number; pct: number } | null>(null);
  const [syncing, setSyncing] = useState(false);

  const WEEKS_SHOWN = 4;
  const rangeEnd = addDays(weekStart, WEEKS_SHOWN * 7 - 1);

  const loadWeekData = useCallback(async (planId: number, ws: Date) => {
    const we = addDays(ws, WEEKS_SHOWN * 7 - 1);
    const [wk, act] = await Promise.all([
      api.getWorkouts({ plan_id: planId, start_date: dateKey(ws), end_date: dateKey(we) }),
      api.getActivities({ start_date: dateKey(ws), end_date: dateKey(we), limit: 100 }),
    ]);
    setWorkouts(wk);
    setActivities(act);
  }, []);

  const loadCompliance = useCallback(async (planId: number) => {
    const c = await api.getPlanCompliance(planId);
    setCompliance({ completed: c.completed, total: c.total, pct: c.compliance_pct });
  }, []);

  useEffect(() => {
    api.getTrainingPlans("active").then((p) => {
      setPlans(p);
      if (p.length > 0) {
        // Prefer the plan with the most workouts
        const best = p.reduce((a, b) => (b.workout_count ?? 0) > (a.workout_count ?? 0) ? b : a, p[0]);
        setActivePlan(best);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (activePlan) {
      loadWeekData(activePlan.id, weekStart);
      loadCompliance(activePlan.id);
    }
  }, [activePlan, weekStart, loadWeekData, loadCompliance]);

  function handlePrevWeek() {
    setWeekStart((prev) => addDays(prev, -7 * WEEKS_SHOWN));
  }

  function handleNextWeek() {
    setWeekStart((prev) => addDays(prev, 7 * WEEKS_SHOWN));
  }

  function handleToday() {
    setWeekStart(getMonday(new Date()));
  }

  function handleDayClick(date: Date) {
    if (!activePlan) return;
    setFormDate(dateKey(date));
    setEditWorkout(undefined);
    setShowForm(true);
  }

  function handleWorkoutClick(w: PlannedWorkout) {
    setEditWorkout(w);
    setFormDate(w.scheduled_date);
    setShowForm(true);
  }

  async function handleSave(data: Record<string, unknown>) {
    if (!activePlan) return;
    if (editWorkout) {
      await api.updateWorkout(editWorkout.id, data);
    } else {
      await api.createWorkout(data as Parameters<typeof api.createWorkout>[0]);
    }
    setShowForm(false);
    setEditWorkout(undefined);
    await loadWeekData(activePlan.id, weekStart);
    await loadCompliance(activePlan.id);
  }

  async function handleDelete() {
    if (!editWorkout || !activePlan) return;
    await api.deleteWorkout(editWorkout.id);
    setShowForm(false);
    setEditWorkout(undefined);
    await loadWeekData(activePlan.id, weekStart);
    await loadCompliance(activePlan.id);
  }

  async function handleComplete() {
    if (!editWorkout || !activePlan) return;
    await api.completeWorkout(editWorkout.id);
    setShowForm(false);
    setEditWorkout(undefined);
    await loadWeekData(activePlan.id, weekStart);
    await loadCompliance(activePlan.id);
  }

  async function handleSkip() {
    if (!editWorkout || !activePlan) return;
    await api.skipWorkout(editWorkout.id);
    setShowForm(false);
    setEditWorkout(undefined);
    await loadWeekData(activePlan.id, weekStart);
    await loadCompliance(activePlan.id);
  }

  async function handleWorkoutDrop(workoutId: number, newDate: string) {
    if (!activePlan) return;
    await api.updateWorkout(workoutId, { scheduled_date: newDate });
    await loadWeekData(activePlan.id, weekStart);
  }

  async function handleAutoMatch() {
    if (!activePlan) return;
    const result = await api.autoMatchWorkouts(activePlan.id);
    if (result.matched > 0) {
      await loadWeekData(activePlan.id, weekStart);
      await loadCompliance(activePlan.id);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Training</h1>
        <Skeleton className="h-96" />
      </div>
    );
  }

  async function handleSyncGarmin() {
    setSyncing(true);
    try {
      await api.syncGarminCalendar();
      // Wait for background task, then reload
      setTimeout(async () => {
        const p = await api.getTrainingPlans("active");
        setPlans(p);
        if (p.length > 0) {
          const plan = p[0];
          setActivePlan(plan);
          await loadWeekData(plan.id, weekStart);
          await loadCompliance(plan.id);
        }
        setSyncing(false);
      }, 4000);
    } catch {
      setSyncing(false);
    }
  }

  if (!activePlan) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Training</h1>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handleSyncGarmin} disabled={syncing}>
              {syncing ? "Syncing..." : "Sync from Garmin"}
            </Button>
            <Link href="/training/plans/new">
              <Button size="sm">Create Plan</Button>
            </Link>
          </div>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground mb-4">No active training plan. Sync from Garmin or create one manually.</p>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={handleSyncGarmin} disabled={syncing}>
                {syncing ? "Syncing..." : "Sync from Garmin"}
              </Button>
              <Link href="/training/plans/new">
                <Button>Create Plan</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const rangeLabel = `${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} - ${rangeEnd.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;

  // Build per-week data
  const weeks = Array.from({ length: WEEKS_SHOWN }, (_, i) => addDays(weekStart, i * 7));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold truncate">{activePlan.name}</h1>
            {activePlan.goal && (
              <p className="text-sm text-muted-foreground truncate">{activePlan.goal}</p>
            )}
          </div>
          {compliance && (
            <div className="flex items-center gap-2 shrink-0">
              <div className="w-16 md:w-24 h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all"
                  style={{ width: `${compliance.pct}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {compliance.pct}%
              </span>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={handleSyncGarmin} disabled={syncing}>
            {syncing ? "Syncing..." : "Sync Garmin"}
          </Button>
          <Button size="sm" variant="outline" onClick={handleAutoMatch}>
            Auto-match
          </Button>
          <Link href="/training/plans/new">
            <Button size="sm" variant="outline">New Plan</Button>
          </Link>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handlePrevWeek}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </Button>
          <Button size="sm" variant="outline" onClick={handleToday}>Today</Button>
          <Button size="sm" variant="outline" onClick={handleNextWeek}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </Button>
        </div>
        <span className="text-sm font-medium">{rangeLabel}</span>
      </div>

      {/* 4-week calendar */}
      <div className="space-y-3">
        {weeks.map((ws) => {
          const we = addDays(ws, 6);
          const weekWorkouts = workouts.filter((w) => w.scheduled_date >= dateKey(ws) && w.scheduled_date <= dateKey(we));
          const weekActivities = activities.filter((a) => {
            const d = a.started_at.split("T")[0];
            return d >= dateKey(ws) && d <= dateKey(we);
          });
          const phase = activePlan.phases.find((p) => p.start_date <= dateKey(addDays(ws, 3)) && p.end_date >= dateKey(addDays(ws, 3)));
          return (
            <WeekCalendar
              key={dateKey(ws)}
              weekStart={ws}
              workouts={weekWorkouts}
              activities={weekActivities}
              onWorkoutClick={handleWorkoutClick}
              onDayClick={handleDayClick}
              onWorkoutDrop={handleWorkoutDrop}
              phaseName={phase?.name}
            />
          );
        })}
      </div>

      {/* Workout form modal */}
      {showForm && (
        <WorkoutForm
          planId={activePlan.id}
          phases={activePlan.phases}
          initialDate={formDate}
          workout={editWorkout}
          onSave={handleSave}
          onDelete={editWorkout ? handleDelete : undefined}
          onComplete={editWorkout ? handleComplete : undefined}
          onSkip={editWorkout ? handleSkip : undefined}
          onClose={() => { setShowForm(false); setEditWorkout(undefined); }}
        />
      )}
    </div>
  );
}
