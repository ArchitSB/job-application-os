import { useEffect, useState } from "react";
import { api, label, type Row } from "./api";
import { ErrorNotice, Badge } from "./ui";
import { DataTable } from "./Records";

export function Dashboard({
  refresh,
  onSelect,
  navigate,
}: {
  refresh: number;
  onSelect: (row: Row) => void;
  navigate: (page: string) => void;
}) {
  const [summary, setSummary] = useState<Record<string, unknown>>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    api<Record<string, unknown>>("/dashboard/summary")
      .then(setSummary)
      .catch(setError);
  }, [refresh]);
  const cards = [
    ["total_applications", "Total applications"],
    ["applications_this_week", "Applied this week"],
    ["awaiting_responses", "Awaiting response"],
    ["interviews", "Interviews"],
    ["total_leads", "Job leads"],
    ["offers", "Offers"],
  ];
  return (
    <>
      <section className="welcome">
        <div>
          <p className="eyebrow">A LITTLE CLARITY. A LOT OF POSSIBILITY.</p>
          <h2>Your next chapter starts here.</h2>
          <p>
            Track opportunities, make deliberate choices, and keep every
            application in view.
          </p>
        </div>
        <button onClick={() => navigate("leads")}>Explore your leads ↗</button>
      </section>
      <ErrorNotice error={error} />
      <div className="stats">
        {cards.map(([key, title]) => (
          <article key={key}>
            <p>{title}</p>
            <strong>{summary ? String(summary[key]) : "—"}</strong>
          </article>
        ))}
      </div>
      <section className="panel">
        <div className="section-heading">
          <h3>Recent applications</h3>
          <button
            className="text-button"
            onClick={() => navigate("applications")}
          >
            View all →
          </button>
        </div>
        {summary && (summary.recent_applications as Row[]).length ? (
          <DataTable
            kind="applications"
            rows={summary.recent_applications as Row[]}
            onSelect={onSelect}
          />
        ) : (
          <div className="empty">
            <h3>A fresh start.</h3>
            <p>Your applications will appear here as you add them.</p>
            <button
              className="secondary"
              onClick={() => navigate("applications")}
            >
              Go to applications
            </button>
          </div>
        )}
      </section>
      <div className="breakdowns">
        {["resume_type", "source", "method"].map((group) => (
          <article className="panel" key={group}>
            <h3>By {label(group)}</h3>
            {summary &&
              Object.entries(
                summary[`applications_by_${group}`] as Record<string, number>,
              ).map(([key, count]) => (
                <div className="breakdown" key={key}>
                  <span>{label(key)}</span>
                  <strong>{count}</strong>
                </div>
              ))}
            {summary &&
              Object.keys(summary[`applications_by_${group}`] as object)
                .length === 0 && <p>No applications yet.</p>}
          </article>
        ))}
      </div>
    </>
  );
}
export function Resumes() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    api<Row[]>("/resumes").then(setRows).catch(setError);
  }, []);
  return (
    <>
      <p className="notice">
        Choose a profile from the full responsibilities and job description. A
        keyword alone is not enough.
      </p>
      <ErrorNotice error={error} />
      <div className="resume-grid">
        {rows.map((row) => (
          <article className="panel resume-card" key={row.id}>
            <p className="eyebrow">{label(row.profile_type)} PROFILE</p>
            <h2>{label(row.name)}</h2>
            <Badge value={row.active ? "active" : "inactive"} />
            <p>{label(row.description)}</p>
            <p>
              {row.local_path
                ? `Local file: ${row.local_path}`
                : "Local PDF not configured yet."}
            </p>
            <a
              className="button"
              href={String(row.drive_url)}
              target="_blank"
              rel="noreferrer"
            >
              Open resume in Drive ↗
            </a>
          </article>
        ))}
      </div>
    </>
  );
}
export function Settings() {
  const [profile, setProfile] = useState<Record<string, unknown>>();
  const [rules, setRules] = useState<Record<string, unknown>>();
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    Promise.all([
      api<Record<string, unknown>>("/profile"),
      api<Record<string, unknown>>("/rules"),
    ])
      .then(([p, r]) => {
        setProfile(p);
        setRules(r);
      })
      .catch(setError);
  }, []);
  async function save(path: string, data: Record<string, unknown>) {
    setBusy(true);
    setMessage("");
    setError(undefined);
    try {
      await api(path, "PATCH", data);
      setMessage("Changes saved.");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ErrorNotice error={error} />
      {message && (
        <p role="status" className="notice">
          {message}
        </p>
      )}
      <div className="settings-grid">
        {profile && (
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault();
              void save("/profile", profile);
            }}
          >
            <h3>Application profile</h3>
            <p>
              Personal information for forms. Keep this local application
              private.
            </p>
            {Object.entries(profile).map(([key, value]) => (
              <label key={key}>
                {label(key)}
                <input
                  type={
                    key === "date_of_birth"
                      ? "date"
                      : key === "email"
                        ? "email"
                        : key.includes("url")
                          ? "url"
                          : key === "notice_period" || key === "current_stipend"
                            ? "number"
                            : "text"
                  }
                  value={String(value ?? "")}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      [key]:
                        e.target.value === ""
                          ? null
                          : ["notice_period", "current_stipend"].includes(key)
                            ? Number(e.target.value)
                            : e.target.value,
                    })
                  }
                />
              </label>
            ))}
            <button disabled={busy}>Save profile</button>
          </form>
        )}
        {rules && (
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault();
              void save("/rules", rules);
            }}
          >
            <h3>Application rules</h3>
            <p>
              Preferences guide matching. Exclusions and lead age are enforced
              by the API. Human approval remains required for recording external
              submissions in this phase.
            </p>
            {Object.entries(rules).map(([key, value]) => (
              <label key={key}>
                {label(key)}
                {typeof value === "boolean" ? (
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) =>
                      setRules({ ...rules, [key]: e.target.checked })
                    }
                  />
                ) : Array.isArray(value) ? (
                  <textarea
                    value={value.join("\n")}
                    onChange={(e) =>
                      setRules({ ...rules, [key]: e.target.value.split("\n") })
                    }
                  />
                ) : key === "remote_preference" ? (
                  <select
                    value={String(value)}
                    onChange={(e) =>
                      setRules({ ...rules, [key]: e.target.value })
                    }
                  >
                    {["any", "preferred", "only", "onsite"].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    min="1"
                    max="3650"
                    value={String(value ?? "")}
                    onChange={(e) =>
                      setRules({
                        ...rules,
                        [key]: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                )}
              </label>
            ))}
            <button disabled={busy}>Save rules</button>
          </form>
        )}
      </div>
    </>
  );
}
