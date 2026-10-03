import { useEffect } from "react";
import { ApiError, label } from "./api";

export function useDialog(onClose: () => void) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const selector =
      "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]";
    dialog?.querySelector<HTMLElement>(selector)?.focus();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keydown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && dialog) {
        const nodes = [...dialog.querySelectorAll<HTMLElement>(selector)];
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      document.body.style.overflow = before;
      previous?.focus();
    };
  }, [onClose]);
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const details = error instanceof ApiError ? error.detail : {};
  const messages = Array.isArray(details.fields)
    ? (details.fields as { field: string; message: string }[])
    : [];
  return (
    <div role="alert" className="notice error">
      <strong>
        {error instanceof Error ? error.message : "Something went wrong"}
      </strong>
      {messages.map((x) => (
        <div key={x.field}>
          {x.field}: {x.message}
        </div>
      ))}
    </div>
  );
}
export function Badge({ value }: { value: unknown }) {
  return <span className={`badge badge-${String(value)}`}>{label(value)}</span>;
}
