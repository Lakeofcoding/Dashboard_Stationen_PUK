/**
 * HonosReportPanel.tsx — v3
 *
 * BI-Reporting: HoNOS/HoNOSCA Outcome mit echten Einzelitem-Subskalen.
 * Drill: Klinik → Zentrum → Station (Breadcrumb + Tiles)
 * Scatter, Subskalen (Grouped Bar), Item-Detail (Heatmap), Verschlechterungsliste
 */
import { useEffect, useState, useMemo } from "react";

/* ─── Types ─── */
interface ScatterPoint {
  case_id: string; entry: number; discharge: number; diff: number;
  clinic: string; station: string; center: string;
  admission: string; discharge_date: string | null;
  subscales_entry: Record<string, number | null>;
  subscales_discharge: Record<string, number | null>;
}
interface KPIs {
  total: number; with_entry: number; with_both: number;
  improved: number; same: number; worse: number;
  avg_diff: number | null; avg_entry: number | null; avg_discharge: number | null;
  entry_completion_pct: number; pair_completion_pct: number;
  improved_pct: number; worse_pct: number;
}
interface Subscale { label: string; max: number; avg_entry: number | null; avg_discharge: number | null; avg_diff: number | null; }
interface ItemDetail { item: number; label: string; avg_entry: number | null; avg_discharge: number | null; avg_diff: number | null; n: number; }
interface ClinicRow { clinic: string; n: number; avg_diff: number; improved_pct: number; }
interface StationRow { station: string; clinic: string; center: string; n: number; avg_diff: number; improved_pct: number; }
interface HistBucket { diff: number; count: number; }
interface WorseCase { case_id: string; station: string; clinic: string; center: string; entry: number; discharge: number; diff: number; admission: string; discharge_date: string | null; }
interface Consistency { total_cases: number; honos_complete: number; completion_pct: number; discharged_total: number; discharged_complete: number; discharged_pct: number; has_items: boolean; source: string; }
type Hierarchy = Record<string, Record<string, string[]>>;
interface HonosData {
  scatter: ScatterPoint[]; kpis: KPIs; subscales: Record<string, Subscale>;
  items_detail: ItemDetail[];
  by_clinic: ClinicRow[]; by_station: StationRow[];
  histogram: HistBucket[]; worse_list: WorseCase[];
  consistency: Consistency; hierarchy: Hierarchy;
}
interface Props { auth: { token: string; stationId: string }; canView: boolean; }

const CC: Record<string, string> = { EPP: "#3b82f6", KJPP: "#a855f7", FPP: "#f59e0b", APP: "#10b981" };
const cc = (c: string) => CC[c] || "#6b7280";

/* ═══ SVG Scatter ═══ */
function Scatter({ points, hovered, onHover, dim }: {
  points: ScatterPoint[]; hovered: ScatterPoint | null;
  onHover: (p: ScatterPoint | null) => void; dim: string;
}) {
  const W = 460, H = 370, P = { t: 26, r: 26, b: 44, l: 48 };
  const pW = W-P.l-P.r, pH = H-P.t-P.b;
  const mx = useMemo(() => {
    if (!points.length) return 48;
    return Math.ceil(Math.max(...points.map(p => Math.max(p.entry, p.discharge)), 12) / 4) * 4 + 4;
  }, [points]);
  const x = (v: number) => P.l + (v/mx)*pW;
  const y = (v: number) => P.t + pH - (v/mx)*pH;
  const ticks = useMemo(() => {
    const s = mx <= 20 ? 4 : mx <= 36 ? 6 : 8;
    return Array.from({length: Math.floor(mx/s)+1}, (_,i) => i*s);
  }, [mx]);
  return (
    <svg width={W} height={H} style={{fontFamily:"system-ui"}}>
      <rect x={P.l} y={P.t} width={pW} height={pH} fill="#fafbfc" rx={4}/>
      <defs>
        <linearGradient id="ig2" x1="0" y1="1" x2="1" y2="0"><stop offset="0%" stopColor="#dcfce7" stopOpacity=".5"/><stop offset="100%" stopColor="#dcfce7" stopOpacity="0"/></linearGradient>
        <linearGradient id="wg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#fee2e2" stopOpacity="0"/><stop offset="100%" stopColor="#fee2e2" stopOpacity=".5"/></linearGradient>
      </defs>
      <polygon points={`${P.l},${P.t} ${P.l},${P.t+pH} ${P.l+pW},${P.t}`} fill="url(#ig2)"/>
      <polygon points={`${P.l+pW},${P.t+pH} ${P.l},${P.t+pH} ${P.l+pW},${P.t}`} fill="url(#wg2)"/>
      {ticks.map(t=><g key={t}>
        <line x1={x(t)} y1={P.t} x2={x(t)} y2={P.t+pH} stroke="#e5e7eb" strokeWidth={.5}/>
        <line x1={P.l} y1={y(t)} x2={P.l+pW} y2={y(t)} stroke="#e5e7eb" strokeWidth={.5}/>
        <text x={x(t)} y={P.t+pH+15} textAnchor="middle" fontSize={9} fill="#9ca3af">{t}</text>
        <text x={P.l-7} y={y(t)+3} textAnchor="end" fontSize={9} fill="#9ca3af">{t}</text>
      </g>)}
      <line x1={x(0)} y1={y(0)} x2={x(mx)} y2={y(mx)} stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="6,4"/>
      <text x={P.l+12} y={P.t+15} fontSize={9} fill="#16a34a" opacity={.6} fontWeight={600}>↑ Verbesserung</text>
      <text x={P.l+pW-12} y={P.t+pH-8} textAnchor="end" fontSize={9} fill="#dc2626" opacity={.6} fontWeight={600}>↓ Verschlechterung</text>
      {points.map(p => {
        const d2 = dim && p.clinic !== dim;
        const h = hovered?.case_id===p.case_id;
        return <circle key={p.case_id} cx={x(p.discharge)} cy={y(p.entry)} r={h?6:4}
          fill={cc(p.clinic)} opacity={d2?.1:h?1:.6}
          stroke={h?"#1f2937":"rgba(255,255,255,.7)"} strokeWidth={h?2:.8}
          style={{cursor:"pointer",transition:"all .12s"}}
          onMouseEnter={()=>onHover(p)} onMouseLeave={()=>onHover(null)}/>;
      })}
      <text x={P.l+pW/2} y={H-4} textAnchor="middle" fontSize={11} fill="#6b7280" fontWeight={600}>Austritt</text>
      <text x={10} y={P.t+pH/2} textAnchor="middle" fontSize={11} fill="#6b7280" fontWeight={600}
        transform={`rotate(-90,10,${P.t+pH/2})`}>Eintritt</text>
      {hovered&&<g>
        <rect x={Math.min(x(hovered.discharge)+10,W-160)} y={Math.max(y(hovered.entry)-46,P.t)}
          width={155} height={40} rx={6} fill="#1f2937" opacity={.92}/>
        <text x={Math.min(x(hovered.discharge)+17,W-153)} y={Math.max(y(hovered.entry)-28,P.t+16)}
          fontSize={10} fill="#fff" fontWeight={600}>Fall {hovered.case_id} ({hovered.clinic})</text>
        <text x={Math.min(x(hovered.discharge)+17,W-153)} y={Math.max(y(hovered.entry)-14,P.t+30)}
          fontSize={9} fill="#d1d5db">ET:{hovered.entry}→AT:{hovered.discharge} (Δ{hovered.diff>0?"+":""}{hovered.diff})</text>
      </g>}
    </svg>
  );
}

/* ═══ Subscale Grouped Bar ═══ */
function SubBars({subscales}:{subscales:Record<string,Subscale>}) {
  const keys = Object.keys(subscales);
  const W=380, H=170, P={t:14,r:14,b:36,l:40};
  const pW=W-P.l-P.r, pH=H-P.t-P.b, gW=pW/keys.length, bW=gW*.3;
  const mx = Math.max(...keys.map(k=>Math.max(subscales[k].avg_entry??0,subscales[k].avg_discharge??0,4)),6);
  return (
    <svg width={W} height={H} style={{fontFamily:"system-ui"}}>
      {[0,Math.round(mx/2),Math.round(mx)].map(v=><g key={v}>
        <line x1={P.l} y1={P.t+pH-(v/mx)*pH} x2={P.l+pW} y2={P.t+pH-(v/mx)*pH} stroke="#f3f4f6" strokeWidth={.5}/>
        <text x={P.l-5} y={P.t+pH-(v/mx)*pH+3} textAnchor="end" fontSize={8} fill="#9ca3af">{v}</text>
      </g>)}
      {keys.map((k,i)=>{
        const s=subscales[k], cx=P.l+i*gW+gW/2;
        const eH=((s.avg_entry??0)/mx)*pH, dH=((s.avg_discharge??0)/mx)*pH;
        const diff=s.avg_diff??0;
        return <g key={k}>
          <rect x={cx-bW-1} y={P.t+pH-eH} width={bW} height={eH} rx={3} fill="#6366f1" opacity={.75}/>
          <rect x={cx+1} y={P.t+pH-dH} width={bW} height={dH} rx={3} fill="#22c55e" opacity={.75}/>
          <text x={cx} y={H-18} textAnchor="middle" fontSize={9} fill="#374151" fontWeight={600}>{s.label}</text>
          <text x={cx} y={H-5} textAnchor="middle" fontSize={8}
            fill={diff>0?"#16a34a":diff<0?"#dc2626":"#9ca3af"} fontWeight={600}>
            Δ{diff>0?"+":""}{diff}
          </text>
        </g>;
      })}
      <rect x={P.l} y={1} width={8} height={8} rx={2} fill="#6366f1" opacity={.75}/>
      <text x={P.l+11} y={9} fontSize={8} fill="#6b7280">Eintritt</text>
      <rect x={P.l+55} y={1} width={8} height={8} rx={2} fill="#22c55e" opacity={.75}/>
      <text x={P.l+66} y={9} fontSize={8} fill="#6b7280">Austritt</text>
    </svg>
  );
}

/* ═══ Item Heatmap ═══ */
function ItemHeatmap({items}:{items:ItemDetail[]}) {
  if (!items.length) return null;
  return (
    <div style={{display:"grid",gridTemplateColumns:`120px repeat(3, 60px)`,gap:"1px",fontSize:10}}>
      <div style={{fontWeight:700,color:"#6b7280",padding:"4px 6px"}}>Item</div>
      <div style={{fontWeight:700,color:"#6366f1",padding:"4px 6px",textAlign:"center"}}>Ø ET</div>
      <div style={{fontWeight:700,color:"#22c55e",padding:"4px 6px",textAlign:"center"}}>Ø AT</div>
      <div style={{fontWeight:700,color:"#374151",padding:"4px 6px",textAlign:"center"}}>Δ</div>
      {items.map(it => {
        const d = it.avg_diff ?? 0;
        const bg = d > 0.3 ? "#f0fdf4" : d < -0.3 ? "#fef2f2" : "#f9fafb";
        return [
          <div key={`l${it.item}`} style={{padding:"3px 6px",background:"#f9fafb",color:"#374151",fontWeight:500}}>
            {it.item}. {it.label}
          </div>,
          <div key={`e${it.item}`} style={{padding:"3px 6px",textAlign:"center",background:"#f9fafb"}}>
            {it.avg_entry?.toFixed(1) ?? "—"}
          </div>,
          <div key={`d${it.item}`} style={{padding:"3px 6px",textAlign:"center",background:"#f9fafb"}}>
            {it.avg_discharge?.toFixed(1) ?? "—"}
          </div>,
          <div key={`x${it.item}`} style={{padding:"3px 6px",textAlign:"center",background:bg,
            fontWeight:700,color:d>0.3?"#16a34a":d<-0.3?"#dc2626":"#6b7280"}}>
            {it.avg_diff != null ? `${d>0?"+":""}${it.avg_diff.toFixed(1)}` : "—"}
          </div>,
        ];
      })}
    </div>
  );
}

/* ═══ KPI Card ═══ */
function Kpi({label,value,unit,sub,color,icon}:{label:string;value:string|number;unit?:string;sub?:string;color:string;icon:string}) {
  return (
    <div style={{flex:"1 1 155px",background:"#fff",borderRadius:12,padding:"13px 16px",
      border:`1px solid ${color}22`,boxShadow:"0 1px 4px rgba(0,0,0,.04)",minWidth:145}}>
      <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:5}}>
        <span style={{fontSize:15}}>{icon}</span>
        <span style={{fontSize:9,color:"#6b7280",fontWeight:600,textTransform:"uppercase",letterSpacing:".03em"}}>{label}</span>
      </div>
      <div style={{fontSize:24,fontWeight:800,color,lineHeight:1.1}}>
        {value}{unit&&<span style={{fontSize:12,fontWeight:600,marginLeft:2}}>{unit}</span>}
      </div>
      {sub&&<div style={{fontSize:9,color:"#9ca3af",marginTop:2}}>{sub}</div>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/*  MAIN PANEL                                                    */
/* ═══════════════════════════════════════════════════════════════ */
export default function HonosReportPanel({auth, canView}: Props) {
  const [data, setData] = useState<HonosData|null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);
  const [drillClinic, setDrillClinic] = useState<string|null>(null);
  const [drillCenter, setDrillCenter] = useState<string|null>(null);
  const [drillStation, setDrillStation] = useState<string|null>(null);
  const [hov, setHov] = useState<ScatterPoint|null>(null);
  const [wSort, setWSort] = useState<"diff"|"case_id"|"station">("diff");
  const [showItems, setShowItems] = useState(false);

  const fClinic = drillClinic||"", fCenter = drillCenter||"", fStation = drillStation||"";

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams();
    if(fClinic)p.set("clinic",fClinic); if(fCenter)p.set("center",fCenter); if(fStation)p.set("station",fStation);
    fetch(`/api/reporting/honos?${p}`,{headers:{Authorization:`Bearer ${auth.token}`}})
      .then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()})
      .then(d=>{setData(d);setError(null)})
      .catch(e=>setError(e.message))
      .finally(()=>setLoading(false));
  }, [auth.token, fClinic, fCenter, fStation]);

  if (!canView) return (
    <div style={{padding:60,textAlign:"center"}}>
      <div style={{fontSize:48,marginBottom:12}}>🔒</div>
      <h2 style={{margin:"0 0 8px",fontSize:18,color:"#374151"}}>Zugriff eingeschränkt</h2>
      <p style={{color:"#9ca3af",fontSize:13}}>Das HoNOS-Reporting ist nur für Klinikleitung und Direktion verfügbar.</p>
    </div>
  );
  if (loading&&!data) return <div style={{padding:40,textAlign:"center",color:"#9ca3af"}}><div style={{fontSize:32,marginBottom:8}}>📊</div>Lade HoNOS-Daten…</div>;
  if (error) return <div style={{padding:40,textAlign:"center",color:"#dc2626"}}>Fehler: {error}</div>;
  if (!data) return null;

  const {kpis, scatter, subscales, items_detail, by_clinic, by_station, histogram, worse_list, consistency, hierarchy} = data;
  const sortedWorse = [...worse_list].sort((a,b)=> wSort==="diff"?a.diff-b.diff : wSort==="case_id"?a.case_id.localeCompare(b.case_id) : a.station.localeCompare(b.station));
  const clinicKeys = Object.keys(hierarchy).sort();

  return (
    <div style={{maxWidth:1200,margin:"0 auto"}}>
      {/* Header */}
      <h2 style={{margin:"0 0 2px",fontSize:18,fontWeight:800,color:"#1f2937"}}>📊 HoNOS Outcome-Report</h2>
      <p style={{margin:"0 0 12px",fontSize:11,color:"#9ca3af"}}>
        Echtdaten-Subskalen aus {consistency.has_items ? "Einzelitems" : "Gesamtscores"} ·
        Positive Δ = Verbesserung · Berechnung identisch mit Stationsübersicht
      </p>

      {/* Breadcrumb */}
      <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:14,fontSize:13,color:"#6b7280"}}>
        <span onClick={()=>{setDrillClinic(null);setDrillCenter(null);setDrillStation(null)}}
          style={{cursor:"pointer",fontWeight:!drillClinic?700:400,color:!drillClinic?"#1d4ed8":"#6b7280"}}>Alle Kliniken</span>
        {drillClinic&&<><span style={{color:"#d1d5db"}}>/</span>
          <span onClick={()=>{setDrillCenter(null);setDrillStation(null)}}
            style={{cursor:"pointer",fontWeight:!drillCenter?700:400,color:!drillCenter?"#1d4ed8":"#6b7280"}}>{drillClinic}</span></>}
        {drillCenter&&<><span style={{color:"#d1d5db"}}>/</span>
          <span onClick={()=>setDrillStation(null)}
            style={{cursor:"pointer",fontWeight:!drillStation?700:400,color:!drillStation?"#1d4ed8":"#6b7280"}}>{drillCenter}</span></>}
        {drillStation&&<><span style={{color:"#d1d5db"}}>/</span><span style={{fontWeight:700,color:"#1d4ed8"}}>{drillStation}</span></>}
      </div>

      {/* Drill Tiles */}
      {!drillClinic && clinicKeys.length>1 && (
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))",gap:12,marginBottom:18}}>
          {clinicKeys.map(k=>{const cd=by_clinic.find(c=>c.clinic===k);return(
            <div key={k} onClick={()=>setDrillClinic(k)}
              style={{padding:"14px 16px",borderRadius:12,cursor:"pointer",transition:"all .15s",
                background:"#fff",border:`2px solid ${cc(k)}30`,boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}
              onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.borderColor=cc(k)}}
              onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.borderColor=cc(k)+"30"}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
                <span style={{width:12,height:12,borderRadius:"50%",background:cc(k)}}/>
                <span style={{fontSize:15,fontWeight:800}}>{k}</span>
              </div>
              <div style={{fontSize:11,color:"#6b7280",display:"flex",gap:10}}>
                <span>{Object.values(hierarchy[k]).flat().length} Stat.</span>
                {cd&&<><span>n={cd.n}</span><span style={{color:cd.improved_pct>=50?"#16a34a":"#dc2626",fontWeight:600}}>{cd.improved_pct}% ↑</span></>}
              </div>
            </div>);})}
        </div>)}
      {drillClinic&&!drillCenter&&hierarchy[drillClinic]&&(
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:10,marginBottom:18}}>
          {Object.keys(hierarchy[drillClinic]).sort().map(z=>{const zD=by_station.filter(s=>s.center===z);const n=zD.reduce((s,d)=>s+d.n,0);return(
            <div key={z} onClick={()=>setDrillCenter(z)}
              style={{padding:"11px 14px",borderRadius:10,cursor:"pointer",background:"#f9fafb",border:"1px solid #e5e7eb",transition:"all .12s"}}
              onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.background="#eff6ff"}}
              onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.background="#f9fafb"}}>
              <div style={{fontWeight:700,fontSize:13}}>{z}</div>
              <div style={{fontSize:10,color:"#6b7280"}}>{hierarchy[drillClinic][z].length} Stationen · n={n}</div>
            </div>);})}
        </div>)}
      {drillClinic&&drillCenter&&!drillStation&&hierarchy[drillClinic]?.[drillCenter]&&(
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(175px,1fr))",gap:10,marginBottom:18}}>
          {hierarchy[drillClinic][drillCenter].map(s=>{const sD=by_station.find(d=>d.station===s);return(
            <div key={s} onClick={()=>setDrillStation(s)}
              style={{padding:"9px 12px",borderRadius:8,cursor:"pointer",background:"#fff",border:"1px solid #e5e7eb",transition:"all .12s"}}
              onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.borderColor="#3b82f6"}}
              onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.borderColor="#e5e7eb"}}>
              <div style={{fontWeight:600,fontSize:12}}>{s}</div>
              {sD?<div style={{fontSize:10,color:"#6b7280",marginTop:1}}>n={sD.n} Ø Δ{sD.avg_diff>0?"+":""}{sD.avg_diff} {sD.improved_pct}%↑</div>
                :<div style={{fontSize:10,color:"#d1d5db",marginTop:1}}>Keine Daten</div>}
            </div>);})}
        </div>)}

      {/* KPIs */}
      <div style={{display:"flex",gap:10,flexWrap:"wrap",marginBottom:18}}>
        <Kpi icon="📈" label="Verbesserung" color="#16a34a" value={`${kpis.improved_pct}`} unit="%" sub={`${kpis.improved}/${kpis.with_both}`}/>
        <Kpi icon="📉" label="Verschlechterung" color="#dc2626" value={`${kpis.worse_pct}`} unit="%" sub={`${kpis.worse}/${kpis.with_both}`}/>
        <Kpi icon="Δ" label="Ø Differenz" color="#3b82f6"
          value={kpis.avg_diff!=null?`${kpis.avg_diff>0?"+":""}${kpis.avg_diff}`:"—"}
          sub={`ET Ø${kpis.avg_entry??"—"} → AT Ø${kpis.avg_discharge??"—"}`}/>
        <Kpi icon="📋" label="Erfassung" color="#8b5cf6" value={`${kpis.pair_completion_pct}`} unit="%"
          sub={`${kpis.with_both} Paare / ${kpis.total} Total`}/>
      </div>

      {/* Main: Scatter + Right */}
      <div style={{display:"flex",gap:18,flexWrap:"wrap",marginBottom:18}}>
        {/* Scatter */}
        <div style={{flex:"1 1 460px",background:"#fff",borderRadius:12,border:"1px solid #e5e7eb",padding:"14px 12px",boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:6}}>
            <h3 style={{margin:0,fontSize:13,fontWeight:700,color:"#374151"}}>Eintritt vs. Austritt</h3>
            <div style={{display:"flex",gap:10,fontSize:9}}>
              {Object.entries(CC).map(([c,col])=>(
                <span key={c} style={{display:"flex",alignItems:"center",gap:3,cursor:"pointer",
                  opacity:drillClinic&&drillClinic!==c?.3:1}}
                  onClick={()=>{drillClinic===c?(setDrillClinic(null),setDrillCenter(null),setDrillStation(null)):(setDrillClinic(c),setDrillCenter(null),setDrillStation(null))}}>
                  <span style={{width:7,height:7,borderRadius:"50%",background:col}}/>{c}
                </span>))}
            </div>
          </div>
          {scatter.length>0?<Scatter points={scatter} hovered={hov} onHover={setHov} dim={drillClinic&&!drillCenter?drillClinic:""}/>
            :<div style={{padding:50,textAlign:"center",color:"#9ca3af",fontSize:12}}>Keine Paardaten</div>}
          <div style={{fontSize:8,color:"#d1d5db",textAlign:"center",marginTop:2}}>n={scatter.length}</div>
        </div>

        {/* Right */}
        <div style={{flex:"1 1 360px",display:"flex",flexDirection:"column",gap:12,minWidth:270}}>
          {/* Subscales */}
          <div style={{background:"#fff",borderRadius:12,border:"1px solid #e5e7eb",padding:12,boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
              <h3 style={{margin:"0 0 4px",fontSize:13,fontWeight:700,color:"#374151"}}>Subskalen {consistency.has_items?"(Einzelitems)":"(geschätzt)"}</h3>
              {items_detail.length>0&&<button onClick={()=>setShowItems(!showItems)}
                style={{fontSize:9,padding:"3px 8px",borderRadius:4,border:"1px solid #e5e7eb",background:showItems?"#eff6ff":"#fff",
                  color:showItems?"#1d4ed8":"#6b7280",cursor:"pointer"}}>
                {showItems?"▼ Items":"▶ Items"}
              </button>}
            </div>
            {kpis.with_both>0?<SubBars subscales={subscales}/>
              :<div style={{padding:16,textAlign:"center",color:"#d1d5db",fontSize:11}}>Keine Daten</div>}
          </div>

          {/* Item Detail (toggleable) */}
          {showItems&&items_detail.length>0&&(
            <div style={{background:"#fff",borderRadius:12,border:"1px solid #e5e7eb",padding:12,boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}>
              <h3 style={{margin:"0 0 8px",fontSize:13,fontWeight:700,color:"#374151"}}>Einzelitem-Analyse</h3>
              <ItemHeatmap items={items_detail}/>
            </div>
          )}

          {/* Histogram */}
          {histogram.length>0&&(
            <div style={{background:"#fff",borderRadius:12,border:"1px solid #e5e7eb",padding:12,boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}>
              <h3 style={{margin:"0 0 4px",fontSize:13,fontWeight:700,color:"#374151"}}>Differenz-Verteilung</h3>
              <svg width={340} height={120} style={{fontFamily:"system-ui"}}>
                {(()=>{const mx2=Math.max(...histogram.map(h=>h.count),1);const bW2=Math.max(Math.min(300/histogram.length-2,20),5);
                  return histogram.map((h,i)=>{const bH=(h.count/mx2)*85;const xp=28+(i/histogram.length)*300;
                    return<g key={h.diff}><rect x={xp} y={95-bH} width={bW2} height={bH} rx={2}
                      fill={h.diff>0?"#22c55e":h.diff<0?"#ef4444":"#94a3b8"} opacity={.7}/>
                      <text x={xp+bW2/2} y={110} textAnchor="middle" fontSize={8} fill="#9ca3af">{h.diff}</text>
                      {h.count>0&&<text x={xp+bW2/2} y={92-bH} textAnchor="middle" fontSize={8} fill="#6b7280">{h.count}</text>}
                    </g>;});})()}
              </svg>
            </div>)}

          {/* Consistency */}
          <div style={{background:"#f0fdf4",borderRadius:10,border:"1px solid #bbf7d0",padding:"9px 12px"}}>
            <h4 style={{margin:"0 0 3px",fontSize:10,fontWeight:700,color:"#166534"}}>✓ Konsistenzprüfung</h4>
            <div style={{fontSize:9,color:"#15803d",lineHeight:1.5}}>
              <div>Logik: <code style={{fontSize:8}}>_q_honos</code> (identisch mit Übersicht)</div>
              <div>Gesamt: {consistency.honos_complete}/{consistency.total_cases} ({consistency.completion_pct}%)</div>
              <div>Entlassene ET+AT: {consistency.discharged_complete}/{consistency.discharged_total} ({consistency.discharged_pct}%)</div>
              {consistency.has_items&&<div style={{color:"#059669",fontWeight:600}}>✓ Berechnung aus Einzelitems</div>}
            </div>
          </div>
        </div>
      </div>

      {/* Verschlechterungsliste */}
      {worse_list.length>0&&(
        <div style={{background:"#fff",borderRadius:12,border:"1px solid #fecaca",padding:"14px 18px",marginBottom:18,boxShadow:"0 1px 4px rgba(0,0,0,.04)"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:8}}>
            <h3 style={{margin:0,fontSize:13,fontWeight:700,color:"#991b1b"}}>⚠ Verschlechterung ({worse_list.length})</h3>
            <div style={{display:"flex",gap:3,fontSize:9}}>
              {(["diff","case_id","station"] as const).map(k=>(
                <button key={k} onClick={()=>setWSort(k)}
                  style={{padding:"2px 7px",borderRadius:4,fontSize:9,cursor:"pointer",
                    border:wSort===k?"1px solid #3b82f6":"1px solid #e5e7eb",
                    background:wSort===k?"#eff6ff":"#fff",color:wSort===k?"#1d4ed8":"#6b7280",fontWeight:wSort===k?700:400}}>
                  {k==="diff"?"Δ":k==="case_id"?"Fall":"Station"}
                </button>))}
            </div>
          </div>
          <div style={{overflowX:"auto"}}>
            <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
              <thead><tr style={{borderBottom:"2px solid #fecaca"}}>
                {["Fall","Station","Klinik","Zentrum","ET","AT","Δ","Eintritt","Austritt"].map(h=>
                  <th key={h} style={{padding:"5px 8px",textAlign:"left",fontSize:9,fontWeight:700,color:"#991b1b"}}>{h}</th>)}
              </tr></thead>
              <tbody>{sortedWorse.map(w=>(
                <tr key={w.case_id} style={{borderBottom:"1px solid #fee2e2"}}>
                  <td style={{padding:"5px 8px",fontWeight:600,fontFamily:"monospace",fontSize:10}}>{w.case_id}</td>
                  <td style={{padding:"5px 8px"}}>{w.station}</td>
                  <td style={{padding:"5px 8px"}}><span style={{display:"inline-flex",alignItems:"center",gap:3}}>
                    <span style={{width:5,height:5,borderRadius:"50%",background:cc(w.clinic)}}/>{w.clinic}</span></td>
                  <td style={{padding:"5px 8px",color:"#6b7280"}}>{w.center}</td>
                  <td style={{padding:"5px 8px"}}>{w.entry}</td>
                  <td style={{padding:"5px 8px"}}>{w.discharge}</td>
                  <td style={{padding:"5px 8px",fontWeight:800,color:"#dc2626"}}>{w.diff}</td>
                  <td style={{padding:"5px 8px",fontSize:9,color:"#9ca3af"}}>{w.admission}</td>
                  <td style={{padding:"5px 8px",fontSize:9,color:"#9ca3af"}}>{w.discharge_date||"—"}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </div>)}

      {/* Methodik */}
      <div style={{padding:"8px 12px",borderRadius:8,background:"#f9fafb",border:"1px solid #e5e7eb",fontSize:9,color:"#9ca3af",lineHeight:1.5}}>
        <strong style={{color:"#6b7280"}}>Methodik:</strong> HoNOS 12 Items / HoNOSCA 13 Items. Bewertung 0–4, 9=unbekannt.
        Subskalen aus {consistency.has_items?"echten Einzelitems":"Gesamtscore-Schätzung"}.
        Konsistenz via <code style={{fontSize:8}}>_q_honos</code> (identisch mit Stationsübersicht).
      </div>
    </div>
  );
}
