"use client";

import { useEffect, useState } from "react";
import { api, FitnessAgeData, FitnessAgeDomain } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const RATING_COLORS = {
  good: "text-emerald-600",
  neutral: "text-muted-foreground",
  poor: "text-red-500",
};

const RATING_DOT = {
  good: "bg-emerald-500",
  neutral: "bg-gray-400",
  poor: "bg-red-500",
};

const DOMAIN_ICONS: Record<string, string> = {
  Cardiorespiratory: "\u2764\ufe0f",
  Autonomic: "\u26a1",
  "Body Composition": "\ud83c\udfcb\ufe0f",
  Recovery: "\ud83d\udca4",
};

function InfoTooltip({ text }: { text: string }) {
  return (
    <div className="relative group">
      <svg className="w-4 h-4 text-muted-foreground cursor-help" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
      <div className="absolute bottom-full right-0 mb-2 w-72 rounded-lg border border-border bg-card p-3 text-xs text-foreground shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-50">
        {text}
        <div className="absolute top-full right-4 -mt-px border-4 border-transparent border-t-border" />
      </div>
    </div>
  );
}

function AgeRing({ fitnessAge, actualAge }: { fitnessAge: number; actualAge: number }) {
  const diff = actualAge - fitnessAge;
  const progress = Math.max(0, Math.min(100, 50 + diff * 2.5));
  const circumference = 2 * Math.PI * 54;
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  const ringColor = diff > 1 ? "#059669" : diff >= -1 ? "#6b7280" : "#ef4444";

  return (
    <div className="relative w-32 h-32 mx-auto">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="54" fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle
          cx="60" cy="60" r="54" fill="none" stroke={ringColor} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold" style={{ color: ringColor }}>
          {Math.round(fitnessAge)}
        </span>
        <span className="text-[10px] text-muted-foreground">fitness age</span>
      </div>
    </div>
  );
}

function DomainCard({ domain }: { domain: FitnessAgeDomain }) {
  const icon = DOMAIN_ICONS[domain.domain] || "";
  const diff = domain.age - domain.age; // placeholder
  return (
    <div className="rounded-lg border border-border p-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-xs">{icon}</span>
          <span className="text-xs font-semibold">{domain.domain}</span>
          <span className="text-[10px] text-muted-foreground">({domain.weight}%)</span>
        </div>
        <span className="text-sm font-bold">{Math.round(domain.age)}</span>
      </div>
      <div className="space-y-1">
        {domain.metrics.map((m) => (
          <div key={m.name} className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1">
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${RATING_DOT[m.rating]}`} />
              <span className="text-muted-foreground">{m.name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`font-medium ${RATING_COLORS[m.rating]}`}>
                {m.value} {m.unit}
              </span>
              <span className="text-muted-foreground/60">
                (avg {m.expected})
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[9px] text-muted-foreground/50 mt-1 truncate">{domain.source}</p>
    </div>
  );
}

const FITNESS_AGE_INFO = `Composite Fitness Age based on 4 research-backed domains:

\u2022 Cardiorespiratory (VO2max + Resting HR) \u2014 HUNT Fitness Study (N=4,637). Maps your VO2max to age-group population norms using the formula: age - 0.2 \u00d7 (VO2max - expected).

\u2022 Autonomic (HRV) \u2014 Lifelines Cohort (N=84,772). Maps your heart rate variability to age norms, reflecting nervous system health.

\u2022 Body Composition (BMI, Body Fat, Activity Level) \u2014 Jackson et al. (1990) coefficients + WHO activity guidelines. Training volume directly impacts this domain.

\u2022 Recovery (Sleep, Stress, Body Battery, Training Readiness) \u2014 Based on validated Garmin metrics and sleep research.

Each domain produces an independent "age" which is combined using research-informed weights. Values are 14-day averages for stability.`;

export function FitnessAgeCard() {
  const [data, setData] = useState<FitnessAgeData | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api.getFitnessAge().then(setData).catch(() => {});
  }, []);

  if (!data) return null;

  const diff = data.difference;
  const diffText =
    diff > 0
      ? `${Math.round(diff)} year${Math.round(diff) !== 1 ? "s" : ""} younger`
      : diff < 0
        ? `${Math.round(Math.abs(diff))} year${Math.round(Math.abs(diff)) !== 1 ? "s" : ""} older`
        : "Same as actual age";
  const diffColor = diff > 0 ? "text-emerald-600" : diff < 0 ? "text-red-500" : "text-muted-foreground";

  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-base">Fitness Age</CardTitle>
        <InfoTooltip text={FITNESS_AGE_INFO} />
      </CardHeader>
      <CardContent className="space-y-3">
        <AgeRing fitnessAge={data.fitness_age} actualAge={data.actual_age} />

        <div className="text-center">
          <p className={`text-sm font-semibold ${diffColor}`}>{diffText}</p>
          <p className="text-xs text-muted-foreground">Actual age: {data.actual_age}</p>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1"
        >
          {expanded ? "Hide" : "Show"} breakdown
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {expanded && (
          <div className="space-y-2 pt-1">
            {data.domains.map((d) => (
              <DomainCard key={d.domain} domain={d} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
