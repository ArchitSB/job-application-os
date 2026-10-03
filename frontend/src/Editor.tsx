import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, label, type Page, type Row } from "./api";
import { fields, statuses, titles, type Field } from "./config";
import { useDialog, ErrorNotice } from "./ui";

function SearchSelect({
  field,
  value,
  text,
  onChange,
}: {
  field: Field;
  value: string;
  text: string;
  onChange: (value: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    const timeout = setTimeout(() => {
      api<Page>(
        `/${field.type === "company" ? "companies" : "applications"}?page_size=25&search=${encodeURIComponent(search)}${field.type === "application" ? "&application_method=email" : ""}`,
      )
        .then((x) => {
          if (active) {
            setItems(x.items);
            setError(undefined);
          }
        })
        .catch((e) => {
          if (active) setError(e);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [search, field.type]);
  return (
    <div>
      <input
        aria-label={`Search ${field.title}`}
        placeholder={`Search ${field.type === "company" ? "companies" : "applications"}…`}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <select
        aria-label={field.title}
        required={field.required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Select {field.type}</option>
        {value && !items.some((x) => x.id === value) && (
          <option value={value}>{text || value}</option>
        )}
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {String(item.name || `${item.company_name} · ${item.role_title}`)}
          </option>
        ))}
      </select>
      <ErrorNotice error={error} />
    </div>
  );
}
export function Editor({
  kind,
  initial,
  editing,
  onClose,
  onSaved,
}: {
  kind: string;
  initial: Partial<Row>;
  editing: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  useDialog(onClose);
  const [values, setValues] = useState<Record<string, unknown>>({
    source: "other",
    ...initial,
  });
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [duplicate, setDuplicate] = useState<Record<string, unknown>>();
  const formFields = [...fields[kind]];
  if (editing && statuses[kind])
    formFields.push({
      key: "status",
      title: "Status",
      options: statuses[kind],
      required: true,
    });
  const update = (key: string, value: unknown) =>
    setValues((v) => ({ ...v, [key]: value }));
  function payload() {
    const result: Record<string, unknown> = {};
    for (const field of formFields) {
      const value = values[field.key];
      if (editing && (value ?? "") === (initial[field.key] ?? "")) continue;
      if (editing && field.key === "application_id") continue;
      result[field.key] =
        value === "" || value === undefined
          ? null
          : field.type === "number"
            ? Number(value)
            : field.type === "datetime-local" && value
              ? new Date(String(value)).toISOString()
              : field.type === "lines" && typeof value === "string"
                ? value.split("\n").filter(Boolean)
                : value;
      if (!editing && result[field.key] === null) delete result[field.key];
    }
    if (kind === "applications" && initial.job_lead_id)
      result.job_lead_id = initial.job_lead_id;
    if (values.duplicate_override_reason)
      result.duplicate_override_reason = values.duplicate_override_reason;
    return result;
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await api(
        `/${kind}${editing ? `/${initial.id}` : ""}`,
        editing ? "PATCH" : "POST",
        payload(),
      );
      onSaved();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function check() {
    setBusy(true);
    setError(undefined);
    try {
      const input: Record<string, unknown> = {};
      for (const key of [
        "company_id",
        "role_title",
        "source",
        "job_url",
        "application_url",
        "source_url",
        "external_job_id",
        "contact_email",
        "job_lead_id",
      ])
        if (values[key]) input[key] = values[key];
      if (editing) input.exclude_application_id = initial.id;
      setDuplicate(await api("/applications/check-duplicate", "POST", input));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const duplicateError =
    error instanceof ApiError && error.detail.code === "duplicate_application";
  return (
    <div className="overlay" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="editor-title"
        className="modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h2 id="editor-title">
              {editing ? "Edit" : "New"} {titles[kind].replace(/s$/, "")}
            </h2>
          </div>
          <button
            className="secondary"
            onClick={onClose}
            aria-label="Close editor"
          >
            Close
          </button>
        </header>
        {kind === "email-drafts" && (
          <p className="notice">
            Write in your own voice: direct, personal and specific. Emphasize
            engineering for technical roles, discovery and outcomes for product
            roles. This form saves a draft; it does not send email.
          </p>
        )}
        <form onSubmit={submit}>
          <div className="form-grid">
            {formFields.map((field) => {
              const raw = values[field.key];
              let value = Array.isArray(raw)
                ? raw.join("\n")
                : String(raw ?? "");
              if (field.type === "datetime-local" && value) {
                const d = new Date(value);
                value = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
                  .toISOString()
                  .slice(0, 16);
              }
              return (
                <label
                  className={
                    ["textarea", "lines"].includes(field.type || "")
                      ? "wide"
                      : ""
                  }
                  key={field.key}
                >
                  {field.title}
                  {field.required ? " *" : ""}
                  {field.type === "company" || field.type === "application" ? (
                    <SearchSelect
                      field={field}
                      value={value}
                      text={String(initial.company_name || "")}
                      onChange={(v) => update(field.key, v)}
                    />
                  ) : field.options ? (
                    <select
                      required={field.required}
                      value={value}
                      onChange={(e) => update(field.key, e.target.value)}
                    >
                      <option value="">Select…</option>
                      {field.options.map((v) => (
                        <option key={v} value={v}>
                          {label(v)}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "textarea" || field.type === "lines" ? (
                    <textarea
                      rows={field.key === "body" ? 14 : 4}
                      required={field.required}
                      value={value}
                      onChange={(e) => update(field.key, e.target.value)}
                    />
                  ) : (
                    <input
                      type={field.type || "text"}
                      required={field.required}
                      value={value}
                      onChange={(e) => update(field.key, e.target.value)}
                    />
                  )}
                </label>
              );
            })}
          </div>
          {kind === "applications" && (
            <div className="duplicate-check">
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={check}
              >
                Check for duplicates
              </button>
              {duplicate && (
                <p>
                  {label(duplicate.reason)}{" "}
                  {duplicate.is_duplicate
                    ? `Confidence: ${Math.round(Number(duplicate.confidence) * 100)}%`
                    : ""}
                </p>
              )}
              {Boolean(
                (duplicate?.requires_review && duplicate.is_duplicate) ||
                (duplicateError && error.detail.requires_review),
              ) && (
                <label>
                  Reason this is a separate opening (minimum 10 characters)
                  <textarea
                    minLength={10}
                    value={String(values.duplicate_override_reason || "")}
                    onChange={(e) =>
                      update("duplicate_override_reason", e.target.value)
                    }
                  />
                </label>
              )}
            </div>
          )}
          <ErrorNotice error={error} />
          <footer>
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button disabled={busy}>
              {busy ? "Saving…" : editing ? "Save changes" : "Create record"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
