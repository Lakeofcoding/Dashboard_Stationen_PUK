export function NotFoundPage() {
  return (
    <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <h2 className="text-sm font-semibold">Seite nicht gefunden</h2>
      <p className="mt-2 text-sm text-slate-600">Die angeforderte Route existiert nicht.</p>
    </div>
  );
}
