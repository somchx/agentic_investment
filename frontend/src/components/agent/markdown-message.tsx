import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

// The agent answers in Markdown (headings, **bold**, *italic*, lists, tables,
// rules). Rendered with react-markdown, which never injects raw HTML from the
// model, and styled here with the app's tokens since there's no typography plugin.
const components: Components = {
  h1: ({ children }) => <h1 className="mb-2 mt-4 text-lg font-bold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-4 text-base font-bold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-3 text-sm font-bold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h4>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  del: ({ children }) => <del className="text-[var(--text-muted)]">{children}</del>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-[var(--text-ghost)]">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-[var(--text-ghost)]">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  hr: () => <hr className="my-4 border-[var(--border-primary)]" />,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-primary/50 pl-3 text-[var(--text-secondary)]">{children}</blockquote>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:opacity-80">
      {children}
    </a>
  ),
  code: ({ className, children }) =>
    className ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="rounded bg-[var(--bg-hover)] px-1 py-0.5 font-mono-num text-[0.85em]">{children}</code>
    ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-md bg-[var(--bg-hover)] p-3 font-mono-num text-xs">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-[var(--border-primary)] px-2 py-1.5 text-left font-semibold text-[var(--text-secondary)]">{children}</th>
  ),
  td: ({ children }) => <td className="border-b border-[var(--border-primary)]/60 px-2 py-1.5">{children}</td>,
}

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
