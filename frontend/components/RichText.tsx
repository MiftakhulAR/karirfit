import { Fragment, type ReactNode } from "react";

/** Minimal, safe renderer for LLM text (no HTML injection): **bold**, # headings and | tables |.
 *  Everything else stays plain text; the container keeps white-space: pre-wrap for line breaks. */
function inline(s: string, key: string): ReactNode[] {
  return s.split(/(\*\*[^*\n]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>
      : <Fragment key={`${key}-${i}`}>{part.replace(/\*\*/g, "")}</Fragment>);
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());

export function RichText({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith("|")) {
      const rows: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
      i--;
      const body = rows.filter(r => !cells(r).every(c => /^:?-{2,}:?$/.test(c)));
      const [head, ...rest] = body.map(cells);
      out.push(
        <table key={`t${i}`} className="md-table">
          {head && <thead><tr>{head.map((c, j) => <th key={j}>{inline(c, `h${i}${j}`)}</th>)}</tr></thead>}
          <tbody>{rest.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c, `c${i}${k}${j}`)}</td>)}</tr>)}</tbody>
        </table>);
      continue;
    }
    const h = /^#{1,6}\s+(.*)$/.exec(line);
    out.push(<Fragment key={`l${i}`}>{h ? <strong>{inline(h[1], `hd${i}`)}</strong> : inline(line, `l${i}`)}{i < lines.length - 1 ? "\n" : ""}</Fragment>);
  }
  return <>{out}</>;
}
