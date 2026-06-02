import { BACKEND_URL } from "@/lib/api";

interface AppHeaderProps {
  backendOnline: boolean | null;
  step: "paste" | "ingest" | "analyze";
}

const STEPS = [
  { id: "paste" as const, label: "Paste URLs" },
  { id: "ingest" as const, label: "Ingest" },
  { id: "analyze" as const, label: "Analyze" },
];

export default function AppHeader({ backendOnline, step }: AppHeaderProps) {
  const statusLabel =
    backendOnline === null ? "Checking..." : backendOnline ? "Online" : "Offline";
  const statusClass =
    backendOnline === null
      ? "bg-surface-muted text-text-muted"
      : backendOnline
        ? "bg-success/10 text-success"
        : "bg-danger/10 text-danger";

  return (
    <header className="mb-6 border-b border-border pb-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-accent">Creator Intelligence</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">CreatorJoy RAG Analyst</h1>
          <p className="mt-1 max-w-xl text-sm text-text-muted">
            Compare YouTube and Instagram Reels side-by-side, then chat with grounded citations.
          </p>
        </div>

        <div
          className={`inline-flex items-center gap-2 self-start rounded-full border border-border px-3 py-1.5 text-xs font-medium ${statusClass}`}
        >
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backendOnline === null
                ? "bg-text-muted/40"
                : backendOnline
                  ? "bg-success"
                  : "bg-danger"
            }`}
          />
          Backend {statusLabel}
          <span className="hidden text-text-muted sm:inline">· {BACKEND_URL}</span>
        </div>
      </div>

      <ol className="mt-5 flex flex-wrap items-center gap-2 text-xs">
        {STEPS.map((item, index) => {
          const active = item.id === step;
          const completed =
            (step === "ingest" && item.id === "paste") ||
            (step === "analyze" && (item.id === "paste" || item.id === "ingest"));

          return (
            <li key={item.id} className="flex items-center gap-2">
              {index > 0 && <span className="text-border">→</span>}
              <span
                className={`rounded-full px-3 py-1 font-medium ${
                  active
                    ? "bg-accent text-white"
                    : completed
                      ? "bg-accent-light text-accent"
                      : "bg-surface-muted text-text-muted"
                }`}
              >
                {item.label}
              </span>
            </li>
          );
        })}
      </ol>
    </header>
  );
}
