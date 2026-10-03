import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type Row } from "./api";
import { titles } from "./config";
import { Editor } from "./Editor";
import { Detail, Records } from "./Records";
import { Dashboard, Resumes, Settings } from "./pages";
import "./style.css";

function App() {
  const [view, setView] = useState(
    titles[location.hash.slice(1)] ? location.hash.slice(1) : "dashboard",
  );
  const [refresh, setRefresh] = useState(0);
  const [editor, setEditor] = useState<{
    kind: string;
    initial: Partial<Row>;
    editing: boolean;
  }>();
  const [detail, setDetail] = useState<{ kind: string; row: Row }>();
  const [connected, setConnected] = useState<boolean | null>(null);
  useEffect(() => {
    api("/health/db")
      .then(() => setConnected(true))
      .catch(() => setConnected(false));
    const handle = () =>
      setView(
        titles[location.hash.slice(1)] ? location.hash.slice(1) : "dashboard",
      );
    window.addEventListener("hashchange", handle);
    return () => window.removeEventListener("hashchange", handle);
  }, []);
  const navigate = (page: string) => {
    location.hash = page;
    setView(page);
    setDetail(undefined);
    setEditor(undefined);
  };
  const icons = ["◈", "⌕", "▤", "▦", "◎", "✉", "▧", "⚙"];
  return (
    <div className="app">
      <aside>
        <a className="brand" href="#dashboard">
          <span>J</span>
          <div>
            Job Application <b>OS</b>
            <small>ARCHIT'S WORKSPACE</small>
          </div>
        </a>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {Object.entries(titles).map(([key, title], i) => (
            <button
              key={key}
              className={view === key ? "selected" : ""}
              onClick={() => navigate(key)}
            >
              <span aria-hidden="true">{icons[i]}</span>
              {title}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p>
            <i className={connected ? "online" : "offline"} />
            {connected === null
              ? "Connecting…"
              : connected
                ? "Database connected"
                : "Database unavailable"}
          </p>
          <strong>Archit Singh Baghel</strong>
          <small>Personal application workspace</small>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">JOB APPLICATION OS</p>
            <h1>{titles[view]}</h1>
          </div>
          <span className="local-tag">LOCAL WORKSPACE</span>
        </header>
        {view === "dashboard" ? (
          <Dashboard
            refresh={refresh}
            navigate={navigate}
            onSelect={(row) => setDetail({ kind: "applications", row })}
          />
        ) : view === "resumes" ? (
          <Resumes />
        ) : view === "settings" ? (
          <Settings />
        ) : (
          <section className="panel">
            <Records
              key={view}
              kind={view}
              refresh={refresh}
              openEditor={() =>
                setEditor({ kind: view, initial: {}, editing: false })
              }
              openDetail={(row) => setDetail({ kind: view, row })}
            />
          </section>
        )}
        <p className="footnote">
          A clear record of every opportunity. You stay in control.
        </p>
      </main>
      {detail && (
        <Detail
          kind={detail.kind}
          row={detail.row}
          onClose={() => setDetail(undefined)}
          onEdit={() => {
            setEditor({
              kind: detail.kind,
              initial: detail.row,
              editing: true,
            });
            setDetail(undefined);
          }}
          onConvert={() => {
            const r = detail.row;
            setEditor({
              kind: "applications",
              initial: {
                company_id: r.company_id,
                company_name: r.company_name,
                role_title: r.role_title,
                source: r.source,
                job_lead_id: r.id,
                job_url: r.job_url,
                application_url: r.application_url,
                source_url: r.source_url,
                contact_email: r.contact_email,
              },
              editing: false,
            });
            setDetail(undefined);
          }}
          onDraft={() => {
            const r = detail.row;
            setEditor({
              kind: "email-drafts",
              initial: {
                application_id: r.id,
                recipient_email: r.contact_email,
                recipient_name: r.contact_name,
                resume_type: r.resume_type,
                subject: `Application for ${r.role_title} | Archit Singh Baghel`,
              },
              editing: false,
            });
            setDetail(undefined);
          }}
        />
      )}
      {editor && (
        <Editor
          {...editor}
          onClose={() => setEditor(undefined)}
          onSaved={() => {
            setEditor(undefined);
            setRefresh((x) => x + 1);
          }}
        />
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
