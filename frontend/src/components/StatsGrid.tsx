import {
  BriefcaseBusiness,
  Globe2,
  Sparkles,
  Wifi,
  type LucideIcon,
} from "lucide-react";

interface StatsGridProps {
  loading: boolean;
  jobCount: number;
  strongMatches: number;
  eligibleCount: number;
  activeSources: number;
}

interface StatCardProps {
  label: string;
  value: string;
  note: string;
  icon: LucideIcon;
  accent: string;
}

function StatCard({ label, value, note, icon: Icon, accent }: StatCardProps) {
  const colorClass: Record<string, string> = {
    blue: "bg-indigo-50 text-indigo-500",
    purple: "bg-purple-50 text-purple-500",
    green: "bg-emerald-50 text-emerald-600",
    orange: "bg-orange-50 text-orange-500",
  };

  return (
    <article className="min-h-[115px] rounded-[10px] border border-slate-200 bg-white p-3.5 shadow-card md:min-h-[132px] md:p-4">
      <div
        className={`mb-2.5 grid h-[30px] w-[30px] place-items-center rounded-lg ${colorClass[accent]}`}
      >
        <Icon size={18} />
      </div>
      <div className="text-[9px] font-medium text-slate-500 md:text-[10px]">
        {label}
      </div>
      <div className="mt-0.5 font-sans text-xl font-bold tracking-tight text-slate-800 md:text-[22px]">
        {value}
      </div>
      <div className="mt-0.5 text-[8px] text-slate-400 md:text-[9px]">
        {note}
      </div>
    </article>
  );
}

export function StatsGrid({
  loading,
  jobCount,
  strongMatches,
  eligibleCount,
  activeSources,
}: StatsGridProps) {
  const value = (number: number) => (loading ? "—" : number.toString());

  return (
    <section
      className="mb-7 grid grid-cols-2 gap-2.5 md:grid-cols-4 md:gap-3.5"
      aria-label="Job search overview"
    >
      <StatCard
        label="Fresh opportunities"
        value={value(jobCount)}
        note="Posted in the last 30 days"
        icon={BriefcaseBusiness}
        accent="blue"
      />
      <StatCard
        label="Strong matches"
        value={value(strongMatches)}
        note="Relevance score of 50+"
        icon={Sparkles}
        accent="purple"
      />
      <StatCard
        label="Location eligible"
        value={value(eligibleCount)}
        note="Worldwide or EMEA · Remote"
        icon={Globe2}
        accent="green"
      />
      <StatCard
        label="Active sources"
        value={value(activeSources)}
        note="Collecting opportunities"
        icon={Wifi}
        accent="orange"
      />
    </section>
  );
}
