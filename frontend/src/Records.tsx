import { useEffect, useState, type FormEvent } from "react";
import { api, date, label, type Page, type Row } from "./api";
import { columns, resumes, sources, statuses, titles } from "./config";
import { useDialog, ErrorNotice, Badge } from "./ui";

export function Detail({
  kind,
  row,
  onClose,
  onEdit,
  onConvert,
  onDraft,
}: {
  kind: string;
  row: Row;
  onClose: () => void;
  onEdit: () => void;
  onConvert: () => void;
  onDraft: () => void;
}) {
  useDialog(onClose);
  const [events, setEvents] = useState<Row[]>([]);
  const [error, setError] = useState<unknown>();
  const [eventType, setEventType] = useState("recruiter_replied");
  const [eventNote, setEventNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const load = () =>
    api<Page>(`/${kind}/${row.id}/events?page=${page}`)
      .then((x) => {
        setEvents(x.items);
        setTotal(x.total);
      })
      .catch(setError);
  useEffect(() => {
    if (kind === "applications" || kind === "leads") void load();
  }, [kind, row.id, page]);
  async function addEvent(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/applications/${row.id}/events`, "POST", {
        event_type: eventType,
        metadata: { note: eventNote },
      });
      setEventNote("");
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="overlay" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Record details"
        className="modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <p className="eyebrow">{titles[kind]}</p>
            <h2>{label(row.role_title || row.name || row.subject)}</h2>
            <p>{label(row.company_name || row.email || row.recipient_email)}</p>
          </div>
          <button className="secondary" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="actions">
          {statuses[kind] && <button onClick={onEdit}>Edit record</button>}
          {kind === "leads" && row.status !== "converted" && (
            <button onClick={onConvert}>Create application</button>
          )}
          {kind === "applications" && row.application_method === "email" && (
            <button onClick={onDraft}>Compose email draft</button>
          )}
        </div>
        <dl className="details">
          {Object.entries(row)
            .filter(
              ([key, v]) =>
                v != null &&
                !["id", "company_id", "job_lead_id", "application_id"].includes(
                  key,
                ) &&
                !key.startsWith("normalized"),
            )
            .map(([key, v]) => (
              <div key={key}>
                <dt>{label(key)}</dt>
                <dd>
                  {key.endsWith("_url") || key === "website" ? (
                    <a href={String(v)} target="_blank" rel="noreferrer">
                      {String(v)}
                    </a>
                  ) : key.endsWith("_at") ? (
                    date(v)
                  ) : typeof v === "object" ? (
                    JSON.stringify(v, null, 2)
                  ) : (
                    label(v)
                  )}
                </dd>
              </div>
            ))}
        </dl>
        {(kind === "applications" || kind === "leads") && (
          <section className="history">
            <h3>Activity history</h3>
            {events.length === 0 && <p>No activity yet.</p>}
            {events.map((item) => (
              <article key={item.id}>
                <Badge value={item.event_type} />
                <span>
                  {date(item.occurred_at)} · {label(item.actor)}
                </span>
                <pre>{JSON.stringify(item.metadata, null, 2)}</pre>
              </article>
            ))}
            <div className="actions">
              <button
                className="secondary"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous events
              </button>
              <button
                className="secondary"
                disabled={page * 25 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                More events
              </button>
            </div>
            {kind === "applications" && (
              <form onSubmit={addEvent}>
                <h3>Record an event</h3>
                <label>
                  Event type
                  <input
                    required
                    pattern="[a-z][a-z0-9_]*"
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                  />
                </label>
                <label>
                  Note
                  <textarea
                    required
                    value={eventNote}
                    onChange={(e) => setEventNote(e.target.value)}
                  />
                </label>
                <button disabled={busy}>Add event</button>
              </form>
            )}
          </section>
        )}
        <ErrorNotice error={error} />
      </section>
    </div>
  );
}
export function DataTable({
  kind,
  rows,
  onSelect,
}: {
  kind: string;
  rows: Row[];
  onSelect: (row: Row) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns[kind].map((key) => (
              <th key={key}>{label(key)}</th>
            ))}
            <th>
              <span className="sr-only">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns[kind].map((key, index) => (
                <td key={key}>
                  {index === 0 ? (
                    <button
                      className="text-button"
                      onClick={() => onSelect(row)}
                    >
                      {label(row[key])}
                    </button>
                  ) : key === "status" || key.includes("resume_type") ? (
                    <Badge value={row[key]} />
                  ) : key.endsWith("_at") ? (
                    date(row[key])
                  ) : (
                    label(row[key])
                  )}
                </td>
              ))}
              <td>
                <button
                  className="text-button"
                  onClick={() => onSelect(row)}
                  aria-label={`View ${label(row.role_title || row.name || row.subject)}`}
                >
                  ↗
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Records({
  kind,
  refresh,
  openEditor,
  openDetail,
}: {
  kind: string;
  refresh: number;
  openEditor: () => void;
  openDetail: (row: Row) => void;
}) {
  const [filters, setFilters] = useState({
    search: "",
    status: "",
    source: "",
    resume_type: "",
    date_from: "",
    date_to: "",
  });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const timeout = setTimeout(() => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "20",
      });
      Object.entries(filters).forEach(([k, v]) => {
        if (v)
          params.set(
            k,
            k.startsWith("date_")
              ? new Date(
                  `${v}T${k === "date_to" ? "23:59:59" : "00:00:00"}+05:30`,
                ).toISOString()
              : v,
          );
      });
      api<Page>(`/${kind}?${params}`)
        .then((x) => {
          if (active) {
            setData(x);
            setError(undefined);
          }
        })
        .catch((e) => {
          if (active) setError(e);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [kind, page, filters, refresh]);
  const change = (key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };
  return (
    <>
      <div className="section-heading">
        <p>{data ? `${data.total} records` : "Your workspace records"}</p>
        <button onClick={openEditor}>
          + Add {titles[kind].replace(/s$/, "")}
        </button>
      </div>
      <div className="filters">
        <input
          aria-label="Search records"
          placeholder="Search…"
          value={filters.search}
          onChange={(e) => change("search", e.target.value)}
        />
        {statuses[kind] && (
          <select
            aria-label="Filter by status"
            value={filters.status}
            onChange={(e) => change("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {statuses[kind].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        )}
        {(kind === "leads" || kind === "applications") && (
          <>
            <select
              aria-label="Filter by source"
              value={filters.source}
              onChange={(e) => change("source", e.target.value)}
            >
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <select
              aria-label="Filter by resume"
              value={filters.resume_type}
              onChange={(e) => change("resume_type", e.target.value)}
            >
              <option value="">Both profiles</option>
              {resumes.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <label>
              From
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => change("date_from", e.target.value)}
              />
            </label>
            <label>
              Through
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => change("date_to", e.target.value)}
              />
            </label>
          </>
        )}
      </div>
      <ErrorNotice error={error} />
      {loading ? (
        <p role="status" className="empty">
          Loading records…
        </p>
      ) : !error && data?.items.length ? (
        <DataTable kind={kind} rows={data.items} onSelect={openDetail} />
      ) : (
        !error && (
          <div className="empty">
            <h3>
              Ready for your first{" "}
              {titles[kind].toLowerCase().replace(/s$/, "")}.
            </h3>
            <p>Add a record to start building your application history.</p>
            <button className="secondary" onClick={openEditor}>
              Create record
            </button>
          </div>
        )
      )}
      <div className="pagination">
        <span>
          Page {page} of {Math.max(1, Math.ceil((data?.total || 0) / 20))}
        </span>
        <button
          className="secondary"
          disabled={loading || page === 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Previous
        </button>
        <button
          className="secondary"
          disabled={loading || !data || page * 20 >= data.total}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </>
  );
}
