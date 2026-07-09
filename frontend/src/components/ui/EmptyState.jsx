export default function EmptyState({ title, children, action }) {
  return (
    <div className="card p-10 text-center">
      {title && <h3 className="text-lg font-black">{title}</h3>}
      {children && <p className="mt-1 text-sm text-ink/60">{children}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  )
}
