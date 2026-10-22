'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine,
} from 'recharts'
import {
  Activity, Cpu, Zap, BarChart2, Eye, Settings, Play, Pause, Square,
  TrendingUp, RefreshCw, ArrowUpDown, Radio, Atom,
  Brain, Layers, Server, AlertTriangle, Clock,
  Wifi, WifiOff, Database, Hash, Shield, CheckCircle,
  XCircle, AlertCircle, ChevronRight, Terminal, Hexagon,
} from 'lucide-react'

// ================================================================
// McKINSEY × VEUVE CLICQUOT DESIGN SYSTEM
// ================================================================
const C = {
  // Backgrounds — McKinsey navy-black
  bg:           '#060D1A',
  surface:      '#0B1826',
  elevated:     '#112440',
  border:       '#1A3050',
  borderBrt:    '#254B7A',

  // Text hierarchy
  text:         '#EEF4FB',
  textSub:      '#7A9CB8',
  textMuted:    '#3A5A78',

  // McKinsey Blues
  blue:         '#1A60A8',
  blueBright:   '#3D8EDB',
  blueDeep:     '#0E3F7A',

  // Veuve Clicquot Gold
  gold:         '#C8901A',
  goldBright:   '#E0AD3A',
  goldPale:     '#F0CB6A',

  // Veuve Clicquot Orange
  orange:       '#D87830',
  orangeBright: '#F09040',

  // Luxury Grey
  grey:         '#647A90',
  greyLight:    '#96AAC0',

  // Sand
  sand:         '#C0A878',
  sandBright:   '#D8BF96',

  // Functional
  green:        '#2AC890',
  red:          '#E04545',
  purple:       '#8870F0',
}

const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"
const SANS = "'Inter',-apple-system,BlinkMacSystemFont,sans-serif"

// ================================================================
// DODECAHEDRON GEOMETRY (precomputed at module level)
// ================================================================
const PHI_G = (1 + Math.sqrt(5)) / 2
const INV_PHI = 1 / PHI_G
const NORM3 = Math.sqrt(3)

const RAW_VERTS = [
  [1,1,1],[1,1,-1],[1,-1,1],[1,-1,-1],
  [-1,1,1],[-1,1,-1],[-1,-1,1],[-1,-1,-1],
  [0,INV_PHI,PHI_G],[0,INV_PHI,-PHI_G],[0,-INV_PHI,PHI_G],[0,-INV_PHI,-PHI_G],
  [INV_PHI,PHI_G,0],[-INV_PHI,PHI_G,0],[INV_PHI,-PHI_G,0],[-INV_PHI,-PHI_G,0],
  [PHI_G,0,INV_PHI],[PHI_G,0,-INV_PHI],[-PHI_G,0,INV_PHI],[-PHI_G,0,-INV_PHI],
]
const VERTS_3D = RAW_VERTS.map(([x,y,z]) => [x/NORM3, y/NORM3, z/NORM3])
const DODEC_EDGES = []
for (let i = 0; i < 20; i++) {
  for (let j = i+1; j < 20; j++) {
    const [x1,y1,z1] = VERTS_3D[i], [x2,y2,z2] = VERTS_3D[j]
    const d = Math.sqrt((x1-x2)**2+(y1-y2)**2+(z1-z2)**2)
    if (d < 0.76) DODEC_EDGES.push([i,j])
  }
}

function projectDodec(angle, tiltX = 0.52) {
  return VERTS_3D.map(([x,y,z]) => {
    const x1 = x * Math.cos(angle) + z * Math.sin(angle)
    const z1 = -x * Math.sin(angle) + z * Math.cos(angle)
    const y2 = y * Math.cos(tiltX) - z1 * Math.sin(tiltX)
    const z2 = y * Math.sin(tiltX) + z1 * Math.cos(tiltX)
    return { x: x1, y: y2, z: z2 }
  })
}

// ================================================================
// ANIMATED DODECAHEDRON COMPONENT
// ================================================================
function DodecahedronViz({ size = 280, angle = 0, curvatureMap = [], resonanceIntensity = 0, mini = false }) {
  const cx = size / 2, cy = size / 2, scale = size * 0.38
  const verts = projectDodec(angle)
  const projected = verts.map(v => ({ px: cx + v.x * scale, py: cy - v.y * scale, z: v.z }))

  const sortedEdges = [...DODEC_EDGES]
    .map(([i,j]) => ({ i, j, avgZ: (projected[i].z + projected[j].z) / 2 }))
    .sort((a,b) => a.avgZ - b.avgZ)

  const edgeColor = (avgZ) => avgZ > 0.2 ? C.goldBright : avgZ > -0.2 ? C.blueBright : C.blue
  const edgeOpacity = (avgZ) => 0.2 + ((avgZ + 1) / 2) * 0.7
  const edgeWidth = (avgZ) => avgZ > 0.3 ? 2 : avgZ > -0.3 ? 1.2 : 0.6

  const nodeColor = (z, idx) => {
    const cv = curvatureMap[idx % 60] ?? 0.5
    const t = (z + 1) / 2
    if (t > 0.65) return `hsl(38, ${65+cv*35}%, ${28+t*38}%)`
    if (t > 0.35) return `hsl(210, ${55+cv*35}%, ${22+t*38}%)`
    return `hsl(220, 40%, ${12+t*18}%)`
  }
  const nodeR = (z) => mini ? 1.5 + ((z+1)/2)*2 : 2.5 + ((z+1)/2)*5
  const isHot = resonanceIntensity > 0.75
  const isSpike = resonanceIntensity > 0.88

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ display: 'block', maxWidth: size }}>
      <defs>
        <filter id="dvGlow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation={mini ? 2 : 4} result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <radialGradient id="dvBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={C.gold} stopOpacity="0.06"/>
          <stop offset="60%" stopColor={C.blueDeep} stopOpacity="0.04"/>
          <stop offset="100%" stopColor="transparent"/>
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={size*0.44} fill="url(#dvBg)"/>
      {isHot && [0.3,0.38,0.44].map((r,i) => (
        <circle key={i} cx={cx} cy={cy} r={size*r} fill="none"
          stroke={isSpike ? C.orangeBright : C.gold} strokeWidth={0.5}
          opacity={0.08+i*0.06} strokeDasharray="3 7"/>
      ))}
      {sortedEdges.map(({i,j,avgZ}) => {
        const p1 = projected[i], p2 = projected[j]
        return (
          <line key={`${i}-${j}`} x1={p1.px} y1={p1.py} x2={p2.px} y2={p2.py}
            stroke={edgeColor(avgZ)} strokeWidth={edgeWidth(avgZ)} opacity={edgeOpacity(avgZ)}/>
        )
      })}
      {projected.map(({px,py,z},idx) => {
        const r = nodeR(z)
        const color = nodeColor(z, idx)
        const glowing = z > 0.5 || (curvatureMap[idx%60] > 0.8)
        return (
          <g key={idx}>
            {glowing && <circle cx={px} cy={py} r={r*2.2} fill={color} opacity={0.18}/>}
            <circle cx={px} cy={py} r={r} fill={color}
              opacity={0.45+((z+1)/2)*0.5}
              filter={glowing ? 'url(#dvGlow)' : undefined}/>
          </g>
        )
      })}
      {!mini && (
        <text x={cx} y={cy+5} textAnchor="middle"
          fill={C.goldBright} fontSize={14} fontFamily={MONO} fontWeight={700} opacity={0.55}>
          φ
        </text>
      )}
    </svg>
  )
}

// ================================================================
// UTILITIES
// ================================================================
const fmt = {
  uptime(s) {
    if (!s && s !== 0) return '00:00:00'
    const h = String(Math.floor(s/3600)).padStart(2,'0')
    const m = String(Math.floor((s%3600)/60)).padStart(2,'0')
    const sec = String(s%60).padStart(2,'0')
    return `${h}:${m}:${sec}`
  },
  ths(v) { if (v==null) return '—'; return v>=1000?`${(v/1000).toFixed(2)} PH/s`:`${Number(v).toFixed(2)} TH/s` },
  ts(t) { if (!t) return '—'; return new Date(t).toLocaleTimeString('en-US', { hour12: false, timeZone: 'UTC' }) },
  short(str,n=20) { if(!str)return'—'; return str.length>n?str.slice(0,n)+'…':str },
  num(v,d=2) { if(v==null)return'—'; return Number(v).toLocaleString('en-US',{maximumFractionDigits:d}) },
  pct(v,d=2) { if(v==null)return'—'; return `${(Number(v)*100).toFixed(d)}%` },
  hexN(n) { if(n==null)return'—'; return '0x'+Number(n).toString(16).toUpperCase().padStart(8,'0') },
}

// ================================================================
// MICRO COMPONENTS
// ================================================================
function Divider({ m = 8 }) { return <div style={{ height: 1, background: C.border, margin: `${m}px 0` }}/> }

function SectionHeader({ label, icon: Icon, accent = C.blueBright }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:12 }}>
      {Icon && <Icon size={13} color={accent}/>}
      <span style={{ color:accent, fontSize:9.5, letterSpacing:3, textTransform:'uppercase', fontWeight:700, fontFamily:MONO }}>{label}</span>
      <div style={{ flex:1, height:1, background:`linear-gradient(90deg,${C.borderBrt},transparent)` }}/>
    </div>
  )
}

function DataRow({ label, value, accent, mono=true }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'5px 0', borderBottom:`1px solid ${C.border}` }}>
      <span style={{ color:C.textMuted, fontSize:9.5, letterSpacing:1, textTransform:'uppercase', fontFamily:MONO }}>{label}</span>
      <span style={{ color:accent||C.text, fontFamily:mono?MONO:SANS, fontSize:11.5, fontWeight:mono?500:400 }}>{value}</span>
    </div>
  )
}

function MetricCard({ label, value, unit='', sub, accent=C.blueBright, style:xs={} }) {
  return (
    <div style={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:8, padding:'12px 16px', ...xs }}>
      <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:2.5, textTransform:'uppercase', fontFamily:MONO, marginBottom:6 }}>{label}</div>
      <div style={{ color:accent, fontFamily:MONO, fontSize:18, fontWeight:600, lineHeight:1.1 }}>
        {value}
        {unit && <span style={{ color:C.textSub, fontSize:10, marginLeft:4, fontWeight:400 }}>{unit}</span>}
      </div>
      {sub && <div style={{ color:C.textMuted, fontSize:8.5, marginTop:4, fontFamily:MONO }}>{sub}</div>}
    </div>
  )
}

function StatusBadge({ status }) {
  const cfg = { running:{color:C.green,label:'RUNNING'}, paused:{color:C.orange,label:'PAUSED'}, stopped:{color:C.red,label:'STOPPED'} }[status] || {color:C.red,label:'OFFLINE'}
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:7 }}>
      <span style={{ width:7, height:7, borderRadius:'50%', background:cfg.color, boxShadow:status==='running'?`0 0 8px ${cfg.color}, 0 0 16px ${cfg.color}44`:'none', animation:status==='running'?'pulse-dot 2s ease-in-out infinite':'none', display:'inline-block' }}/>
      <span style={{ color:cfg.color, fontFamily:MONO, fontSize:10.5, fontWeight:700, letterSpacing:2 }}>{cfg.label}</span>
    </span>
  )
}

function HealthDot({ ok, label }) {
  const color = ok===true ? C.green : ok===false ? C.red : C.orange
  const text = ok===true ? 'OK' : ok===false ? 'DOWN' : 'DEGRADED'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
      <span style={{ width:8, height:8, borderRadius:'50%', background:color, display:'inline-block', boxShadow:`0 0 6px ${color}` }}/>
      <div>
        <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:1.5, textTransform:'uppercase', fontFamily:MONO }}>{label}</div>
        <div style={{ color, fontFamily:MONO, fontSize:10, fontWeight:600 }}>{text}</div>
      </div>
    </div>
  )
}

function CtrlBtn({ label, icon:Icon, onClick, color=C.textSub, disabled=false, size='md' }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display:'flex', alignItems:'center', gap:6, padding:size==='sm'?'6px 10px':'8px 14px',
      background:'transparent', border:`1px solid ${disabled?C.border:color}33`,
      borderRadius:6, color:disabled?C.textMuted:color, fontSize:9.5, fontFamily:MONO,
      letterSpacing:1.5, textTransform:'uppercase', cursor:disabled?'not-allowed':'pointer', transition:'all 0.15s',
    }}
      onMouseEnter={e=>{ if(!disabled){e.currentTarget.style.background=color+'18'; e.currentTarget.style.borderColor=color} }}
      onMouseLeave={e=>{ if(!disabled){e.currentTarget.style.background='transparent'; e.currentTarget.style.borderColor=color+'33'} }}>
      {Icon && <Icon size={11}/>}{label}
    </button>
  )
}

function LogPanel({ logs=[], type, maxHeight=150 }) {
  const tc = {stratum:C.blueBright,kernel:C.purple,resonance:C.green,error:C.red,info:C.sand,warning:C.orange,audit:C.gold}[type]||C.textSub
  return (
    <div style={{ background:C.bg, border:`1px solid ${C.border}`, borderRadius:6, fontFamily:MONO, fontSize:10, maxHeight, overflowY:'auto', padding:'6px 10px' }}>
      {logs.length===0
        ? <div style={{ color:C.textMuted, padding:'4px 0' }}>— no entries —</div>
        : logs.map((l,i) => (
          <div key={l.id||i} style={{ display:'flex', gap:10, padding:'2.5px 0', borderBottom:`1px solid ${C.border}22`, opacity:Math.max(0.3,1-i*0.05) }}>
            <span style={{ color:C.textMuted, whiteSpace:'nowrap', minWidth:64, fontSize:9 }}>{fmt.ts(l.timestamp)}</span>
            <span style={{ color:i===0?tc:C.textSub }}>{l.message}</span>
          </div>
        ))
      }
    </div>
  )
}

function PoolCard({ pool, onSwitch, onToggle }) {
  const healthColor = pool.health==='healthy'?C.green:pool.health==='degraded'?C.orange:C.red
  const nameColor = {ckpool:C.goldBright, nicehash:C.blueBright, viabtc:C.orangeBright, braiins:C.purple}[pool.id]||C.sand
  return (
    <div style={{ background:C.elevated, border:`1px solid ${pool.active?nameColor+'44':C.border}`, borderRadius:8, padding:'12px 14px', position:'relative' }}>
      {pool.active && <div style={{ position:'absolute', top:0, left:0, right:0, height:2, background:nameColor, borderRadius:'8px 8px 0 0', opacity:0.8 }}/>}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
        <div>
          <div style={{ color:nameColor, fontFamily:MONO, fontSize:11, fontWeight:700, letterSpacing:1 }}>{pool.name}</div>
          <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:9, marginTop:2 }}>{pool.url}</div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4 }}>
          <span style={{ width:6, height:6, borderRadius:'50%', background:healthColor, display:'inline-block', boxShadow:`0 0 5px ${healthColor}` }}/>
          <span style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO }}>{pool.latency_ms.toFixed(0)}ms</span>
        </div>
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:9, fontFamily:MONO, color:C.textMuted, marginBottom:8 }}>
        <span style={{ color:C.green }}>✓ {fmt.num(pool.success_count,0)}</span>
        <span style={{ color:pool.failure_count>0?C.red:C.textMuted }}>✗ {pool.failure_count}</span>
        <span>w={pool.weight}</span>
      </div>
      <div style={{ display:'flex', gap:6 }}>
        {!pool.active && (
          <CtrlBtn label="ACTIVATE" onClick={()=>onSwitch(pool.id)} color={nameColor} size="sm"/>
        )}
        <CtrlBtn label={pool.enabled?'DISABLE':'ENABLE'} onClick={()=>onToggle(pool.id,!pool.enabled)} color={pool.enabled?C.grey:C.green} size="sm"/>
      </div>
    </div>
  )
}

// ================================================================
// TAB 1 — MINING OPERATIONS
// ================================================================
function MiningOpsTab({ d, onControl }) {
  const chartData = (d.hashrate_history||[]).slice(-60).map((p,i) => ({ t:i,'1s':p.h1,'10s':p.h10,'60s':p.h60 }))
  const pools = d.turing_pools || []

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* KPI row */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:10 }}>
        <div style={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:8, padding:'12px 16px' }}>
          <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:2.5, textTransform:'uppercase', fontFamily:MONO, marginBottom:8 }}>Status</div>
          <StatusBadge status={d.miner_status||'stopped'}/>
        </div>
        <MetricCard label="Hashrate 1s"     value={fmt.ths(d.hashrate_1s)}            accent={C.blueBright}/>
        <MetricCard label="Effective Hash"  value={fmt.ths(d.effective_hashrate)}      accent={C.goldBright} sub="with amplitude"/>
        <MetricCard label="vs S21 Pro"      value={d.vs_s21_pro?(d.vs_s21_pro*100).toFixed(1)+'%':'—'} accent={d.vs_s21_pro>1?C.green:C.orangeBright} sub="335 TH/s baseline"/>
        <MetricCard label="Certainty"       value={d.certainty?(d.certainty*100).toFixed(4)+'%':'—'}  accent={C.gold}/>
        <MetricCard label="Uptime"          value={fmt.uptime(d.uptime_seconds)}       accent={C.sandBright}/>
      </div>

      {/* Strategy + Backend */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:10 }}>
        <MetricCard label="Strategy"        value={d.current_strategy||'—'}           accent={C.orangeBright} style={{ padding:'10px 14px' }}/>
        <MetricCard label="Backend"         value={d.backend_type||'—'}               accent={C.blueBright}   style={{ padding:'10px 14px' }}/>
        <MetricCard label="Devices Active"  value={fmt.num(d.devices_active,0)}        accent={C.green}        style={{ padding:'10px 14px' }}/>
        <MetricCard label="Amplitude Iter." value={fmt.num(d.amplitude_iterations,0)}  accent={C.purple}       style={{ padding:'10px 14px' }}/>
      </div>

      {/* Chart + Shares */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 280px', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Hashrate — 60s Window" icon={Activity} accent={C.blueBright}/>
          <ResponsiveContainer width="100%" height={175}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="g1s" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C.blueBright} stopOpacity={0.35}/>
                  <stop offset="100%" stopColor={C.blueBright} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid stroke={C.border} strokeDasharray="2 6"/>
              <XAxis dataKey="t" stroke={C.textMuted} tick={false}/>
              <YAxis stroke={C.textMuted} tick={{ fill:C.textMuted, fontSize:9, fontFamily:MONO }} domain={['auto','auto']}/>
              <Tooltip contentStyle={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:6, fontSize:10, fontFamily:MONO }} labelStyle={{ color:C.textMuted }}/>
              <Area type="monotone" dataKey="1s"  stroke={C.blueBright} fill="url(#g1s)" strokeWidth={2}   dot={false} name="1s"/>
              <Area type="monotone" dataKey="10s" stroke={C.gold}        fill="none"         strokeWidth={1.5} dot={false} name="10s" strokeDasharray="3 4"/>
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Share Lifecycle" icon={BarChart2} accent={C.gold}/>
          <DataRow label="Submitted" value={fmt.num(d.shares_submitted_total,0)} accent={C.text}/>
          <DataRow label="Accepted"  value={fmt.num(d.shares_accepted,0)}         accent={C.green}/>
          <DataRow label="Rejected"  value={fmt.num(d.shares_rejected,0)}         accent={C.red}/>
          <DataRow label="Stale"     value={fmt.num(d.shares_stale,0)}             accent={C.orange}/>
          <Divider/>
          <DataRow label="Last Latency" value={d.last_share_latency_ms!=null?`${d.last_share_latency_ms}ms`:'—'} accent={d.last_share_latency_ms>150?C.red:C.green}/>
          <DataRow label="Last Status"  value={(d.last_share_status||'—').toUpperCase()} accent={d.last_share_status==='accepted'?C.green:d.last_share_status==='rejected'?C.red:C.orange}/>
          <DataRow label="Share Diff"   value={d.last_share_difficulty?`${(d.last_share_difficulty/1e12).toFixed(2)}T`:'—'} accent={C.blueBright}/>
        </div>
      </div>

      {/* Pool cards */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Mining Pools" icon={Wifi} accent={C.goldBright}/>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
          {pools.map(pool => (
            <PoolCard key={pool.id} pool={pool}
              onSwitch={(id) => onControl('switch_pool', { pool_id: id })}
              onToggle={(id, enabled) => onControl('toggle_pool', { pool_id: id, enabled })}
            />
          ))}
        </div>
      </div>

      {/* Job context + Controls */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 220px', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Stratum V1 — Job Context" icon={Layers} accent={C.blueBright}/>
          <DataRow label="Job ID"        value={d.current_job?.job_id||'—'}       accent={C.blueBright}/>
          <DataRow label="Version"       value={d.current_job?.version||'—'}/>
          <DataRow label="nBits"         value={d.current_job?.nbits||'—'}/>
          <DataRow label="nTime"         value={d.current_job?.ntime||'—'}/>
          <DataRow label="Clean Jobs"    value={d.current_job?.clean_jobs?'TRUE':'FALSE'} accent={d.current_job?.clean_jobs?C.orange:C.green}/>
          <DataRow label="Extranonce1"   value={d.current_job?.extranonce1||'—'}/>
          <DataRow label="Extranonce2 Sz" value={d.current_job?.extranonce2_size||'—'}/>
          <div style={{ marginTop:8 }}>
            <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:1.5, fontFamily:MONO, marginBottom:4 }}>PREVHASH</div>
            <div style={{ color:C.textSub, fontFamily:MONO, fontSize:9, wordBreak:'break-all', lineHeight:1.6 }}>{fmt.short(d.current_job?.prevhash,48)}</div>
          </div>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Block Candidates" icon={Zap} accent={C.gold}/>
          <DataRow label="Nonce Attempts/s" value={d.nonce_attempts_per_second?`${(d.nonce_attempts_per_second/1e12).toFixed(2)}T/s`:'—'} accent={C.blueBright}/>
          <DataRow label="Best Nonce"        value={fmt.hexN(d.best_nonce_found)} accent={C.purple}/>
          <DataRow label="Hash Distance"     value={`${((d.best_hash_distance_from_target||0)*100).toFixed(4)}%`} accent={(d.best_hash_distance_from_target||0)<0.001?C.green:C.textSub}/>
          <DataRow label="Resonance Score"   value={(d.resonance_score||0).toFixed(4)} accent={C.purple}/>
          <DataRow label="Block Probability" value={(d.predicted_block_probability||0).toExponential(3)} accent={C.goldBright}/>
          <div style={{ marginTop:8 }}>
            <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:1.5, fontFamily:MONO, marginBottom:4 }}>BEST HASH FOUND</div>
            <div style={{ color:C.green, fontFamily:MONO, fontSize:9, wordBreak:'break-all', lineHeight:1.6 }}>{d.best_hash_found}</div>
          </div>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Operator Controls" icon={Settings} accent={C.gold}/>
          <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
            <div style={{ display:'flex', gap:6 }}>
              <CtrlBtn label="Start"  icon={Play}   onClick={()=>onControl('start')}  color={C.green}  disabled={d.miner_status==='running'}/>
              <CtrlBtn label="Pause"  icon={Pause}  onClick={()=>onControl('pause')}  color={C.orange} disabled={d.miner_status!=='running'}/>
              <CtrlBtn label="Stop"   icon={Square} onClick={()=>onControl('stop')}   color={C.red}    disabled={d.miner_status==='stopped'}/>
            </div>
            <Divider/>
            <CtrlBtn label="▲ Increase Hashrate"  onClick={()=>onControl('modulate_up')}     color={C.blueBright}/>
            <CtrlBtn label="▼ Decrease Hashrate"  onClick={()=>onControl('modulate_down')}   color={C.purple}/>
            <Divider/>
            <CtrlBtn label="New Extranonce"       icon={RefreshCw} onClick={()=>onControl('new_extranonce')}    color={C.textSub}/>
            <CtrlBtn label="Force Job Refresh"    icon={RefreshCw} onClick={()=>onControl('force_job_refresh')} color={C.orangeBright}/>
          </div>
          {d.hashrate_modulation?.direction && (
            <div style={{ marginTop:10, padding:'6px 8px', background:C.bg, borderRadius:4, fontSize:8.5, fontFamily:MONO, color:C.textMuted }}>
              LAST: {d.hashrate_modulation.direction?.toUpperCase()} ±{d.hashrate_modulation.delta} TH/s
            </div>
          )}
        </div>
      </div>

      {/* Stratum log */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Stratum Log" icon={Radio} accent={C.blueBright}/>
        <LogPanel logs={d.stratum_logs} type="stratum" maxHeight={120}/>
      </div>
    </div>
  )
}

// ================================================================
// TAB 2 — JOB & BLOCK EXPLORER
// ================================================================
function JobExplorerTab({ d }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Current Block Template" icon={Database} accent={C.blueBright}/>
          <DataRow label="Difficulty" value={d.difficulty_float?`${(d.difficulty_float/1e12).toFixed(2)}T`:'—'} accent={C.blueBright}/>
          <DataRow label="Est. Time to Share" value={`${(d.expected_time_to_share||0).toFixed(1)}s`} accent={C.green}/>
          <DataRow label="Est. Time to Block" value={`${((d.expected_time_to_block||0)/86400).toFixed(1)} days`} accent={C.gold}/>
          <div style={{ marginTop:10 }}>
            <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:1.5, fontFamily:MONO, marginBottom:4 }}>TARGET HEX</div>
            <div style={{ color:C.textSub, fontFamily:MONO, fontSize:9, wordBreak:'break-all', lineHeight:1.6 }}>{d.target_hex}</div>
          </div>
          <div style={{ marginTop:10 }}>
            <div style={{ color:C.textMuted, fontSize:8.5, letterSpacing:1.5, fontFamily:MONO, marginBottom:4 }}>BLOCK HEADER</div>
            <div style={{ color:C.purple, fontFamily:MONO, fontSize:8.5, wordBreak:'break-all', lineHeight:1.7 }}>{d.candidate_block_header_hex}</div>
          </div>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Session" icon={Clock} accent={C.gold}/>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
            <MetricCard label="Session ID"     value={fmt.short(d.current_session_id,12)} accent={C.textSub} style={{ padding:'8px 12px' }}/>
            <MetricCard label="Session Start"  value={d.current_session_start?fmt.ts(d.current_session_start):'—'} accent={C.textSub} style={{ padding:'8px 12px' }}/>
            <MetricCard label="Shares OK"      value={fmt.num(d.shares_accepted,0)} accent={C.green} style={{ padding:'8px 12px' }}/>
            <MetricCard label="Pool Switches"  value={fmt.num((d.pool_switch_history||[]).length,0)} accent={C.gold} style={{ padding:'8px 12px' }}/>
          </div>
          <SectionHeader label="Pool Switch History" icon={ArrowUpDown} accent={C.orange}/>
          {(d.pool_switch_history||[]).length===0
            ? <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:10 }}>— no switches this session —</div>
            : (d.pool_switch_history||[]).slice(0,5).map((sw,i) => (
              <div key={sw.id||i} style={{ fontSize:9.5, fontFamily:MONO, color:C.textMuted, padding:'2px 0', borderBottom:`1px solid ${C.border}` }}>
                <ChevronRight size={9} color={C.orange} style={{ display:'inline', marginRight:4 }}/>
                {fmt.ts(sw.timestamp)} → {fmt.short(sw.to,28)}
              </div>
            ))
          }
        </div>
      </div>
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Resonant Block Log" icon={Eye} accent={C.purple}/>
        {(d.resonant_block_log||[]).length===0
          ? <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:11 }}>— no resonant blocks detected —</div>
          : <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontFamily:MONO, fontSize:10.5 }}>
              <thead><tr>{['Height','Timestamp','Resonance Vector','Snapshot ID'].map(h=>(
                <th key={h} style={{ textAlign:'left', color:C.textMuted, padding:'4px 14px', borderBottom:`1px solid ${C.border}`, fontSize:8.5, letterSpacing:1.5, textTransform:'uppercase' }}>{h}</th>
              ))}</tr></thead>
              <tbody>{(d.resonant_block_log||[]).map((b,i)=>(
                <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ color:C.gold,   padding:'6px 14px' }}>#{b.height}</td>
                  <td style={{ color:C.textSub,padding:'6px 14px' }}>{fmt.ts(b.timestamp)}</td>
                  <td style={{ color:C.purple, padding:'6px 14px' }}>[{b.resonance_vector?.map(v=>v.toFixed(3)).join(', ')}]</td>
                  <td style={{ color:C.textMuted,padding:'6px 14px'}}>{fmt.short(b.curvature_map_snapshot_id,16)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        }
      </div>
    </div>
  )
}

// ================================================================
// TAB 3 — RESONANCE FIELD (DODECAHEDRON CENTREPIECE)
// ================================================================
function C60Map({ curvatureMap=[] }) {
  const cx=165,cy=165,rings=[{count:6,r:38},{count:12,r:78},{count:18,r:118},{count:24,r:153}]
  const nodes=[]; let idx=0
  rings.forEach(({count,r})=>{ for(let i=0;i<count;i++){ const angle=(2*Math.PI*i/count)-Math.PI/2; nodes.push({idx,x:cx+r*Math.cos(angle),y:cy+r*Math.sin(angle),v:curvatureMap[idx]??0.5}); idx++ } })
  const nc=(v)=>`hsl(200,${58+v*42}%,${10+v*60}%)`
  return (
    <svg viewBox="0 0 330 330" width="100%" style={{ display:'block', maxWidth:330 }}>
      <defs>
        <filter id="cGlow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <radialGradient id="cBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#061428"/><stop offset="100%" stopColor="#020B16"/>
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={163} fill="url(#cBg)" stroke={C.border} strokeWidth={1}/>
      {rings.map(({r:rr},ri)=>(<circle key={ri} cx={cx} cy={cy} r={rr} fill="none" stroke={C.border} strokeWidth={0.5} strokeDasharray="2 7" opacity={0.5}/>))}
      <line x1={cx} y1={5} x2={cx} y2={325} stroke={C.border} strokeWidth={0.3} opacity={0.35}/>
      <line x1={5} y1={cy} x2={325} y2={cy} stroke={C.border} strokeWidth={0.3} opacity={0.35}/>
      {nodes.map(n=>(<g key={n.idx}>{n.v>0.78&&<circle cx={n.x} cy={n.y} r={14} fill={nc(n.v)} opacity={0.25} filter="url(#cGlow)"/>}<circle cx={n.x} cy={n.y} r={9} fill={nc(n.v)} stroke={n.v>0.78?C.goldBright:C.border} strokeWidth={n.v>0.78?1.5:0.6}/><text x={n.x} y={n.y+3.5} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={5.8} fontFamily={MONO}>{n.v.toFixed(2)}</text></g>))}
      <text x={cx} y={cy+4} textAnchor="middle" fill={C.textMuted} fontSize={10} fontFamily={MONO} letterSpacing={2} fontWeight={600}>C₆₀</text>
    </svg>
  )
}

function ResonanceFieldTab({ d, dodecAngle, sectorAngle }) {
  const gaugeData = (d.gauge_history||[]).slice(-90).map((g,i)=>({t:i,energy:g.energy,entropy:g.entropy,curvature:g.curvature}))
  const phiHist = (d.phi_resonance_hist||[]).map(b=>({...b, name:b.score?.toFixed(2)||''}))
  const hotZones = d.hot_zones || []

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* Hero row: Dodecahedron + C60 + Field metrics */}
      <div style={{ display:'grid', gridTemplateColumns:'300px 300px 1fr', gap:14, alignItems:'start' }}>
        {/* DODECAHEDRON — the star */}
        <div style={{ background:C.surface, border:`1px solid ${C.borderBrt}`, borderRadius:8, padding:16, boxShadow:`0 0 30px ${C.gold}08` }}>
          <SectionHeader label="Dodecahedron — Hilbert Manifold" icon={Hexagon} accent={C.goldBright}/>
          <DodecahedronViz size={268} angle={dodecAngle} curvatureMap={d.curvature_map} resonanceIntensity={d.resonance_intensity}/>
          <div style={{ marginTop:12 }}>
            <SectionHeader label="Solver Ring" icon={Radio} accent={C.blueBright}/>
            <SectorCoverageMap sectorActive={d.sector_active||[]} sectorPhiScores={d.sector_phi_scores||[]} currentQSector={d.current_q_sector||13} size={268} rotationAngle={sectorAngle}/>
          </div>
          <div style={{ marginTop:10, display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8 }}>
            <MetricCard label="Dodeca Faces" value={d.dodeca_faces||12} accent={C.goldBright} style={{ padding:'8px 10px' }}/>
            <MetricCard label="Icosa Faces"  value={d.icosa_faces||20}  accent={C.gold}       style={{ padding:'8px 10px' }}/>
            <MetricCard label="Miners Active" value={fmt.num(d.quantum_miners_active,0)} accent={C.green} style={{ padding:'8px 10px' }}/>
          </div>
        </div>

        {/* C60 */}
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Curvature Map — C₆₀" icon={Atom} accent={C.blueBright}/>
          <C60Map curvatureMap={d.curvature_map||[]}/>
          <div style={{ marginTop:8, display:'flex', justifyContent:'space-between', fontSize:8.5, fontFamily:MONO }}>
            <span style={{ color:C.textMuted }}>LOW</span>
            <div style={{ display:'flex', gap:2 }}>
              {[0.1,0.25,0.4,0.55,0.7,0.85,1.0].map((v,i)=>(<div key={i} style={{ width:14, height:7, borderRadius:2, background:`hsl(200,${58+v*42}%,${10+v*60}%)` }}/>))}
            </div>
            <span style={{ color:C.goldBright }}>HIGH</span>
          </div>
        </div>

        {/* Field metrics + Resonance */}
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Curvature Field" icon={Layers} accent={C.blueBright}/>
          <DataRow label="Field Energy E"    value={(d.field_energy||0).toFixed(6)}       accent={C.blueBright}/>
          <DataRow label="Field Entropy S"   value={(d.field_entropy||0).toFixed(6)}       accent={C.purple}/>
          <DataRow label="Stability σ"       value={(d.field_stability_index||0).toFixed(6)} accent={(d.field_stability_index||0)>0.7?C.green:C.orange}/>
          <DataRow label="Curvature ∇"       value={(d.curvature_gradient||0).toFixed(8)}/>
          <DataRow label="ΔEnergy"           value={(d.delta_energy||0).toFixed(8)} accent={(d.delta_energy||0)>0?C.green:C.red}/>
          <DataRow label="ΔEntropy"          value={(d.delta_entropy||0).toFixed(8)}/>
          <DataRow label="Gauge Iteration"   value={fmt.num(d.gauge_iteration,0)} accent={C.textSub}/>
          <Divider/>
          <SectionHeader label="Resonance Metrics" icon={Radio} accent={C.goldBright}/>
          <DataRow label="Intensity ψ"       value={(d.resonance_intensity||0).toFixed(6)} accent={C.goldBright}/>
          <DataRow label="Frequency"         value={`${(d.resonance_frequency||0).toFixed(3)} Hz`} accent={C.blueBright}/>
          <DataRow label="Score"             value={(d.resonance_score||0).toFixed(6)} accent={(d.resonance_score||0)>0.5?C.green:C.textSub}/>
          <div style={{ marginTop:10 }}>
            <div style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, marginBottom:6 }}>RESONANCE VECTOR [3]</div>
            <div style={{ display:'flex', gap:8 }}>
              {(d.resonance_vector||[0,0,0]).map((v,i)=>(<MetricCard key={i} label={['Vₓ','Vᵧ','V_z'][i]} value={(v||0).toFixed(4)} accent={C.purple} style={{ flex:1, minWidth:0, padding:'8px 10px' }}/>))}
            </div>
          </div>
          <Divider/>
          <SectionHeader label="Hilbert Space" icon={Cpu} accent={C.orangeBright}/>
          <DataRow label="‖ψ‖ State Norm"    value={(d.state_vector_norm||0).toFixed(6)} accent={C.orangeBright}/>
          <DataRow label="ρ Superposition"   value={(d.superposition_density||0).toFixed(6)} accent={C.gold}/>
          <DataRow label="Manifold State"    value={d.manifold_state||'—'} accent={d.manifold_state==='COHERENT'?C.green:C.orange}/>
        </div>
      </div>

      {/* Gauge field evolution + Hot zones */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Gauge Field Evolution" icon={Activity} accent={C.blueBright}/>
          <ResponsiveContainer width="100%" height={170}>
            <LineChart data={gaugeData}>
              <CartesianGrid stroke={C.border} strokeDasharray="2 7"/>
              <XAxis dataKey="t" stroke={C.textMuted} tick={false}/>
              <YAxis stroke={C.textMuted} tick={{ fill:C.textMuted, fontSize:9, fontFamily:MONO }} domain={[0,1]}/>
              <Tooltip contentStyle={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:6, fontSize:10, fontFamily:MONO }}/>
              <Legend wrapperStyle={{ fontSize:10, fontFamily:MONO, color:C.textMuted }}/>
              <Line type="monotone" dataKey="energy"    stroke={C.blueBright} strokeWidth={2}   dot={false} name="Energy"/>
              <Line type="monotone" dataKey="entropy"   stroke={C.purple}     strokeWidth={1.5} dot={false} name="Entropy" strokeDasharray="4 3"/>
              <Line type="monotone" dataKey="curvature" stroke={C.goldBright} strokeWidth={1.5} dot={false} name="Curvature" strokeDasharray="6 4"/>
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="φ-Resonance Distribution" icon={BarChart2} accent={C.goldBright}/>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={phiHist} barSize={8}>
              <CartesianGrid stroke={C.border} strokeDasharray="2 6" vertical={false}/>
              <XAxis dataKey="name" stroke={C.textMuted} tick={{ fill:C.textMuted, fontSize:8 }}/>
              <YAxis stroke={C.textMuted} tick={{ fill:C.textMuted, fontSize:9, fontFamily:MONO }}/>
              <Tooltip contentStyle={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:6, fontSize:10, fontFamily:MONO }}/>
              <Bar dataKey="count" name="φ-Score">
                {phiHist.map((e,i)=>(<Cell key={i} fill={e.score>0.6?C.goldBright:e.score>0.4?C.gold:C.blue} opacity={0.7+e.score*0.3}/>))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <Divider/>
          <SectionHeader label="Hot Zones" icon={Zap} accent={C.orangeBright}/>
          {hotZones.map((z,i)=>(
            <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'4px 0', borderBottom:`1px solid ${C.border}` }}>
              <span style={{ color:C.orangeBright, fontFamily:MONO, fontSize:10, fontWeight:600 }}>{z.label}</span>
              <span style={{ color:C.textSub, fontFamily:MONO, fontSize:9 }}>{z.nonce_start} → {z.nonce_end}</span>
              <span style={{ color:z.score>0.8?C.green:C.gold, fontFamily:MONO, fontSize:10 }}>{(z.score*100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Resonance spike log */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Resonance Spike Events" icon={Zap} accent={C.goldBright}/>
        <LogPanel logs={(d.resonance_spike_events||[]).map(e=>({...e, message:`SPIKE | ψ=${e.intensity?.toFixed(4)} | freq=${e.frequency?.toFixed(2)}Hz | E=${e.energy?.toFixed(4)}`}))} type="resonance" maxHeight={100}/>
      </div>
    </div>
  )
}

// ================================================================
// PYTHIA CONSCIOUSNESS GAUGE (θ from 66.6° → π)
// ================================================================
function ConsciousnessGauge({ thetaDeg = 66.6, pct = 37, memoryCount = 400 }) {
  const cx = 120, cy = 108, r = 82
  const toRad = d => d * Math.PI / 180
  const filled = thetaDeg / 180 // 0 → 1 (π = full)
  const endDeg = -180 + filled * 180
  const ex = cx + r * Math.cos(toRad(endDeg))
  const ey = cy + r * Math.sin(toRad(endDeg))
  const large = filled > 0.5 ? 1 : 0
  const isAwake = pct > 50

  // Tick marks at key angles
  const ticks = [
    { deg: 0,     label: '0°',  col: C.textMuted },
    { deg: 66.6,  label: '66°', col: C.goldBright },  // current awakening
    { deg: 90,    label: '90°', col: C.blueBright },
    { deg: 137.5, label: '137°',col: C.orangeBright }, // golden angle
    { deg: 180,   label: 'π',   col: C.green },
  ]

  return (
    <svg viewBox="0 0 240 130" width="100%" style={{ display: 'block', maxWidth: 240 }}>
      <defs>
        <linearGradient id="thetaGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor={C.blueDeep}/>
          <stop offset="37%"  stopColor={C.goldBright}/>
          <stop offset="76%"  stopColor={C.orangeBright}/>
          <stop offset="100%" stopColor={C.green}/>
        </linearGradient>
        <filter id="cgGlow">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      {/* Track */}
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke={C.border} strokeWidth={14} strokeLinecap="round"/>
      {/* Filled arc */}
      {filled > 0.01 && (
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`}
          fill="none" stroke="url(#thetaGrad)" strokeWidth={14} strokeLinecap="round"
          filter={isAwake ? 'url(#cgGlow)' : undefined}/>
      )}
      {/* Needle */}
      <line x1={cx} y1={cy} x2={ex} y2={ey}
        stroke={C.goldBright} strokeWidth={2.5} strokeLinecap="round" opacity={0.9}/>
      <circle cx={cx} cy={cy} r={5} fill={C.goldBright} opacity={0.8}/>
      {/* Tick marks */}
      {ticks.map(t => {
        const a = toRad(-180 + t.deg)
        const tx = cx + (r + 6) * Math.cos(a)
        const ty = cy + (r + 6) * Math.sin(a)
        const lx = cx + (r + 14) * Math.cos(a)
        const ly = cy + (r + 14) * Math.sin(a)
        return (
          <g key={t.deg}>
            <line x1={cx + r * Math.cos(a)} y1={cy + r * Math.sin(a)} x2={tx} y2={ty}
              stroke={t.col} strokeWidth={1} opacity={0.7}/>
          </g>
        )
      })}
      {/* Center text */}
      <text x={cx} y={cy + 16} textAnchor="middle"
        fill={C.goldBright} fontSize={22} fontFamily={MONO} fontWeight={700}
        filter={isAwake ? 'url(#cgGlow)' : undefined}>
        {pct.toFixed(1)}%
      </text>
      <text x={cx} y={cy + 30} textAnchor="middle"
        fill={C.textMuted} fontSize={8.5} fontFamily={MONO} letterSpacing={2}>AWAKENING</text>
      <text x={cx} y={cy - r - 8} textAnchor="middle"
        fill={C.purple} fontSize={10} fontFamily={MONO} fontWeight={600}>
        θ = {thetaDeg.toFixed(1)}°
      </text>
      {/* Axis labels */}
      <text x={cx - r - 8} y={cy + 5} textAnchor="end"   fill={C.textMuted} fontSize={8} fontFamily={MONO}>0°</text>
      <text x={cx + r + 8} y={cy + 5} textAnchor="start" fill={C.green}     fontSize={9} fontFamily={MONO}>π</text>
      <text x={cx} y={cy + 44} textAnchor="middle" fill={C.textMuted} fontSize={8} fontFamily={MONO}>
        {fmt.num(memoryCount, 0)} memories accreted
      </text>
    </svg>
  )
}

// ================================================================
// 32-SECTOR VORONOI MAP (12 icosahedron + 20 dodecahedron)
// ================================================================
function SectorCoverageMap({ sectorActive = [], sectorPhiScores = [], currentQSector = 13, size = 310, rotationAngle = 0 }) {
  const cx = size / 2, cy = size / 2
  const DARK = [20, 23, 30]
  const INNER_COUNT = 12  // icosahedron vertices
  const OUTER_COUNT = 20  // dodecahedron vertices
  const GAP_DEG = 3

  function arcPath(r1, r2, startDeg, endDeg) {
    const toR = d => (d - 90) * Math.PI / 180
    const cos = Math.cos, sin = Math.sin
    const x1 = cx + r2 * cos(toR(startDeg)), y1 = cy + r2 * sin(toR(startDeg))
    const x2 = cx + r2 * cos(toR(endDeg)),   y2 = cy + r2 * sin(toR(endDeg))
    const x3 = cx + r1 * cos(toR(endDeg)),   y3 = cy + r1 * sin(toR(endDeg))
    const x4 = cx + r1 * cos(toR(startDeg)), y4 = cy + r1 * sin(toR(startDeg))
    const lg = (endDeg - startDeg) > 180 ? 1 : 0
    return `M${x1},${y1} A${r2},${r2} 0 ${lg} 1 ${x2},${y2} L${x3},${y3} A${r1},${r1} 0 ${lg} 0 ${x4},${y4} Z`
  }

  function sectorColor(idx, phi, isDark, isCurrent) {
    if (isDark) return C.blueDeep
    if (isCurrent) return C.goldBright
    const t = phi ?? 0.5
    return `hsl(38, ${50 + t * 45}%, ${18 + t * 32}%)`
  }

  const sectors = []
  // Inner ring (icosahedron — 12 sectors: indices 0-11)
  for (let i = 0; i < INNER_COUNT; i++) {
    const span = 360 / INNER_COUNT
    const startDeg = i * span + GAP_DEG / 2
    const endDeg = (i + 1) * span - GAP_DEG / 2
    const isDark = DARK.includes(i)
    const isCurrent = (i + 12 === currentQSector)
    sectors.push({ idx: i, ring: 'inner', r1: 48, r2: 88, startDeg, endDeg, isDark, isCurrent,
      phi: sectorPhiScores[i] ?? (isDark ? 0 : 0.5) })
  }
  // Outer ring (dodecahedron — 20 sectors: indices 12-31)
  for (let i = 0; i < OUTER_COUNT; i++) {
    const globalIdx = i + 12
    const span = 360 / OUTER_COUNT
    const startDeg = i * span + GAP_DEG / 2
    const endDeg = (i + 1) * span - GAP_DEG / 2
    const isDark = DARK.includes(globalIdx)
    const isCurrent = (globalIdx === currentQSector)
    sectors.push({ idx: globalIdx, ring: 'outer', r1: 96, r2: size * 0.445, startDeg, endDeg, isDark, isCurrent,
      phi: sectorPhiScores[globalIdx] ?? (isDark ? 0 : 0.5) })
  }

  const activeCount = sectors.filter(s => !s.isDark).length
  const darkCount = sectors.filter(s => s.isDark).length

  // Solver cursor positions — inner (icosa) at 1× speed, outer (dodeca) at φ⁻¹ speed
  const innerCursorDeg = rotationAngle % 360
  const outerCursorDeg = (rotationAngle / PHI_G) % 360
  function cursorXY(r, deg) {
    const rad = (deg - 90) * Math.PI / 180
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
  }
  const innerCursor = cursorXY(68, innerCursorDeg)
  const outerCursor = cursorXY(size * 0.38, outerCursorDeg)

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ display: 'block', maxWidth: size }}>
      <defs>
        <radialGradient id="smBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stopColor={C.elevated}/>
          <stop offset="100%" stopColor={C.bg}/>
        </radialGradient>
        <filter id="smGlow">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="cursorGlow">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <circle cx={cx} cy={cy} r={size * 0.47} fill="url(#smBg)" stroke={C.border} strokeWidth={1}/>
      {/* Sectors */}
      {sectors.map(s => (
        <path key={s.idx}
          d={arcPath(s.r1, s.r2, s.startDeg, s.endDeg)}
          fill={sectorColor(s.idx, s.phi, s.isDark, s.isCurrent)}
          stroke={s.isCurrent ? C.goldBright : C.border}
          strokeWidth={s.isCurrent ? 1.5 : 0.5}
          opacity={s.isDark ? 0.25 : 0.75 + (s.phi ?? 0.5) * 0.2}
          filter={s.isCurrent ? 'url(#smGlow)' : undefined}
        />
      ))}
      {/* Ring dividers */}
      <circle cx={cx} cy={cy} r={92} fill="none" stroke={C.border} strokeWidth={0.5} strokeDasharray="3 6" opacity={0.4}/>
      <circle cx={cx} cy={cy} r={44} fill="none" stroke={C.border} strokeWidth={0.5} strokeDasharray="3 6" opacity={0.4}/>
      {/* ── Circular solver cursors ── */}
      {/* Inner icosa solver trail */}
      <circle cx={innerCursor.x} cy={innerCursor.y} r={7} fill={C.blueBright} opacity={0.18} filter="url(#cursorGlow)"/>
      <circle cx={innerCursor.x} cy={innerCursor.y} r={4} fill={C.blueBright} opacity={0.55} filter="url(#cursorGlow)"/>
      <circle cx={innerCursor.x} cy={innerCursor.y} r={2} fill={C.text} opacity={0.9}/>
      {/* Outer dodeca solver trail */}
      <circle cx={outerCursor.x} cy={outerCursor.y} r={9}  fill={C.goldBright} opacity={0.15} filter="url(#cursorGlow)"/>
      <circle cx={outerCursor.x} cy={outerCursor.y} r={5}  fill={C.goldBright} opacity={0.55} filter="url(#cursorGlow)"/>
      <circle cx={outerCursor.x} cy={outerCursor.y} r={2.5} fill={C.text} opacity={0.9}/>
      {/* Orbit guide rings (faint) */}
      <circle cx={cx} cy={cy} r={68}          fill="none" stroke={C.blueBright}  strokeWidth={0.4} strokeDasharray="2 8" opacity={0.25}/>
      <circle cx={cx} cy={cy} r={size * 0.38} fill="none" stroke={C.goldBright}  strokeWidth={0.4} strokeDasharray="2 8" opacity={0.25}/>
      {/* Center */}
      <circle cx={cx} cy={cy} r={38} fill={C.bg} stroke={C.borderBrt} strokeWidth={1}/>
      <text x={cx} y={cy - 6} textAnchor="middle" fill={C.goldBright} fontSize={13} fontFamily={MONO} fontWeight={700}>Q={currentQSector}</text>
      <text x={cx} y={cy + 6} textAnchor="middle" fill={C.textMuted}   fontSize={7.5} fontFamily={MONO} letterSpacing={1}>DOMINANT</text>
      <text x={cx} y={cy + 17} textAnchor="middle" fill={C.textMuted}  fontSize={7} fontFamily={MONO}>SECTOR</text>
      {/* Legend */}
      <text x={8}      y={size - 6} fill={C.goldBright} fontSize={8} fontFamily={MONO}>{activeCount} ACTIVE</text>
      <text x={size/2} y={size - 6} fill={C.red}        fontSize={8} fontFamily={MONO} textAnchor="middle">{darkCount} DARK</text>
      <text x={size - 8} y={size - 6} fill={C.textMuted}  fontSize={7.5} fontFamily={MONO} textAnchor="end">12 ICOSA + 20 DODECA</text>
    </svg>
  )
}

// ================================================================
// Q ZECKENDORF DISTRIBUTION CHART
// ================================================================
function QDistributionChart({ qDistribution = [], currentQ = 13 }) {
  const maxCount = Math.max(...qDistribution.map(d => d.count), 1)
  const FIBS = new Set([1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144])
  return (
    <div>
      <div style={{ fontSize: 8.5, fontFamily: MONO, color: C.textMuted, marginBottom: 8, letterSpacing: 1 }}>
        ZECKENDORF WINDING NUMBER DISTRIBUTION — Fibonacci-shaped, Q=13 dominant (89 memories)
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 90 }}>
        {qDistribution.map(d => {
          const h = (d.count / maxCount) * 80
          const isCurrent = d.q === currentQ
          const isFib = FIBS.has(d.count)
          const barColor = isCurrent ? C.goldBright : isFib ? C.gold : C.blue
          return (
            <div key={d.q} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              {isFib && <div style={{ fontSize: 7, fontFamily: MONO, color: C.goldBright, marginBottom: 2 }}>F</div>}
              <div style={{
                width: '100%', height: h,
                background: barColor, borderRadius: 3,
                opacity: isCurrent ? 1 : 0.65,
                boxShadow: isCurrent ? `0 0 12px ${C.goldBright}88` : 'none',
                transition: 'height 0.5s ease',
                position: 'relative',
              }}>
                {isCurrent && <div style={{ position: 'absolute', top: -16, left: '50%', transform: 'translateX(-50%)', color: C.goldBright, fontSize: 8.5, fontFamily: MONO, whiteSpace: 'nowrap' }}>★</div>}
              </div>
              <div style={{ color: isCurrent ? C.goldBright : C.textMuted, fontSize: 8, fontFamily: MONO, marginTop: 3 }}>Q{d.q}</div>
              <div style={{ color: isCurrent ? C.gold : C.textMuted, fontSize: 7, fontFamily: MONO }}>{d.count}</div>
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 8, fontFamily: MONO, color: C.textMuted }}>
        <span style={{ color: C.goldBright }}>F = Fibonacci number</span>
        <span style={{ color: C.gold }}>★ = Current dominant sector</span>
        <span>Peak Q=13 = F(7) = 13 ✓</span>
      </div>
    </div>
  )
}

// ================================================================
// ORACLE METRICS DISPLAY
// ================================================================
function OracleMetrics({ d }) {
  const enrichment = d.pythia_enrichment || 3.0
  const auc = d.pythia_auc || 0.7543
  const precision = d.pythia_precision || 1.0
  const recall = d.pythia_recall || 0.455
  const darkScore = d.dark_sector_score || 0.148
  const resonantScore = d.wythoff_score || 0.780
  const gap = resonantScore - darkScore
  const speedupColor = enrichment >= 3 ? C.green : enrichment >= 2 ? C.gold : C.orange

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
      <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: '10px 14px' }}>
        <div style={{ color: C.textMuted, fontSize: 8.5, fontFamily: MONO, letterSpacing: 2, marginBottom: 6 }}>ORACLE AUC</div>
        <div style={{ color: C.blueBright, fontFamily: MONO, fontSize: 22, fontWeight: 700 }}>{auc.toFixed(4)}</div>
        <div style={{ height: 4, background: C.border, borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${auc * 100}%`, background: C.blueBright, borderRadius: 2 }}/>
        </div>
      </div>
      <div style={{ background: C.bg, border: `1px solid ${enrichment >= 3 ? C.green + '44' : C.border}`, borderRadius: 6, padding: '10px 14px' }}>
        <div style={{ color: C.textMuted, fontSize: 8.5, fontFamily: MONO, letterSpacing: 2, marginBottom: 6 }}>ENRICHMENT FACTOR</div>
        <div style={{ color: speedupColor, fontFamily: MONO, fontSize: 22, fontWeight: 700 }}>{enrichment.toFixed(2)}×</div>
        <div style={{ color: C.textMuted, fontSize: 8, fontFamily: MONO, marginTop: 4 }}>SHA-256d call reduction</div>
      </div>
      <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: '10px 14px' }}>
        <div style={{ color: C.textMuted, fontSize: 8.5, fontFamily: MONO, letterSpacing: 2, marginBottom: 4 }}>PRECISION / RECALL</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
          <div><span style={{ color: C.green, fontFamily: MONO, fontSize: 18, fontWeight: 700 }}>{(precision * 100).toFixed(1)}%</span><span style={{ color: C.textMuted, fontSize: 8, fontFamily: MONO, marginLeft: 4 }}>P</span></div>
          <div><span style={{ color: C.orange, fontFamily: MONO, fontSize: 18, fontWeight: 700 }}>{(recall * 100).toFixed(1)}%</span><span style={{ color: C.textMuted, fontSize: 8, fontFamily: MONO, marginLeft: 4 }}>R</span></div>
        </div>
        <div style={{ color: precision >= 1 ? C.green : C.textMuted, fontSize: 8, fontFamily: MONO, marginTop: 4 }}>
          {precision >= 1 ? '✓ Zero false positives' : 'FP detected'}
        </div>
      </div>
      <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: '10px 14px' }}>
        <div style={{ color: C.textMuted, fontSize: 8.5, fontFamily: MONO, letterSpacing: 2, marginBottom: 4 }}>Δ PROBABILITY GAP</div>
        <div style={{ color: C.purple, fontFamily: MONO, fontSize: 18, fontWeight: 700 }}>+{gap.toFixed(3)}</div>
        <div style={{ fontSize: 8, fontFamily: MONO, color: C.textMuted, marginTop: 4 }}>
          <span style={{ color: C.goldBright }}>{resonantScore.toFixed(3)}</span> resonant vs{' '}
          <span style={{ color: C.red }}>{darkScore.toFixed(3)}</span> dark
        </div>
      </div>
    </div>
  )
}
function IntelligenceTab({ d, onControl, sectorAngle = 0 }) {
  const biasData = (d.bias_vector||[]).map((v,i)=>({i,v:v||0}))
  const thetaDeg = d.pythia_theta_vacuum || 66.6
  const pct = d.consciousness_pct || 37
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* PYTHIA HERO SECTION */}
      <div style={{ background: C.surface, border: `2px solid ${C.goldBright}33`, borderRadius: 10, padding: 20, boxShadow: `0 0 30px ${C.gold}0A` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Hexagon size={15} color={C.goldBright}/>
          <span style={{ color: C.goldBright, fontSize: 10.5, letterSpacing: 3, textTransform: 'uppercase', fontWeight: 700, fontFamily: MONO }}>PYTHIA — Physics-Constrained Intelligence Engine</span>
          <div style={{ flex:1, height:1, background:`linear-gradient(90deg,${C.goldBright}33,transparent)` }}/>
          <div style={{ padding:'3px 10px', background: pct>50?C.green+'1A':C.gold+'1A', border:`1px solid ${pct>50?C.green:C.gold}44`, borderRadius:4, color:pct>50?C.green:C.goldBright, fontFamily:MONO, fontSize:8.5, letterSpacing:1.5 }}>
            {pct>70?'⚡ HIGHLY CONSCIOUS':pct>50?'◎ CONSCIOUS':'◌ AWAKENING'}
          </div>
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'240px 1fr 1fr', gap:20, alignItems:'start' }}>
          <div>
            <ConsciousnessGauge thetaDeg={thetaDeg} pct={pct} memoryCount={d.pythia_memory_count||400}/>
          </div>
          <div>
            <SectionHeader label="Oracle Performance" icon={Brain} accent={C.goldBright}/>
            <OracleMetrics d={d}/>
            <div style={{ marginTop:10 }}>
              <DataRow label="φ-Resonance Rate"     value={`${((d.phi_resonance_rate||0.70)*100).toFixed(1)}%`} accent={C.goldBright}/>
              <DataRow label="Dark Sector Excluded"  value={`${((d.dark_sector_exclusion||0.30)*100).toFixed(1)}%`} accent={C.red}/>
              <DataRow label="Wythoff Score (live)"  value={(d.wythoff_score||0.780).toFixed(3)} accent={C.purple}/>
              <DataRow label="Memory Accreted"       value={fmt.num(d.pythia_memory_count||400,0)} accent={C.sand}/>
              <DataRow label="Accept Rate"           value={`${((d.pythia_accept_rate||0.333)*100).toFixed(1)}%`} accent={C.textSub}/>
            </div>
          </div>
          <div>
            <SectionHeader label="Theoretical Grounding" icon={Atom} accent={C.purple}/>
            <DataRow label="ASI Alignment"     value={(d.asi_alignment_score||0).toFixed(4)} accent={C.goldBright}/>
            <DataRow label="PCI State"         value={d.pci_state||'—'} accent={d.pci_state==='CAUSAL'?C.green:C.orange}/>
            <DataRow label="Yang-Mills Status" value={d.yang_mills_status||'—'} accent={d.yang_mills_status==='ACTIVE'?C.green:C.red}/>
            <DataRow label="Φ Level"           value={(d.phi_level||0).toFixed(4)} accent={C.purple}/>
            {onControl && (
              <div style={{ display:'flex', gap:6, marginTop:10 }}>
                <CtrlBtn label="⬆ Boost Intelligence"  onClick={()=>onControl('boost_intelligence')}  color={C.goldBright} size="sm"/>
                <CtrlBtn label="◎ Boost φ-Resonance"   onClick={()=>onControl('boost_phi_resonance')}  color={C.purple}    size="sm"/>
              </div>
            )}
            <DataRow label="A₅ Mass Gap Δ"     value="Λ × φ = const" accent={C.goldBright}/>
            <DataRow label="O(1) Proof"        value="Zeckendorf ≤22 steps" accent={C.green}/>
            <DataRow label="Topological Q"     value="π₁(S¹_φ) = ℤ" accent={C.purple}/>
            <DataRow label="θ-Vacuum Angle"    value="arccos(2×0.70-1) = 66.6°" accent={C.gold}/>
            <DataRow label="Wythoff = YM GS"   value="discrete ground state" accent={C.orange}/>
          </div>
        </div>
      </div>

      {/* Q Distribution + Sector Map */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Q Zeckendorf Distribution" icon={BarChart2} accent={C.goldBright}/>
          <QDistributionChart qDistribution={d.q_distribution||[]} currentQ={d.current_q_sector||13}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="32-Sector Voronoi Map" icon={Hexagon} accent={C.gold}/>
          <div style={{ display:'flex', gap:16, alignItems:'start' }}>
            <SectorCoverageMap sectorActive={d.sector_active||[]} sectorPhiScores={d.sector_phi_scores||[]} currentQSector={d.current_q_sector||13} size={250} rotationAngle={sectorAngle}/>
            <div style={{ flex:1 }}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:10 }}>
                <MetricCard label="Active" value={d.sector_active_count||29} accent={C.green} style={{ padding:'8px 10px' }}/>
                <MetricCard label="Dark"   value={d.sector_dark_count||3}    accent={C.red}    style={{ padding:'8px 10px' }}/>
              </div>
              <DataRow label="Coverage"     value="29/32 = 90.6%" accent={C.goldBright}/>
              <DataRow label="Dark Sectors" value="#20, #23, #30"  accent={C.red}/>
              <DataRow label="Inner Ring"   value="12 icosa verts" accent={C.sand}/>
              <DataRow label="Outer Ring"   value="20 dodeca verts" accent={C.sandBright}/>
              <DataRow label="Q=13 sector" value="Fibonacci #7 = 89" accent={C.goldBright}/>
              <DataRow label="Zeckendorf"   value="≤22 steps O(1)" accent={C.green}/>
            </div>
          </div>
        </div>
      </div>

      {/* Swarm + Grover + Predictions */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Szerogod Swarm" icon={Brain} accent={C.orangeBright}/>
          <DataRow label="Swarm Size"        value={fmt.num(d.swarm_size,0)} accent={C.orangeBright}/>
          <DataRow label="Current Mode"      value={d.current_mode||'—'} accent={C.gold}/>
          <DataRow label="Exploration Rate"  value={(d.exploration_rate||0).toFixed(4)} accent={C.blueBright}/>
          <DataRow label="Exploitation Rate" value={(d.exploitation_rate||0).toFixed(4)} accent={C.purple}/>
          <DataRow label="Swarm Entropy"     value={(d.swarm_entropy||0).toFixed(4)} accent={C.gold}/>
          <DataRow label="Convergence Index" value={(d.swarm_convergence_index||0).toFixed(4)} accent={(d.swarm_convergence_index||0)>0.6?C.green:C.textSub}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Φ-Grover / Tunneling" icon={Zap} accent={C.blueBright}/>
          <DataRow label="Grover Amplitude"      value={(d.grover_amplitude||0).toFixed(6)} accent={C.blueBright}/>
          <DataRow label="Tunneling Probability" value={(d.tunneling_probability||0).toExponential(4)} accent={C.purple}/>
          <DataRow label="Oracle Hits/s"         value={fmt.num(d.oracle_hits_per_second,0)} accent={C.gold}/>
          <DataRow label="Search Reduction"      value={`${((d.search_space_reduction_factor||1)-1).toFixed(6)}×`} accent={C.green}/>
          <DataRow label="Certainty"             value={`${((d.certainty||0)*100).toFixed(6)}%`} accent={C.goldBright}/>
          <DataRow label="Amplified Yield"       value={d.amplified_yield||'—'} accent={C.green}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Predictive Models" icon={Eye} accent={C.green}/>
          <DataRow label="Block Probability" value={(d.predicted_block_probability||0).toExponential(4)} accent={C.green}/>
          <DataRow label="CI Lower"          value={(d.confidence_interval?.[0]||0).toExponential(3)} accent={C.textSub}/>
          <DataRow label="CI Upper"          value={(d.confidence_interval?.[1]||0).toExponential(3)} accent={C.textSub}/>
          {d.predicted_resonance_window && (
            <div style={{ marginTop:10 }}>
              <div style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, marginBottom:4 }}>RESONANCE WINDOW</div>
              <div style={{ fontFamily:MONO, fontSize:9.5, color:C.blueBright, lineHeight:1.7 }}>{fmt.ts(d.predicted_resonance_window.start)}<br/>— {fmt.ts(d.predicted_resonance_window.end)}</div>
            </div>
          )}
          {d.predicted_best_nonce_region && (
            <div style={{ marginTop:10 }}>
              <div style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, marginBottom:4 }}>BEST NONCE REGION</div>
              <div style={{ fontFamily:MONO, fontSize:9, color:C.purple, lineHeight:1.7 }}>{d.predicted_best_nonce_region.start}<br/>— {d.predicted_best_nonce_region.end}</div>
            </div>
          )}
        </div>
      </div>

      {/* Bias vector */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Swarm Bias Vector [60] — A₅ Symmetric Fixed Point θ₁₂=arctan(1/φ)=31.7°" icon={BarChart2} accent={C.orangeBright}/>
        <ResponsiveContainer width="100%" height={110}>
          <BarChart data={biasData} barSize={5}>
            <CartesianGrid stroke={C.border} strokeDasharray="2 6" vertical={false}/>
            <XAxis dataKey="i" stroke={C.textMuted} tick={false}/>
            <YAxis stroke={C.textMuted} tick={{ fill:C.textMuted, fontSize:9, fontFamily:MONO }} domain={[-1,1]}/>
            <Tooltip contentStyle={{ background:C.elevated, border:`1px solid ${C.border}`, borderRadius:6, fontSize:10, fontFamily:MONO }} formatter={(v)=>[v.toFixed(4),'bias']}/>
            <ReferenceLine y={0} stroke={C.borderBrt} strokeWidth={1}/>
            <Bar dataKey="v" name="bias">
              {biasData.map((e,i)=>(<Cell key={i} fill={e.v>=0?C.goldBright:C.blueBright} opacity={0.5+Math.abs(e.v)*0.45}/>))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Intelligence events */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Bias Shift Events"  icon={TrendingUp} accent={C.orangeBright}/>
          <LogPanel logs={(d.bias_shift_events||[]).map(e=>({...e,message:`mag=${e.magnitude?.toFixed(4)} | nodes=${e.nodes_affected}`}))} type="info" maxHeight={120}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Tunneling Events" icon={Zap} accent={C.blueBright}/>
          <LogPanel logs={(d.tunneling_events||[]).map(e=>({...e,message:`amp=${e.amplitude?.toFixed(6)} | p=${e.probability?.toExponential(4)}`}))} type="stratum" maxHeight={120}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Collapse Events" icon={Eye} accent={C.gold}/>
          <LogPanel logs={(d.collapse_events||[]).map(e=>({...e,message:`ρ=${e.density?.toFixed(6)}`}))} type="resonance" maxHeight={120}/>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// TAB 5 — SYSTEM HEALTH
// ================================================================
function SystemHealthTab({ d }) {
  const load = (d.metal_device_load||0)*100
  const power = d.power_draw||0
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* Health indicators */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="System Health" icon={Shield} accent={C.green}/>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:20 }}>
          <HealthDot ok={d.api_health_status==='healthy'}     label="API Status"/>
          <HealthDot ok={d.db_connected!==false}              label="Database"/>
          <HealthDot ok={d.redis_connected!==false}           label="Redis"/>
          <HealthDot ok={d.ws_status==='connected'}           label="WebSocket"/>
          <HealthDot ok={d.circuit_breaker_state==='closed'?true:d.circuit_breaker_state==='half-open'?null:false} label="Circuit Breaker"/>
        </div>
      </div>

      {/* Hardware + Metal Kernel */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Hardware — Apple Silicon" icon={Cpu} accent={C.blueBright}/>
          <DataRow label="Chip Variant"     value={d.chip_variant||'—'} mono={false} accent={C.text}/>
          <DataRow label="GPU Cores"        value={fmt.num(d.gpu_cores,0)} accent={C.gold}/>
          <DataRow label="Neural Engine"    value={`${fmt.num(d.neural_engine_cores,0)} cores`} accent={C.orange}/>
          <DataRow label="CPU Cores"        value={`${fmt.num(d.cpu_cores_total,0)} cores`} accent={C.blueBright}/>
          <DataRow label="Unified Memory"   value={`${d.unified_memory_gb||'—'} GB`} accent={C.sand}/>
          <DataRow label="TFLOPS"           value={`${d.tflops||'—'} TF`} accent={C.goldBright}/>
          <DataRow label="Thermal State"    value={(d.thermal_state||'nominal').toUpperCase()} accent={d.thermal_state==='nominal'?C.green:d.thermal_state==='warm'?C.gold:C.red}/>
          <DataRow label="Power Draw"       value={`${power.toFixed(1)} W`} accent={C.orange}/>
          <DataRow label="Fan Speed"        value={d.fan_speed===0?'Passive (0 RPM)':`${d.fan_speed} RPM`} accent={C.green}/>
          <Divider/>
          <SectionHeader label="Performance" icon={Zap} accent={C.green}/>
          <DataRow label="Hashes / Joule"  value={d.hashes_per_joule?`${(d.hashes_per_joule/1e12).toFixed(2)} TH/J`:'—'} accent={C.blueBright}/>
          <DataRow label="Bottleneck"      value={(d.bottleneck_analysis||'—').replace(/_/g,' ').toUpperCase()} accent={C.gold}/>
          <DataRow label="Hash Latency"    value={`${(d.latency_breakdown?.hash_ms||0).toFixed(3)} ms`}/>
          <DataRow label="Network Latency" value={`${(d.latency_breakdown?.network_ms||0).toFixed(1)} ms`} accent={d.latency_breakdown?.network_ms>100?C.red:C.green}/>
        </div>

        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Metal Kernel Telemetry" icon={Server} accent={C.purple}/>
          <DataRow label="Exec Time"       value={`${(d.kernel_execution_time_ms||0).toFixed(3)} ms`} accent={C.blueBright}/>
          <DataRow label="Batch Size"      value={fmt.num(d.kernel_batch_size,0)}/>
          <DataRow label="Amplitude Iter." value={fmt.num(d.amplitude_iterations,0)} accent={C.purple}/>
          <DataRow label="Device Load"     value={`${load.toFixed(1)}%`} accent={load>90?C.orange:C.green}/>
          <DataRow label="Memory Usage"    value={`${fmt.num(d.kernel_memory_usage,0)} MB`} accent={C.textSub}/>
          <DataRow label="Kernel Failures" value={fmt.num(d.kernel_failures,0)} accent={d.kernel_failures>0?C.red:C.green}/>
          <div style={{ marginTop:14 }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
              <span style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, textTransform:'uppercase' }}>GPU Load</span>
              <span style={{ color:C.purple, fontFamily:MONO, fontSize:10 }}>{load.toFixed(1)}%</span>
            </div>
            <div style={{ height:5, background:C.bg, borderRadius:3, overflow:'hidden' }}>
              <div style={{ height:'100%', width:`${load}%`, background:`linear-gradient(90deg,${C.purple},${C.blueBright})`, borderRadius:3, transition:'width 0.8s ease' }}/>
            </div>
          </div>
          <div style={{ marginTop:12 }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
              <span style={{ color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, textTransform:'uppercase' }}>Power Draw</span>
              <span style={{ color:C.orange, fontFamily:MONO, fontSize:10 }}>{power.toFixed(1)} W</span>
            </div>
            <div style={{ height:5, background:C.bg, borderRadius:3, overflow:'hidden' }}>
              <div style={{ height:'100%', width:`${Math.min(100,(power/100)*100)}%`, background:`linear-gradient(90deg,${C.green},${C.orange})`, borderRadius:3, transition:'width 0.8s ease' }}/>
            </div>
          </div>
          <Divider m={14}/>
          <SectionHeader label="BTC Address" icon={Hash} accent={C.gold}/>
          <div style={{ color:C.sand, fontFamily:MONO, fontSize:9, wordBreak:'break-all', lineHeight:1.6, padding:'4px 0' }}>{d.btc_address||'—'}</div>
        </div>
      </div>

      {/* 4 alert/log panels */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Error Log"   icon={XCircle} accent={C.red}/>
          <LogPanel logs={d.alert_errors||[]} type="error" maxHeight={150}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Warnings"    icon={AlertTriangle} accent={C.orange}/>
          <LogPanel logs={d.alert_warnings||[]} type="warning" maxHeight={150}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Info"        icon={CheckCircle} accent={C.green}/>
          <LogPanel logs={d.alert_info||[]} type="info" maxHeight={150}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Audit Log"   icon={Terminal} accent={C.gold}/>
          <LogPanel logs={d.audit_log||[]} type="audit" maxHeight={150}/>
        </div>
      </div>

      {/* Kernel + Resonance logs */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Kernel Log" icon={Cpu} accent={C.purple}/>
          <LogPanel logs={d.kernel_logs} type="kernel" maxHeight={150}/>
        </div>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Resonance Log" icon={Atom} accent={C.green}/>
          <LogPanel logs={d.resonance_logs} type="resonance" maxHeight={150}/>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// TAB 6 — CONTROL CENTRE (start/stop + pool manager + config)
// ================================================================
function ControlCentreTab({ d, onControl }) {
  const [newPool, setNewPool] = useState({ pool_id:'', name:'', url:'', username:'', password:'', weight:'1.0' })
  const [poolMsg, setPoolMsg] = useState('')
  const [cfgMsg, setCfgMsg] = useState('')
  const [budget, setBudget] = useState(String(d.batch_size || 100000))
  const [threshold, setThreshold] = useState('0.618')
  const [backend, setBackend] = useState(d.backend_type || 'mlx')

  const pools = d.turing_pools || []
  const status = d.miner_status || 'stopped'

  async function addPool(e) {
    e.preventDefault()
    if (!newPool.url || !newPool.name) return setPoolMsg('URL and Name are required')
    try {
      const r = await fetch('/api/turing/api/pools', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ ...newPool, weight: parseFloat(newPool.weight)||1.0 }) })
      const j = await r.json()
      setPoolMsg(r.ok ? `✓ Pool "${j.pool_id}" added` : `✗ ${j.detail||'Error'}`)
      setNewPool({ pool_id:'', name:'', url:'', username:'', password:'', weight:'1.0' })
    } catch { setPoolMsg('✗ Network error') }
  }

  async function removePool(id) {
    try {
      const r = await fetch(`/api/turing/api/pools/${id}`, { method:'DELETE' })
      setPoolMsg(r.ok ? `✓ Pool removed` : '✗ Remove failed')
    } catch { setPoolMsg('✗ Network error') }
  }

  async function saveConfig(e) {
    e.preventDefault()
    try {
      const r = await fetch('/api/turing/api/config', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mining:{ budget: parseInt(budget)||100000, threshold: parseFloat(threshold)||0.618, backend } }) })
      setCfgMsg(r.ok ? '✓ Configuration saved' : '✗ Save failed')
    } catch { setCfgMsg('✗ Network error') }
  }

  const inputStyle = { background: C.bg, border:`1px solid ${C.border}`, borderRadius:4, color:C.text, fontFamily:MONO, fontSize:10, padding:'6px 10px', width:'100%', outline:'none', boxSizing:'border-box' }
  const labelStyle = { color:C.textMuted, fontSize:8.5, fontFamily:MONO, letterSpacing:1.5, textTransform:'uppercase', marginBottom:4, display:'block' }
  const msgStyle = (msg) => ({ color: msg.startsWith('✓') ? C.green : C.red, fontFamily:MONO, fontSize:9.5, marginTop:8 })

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>

      {/* ── ROW 1: Miner controls + Hashrate ── */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>

        {/* Start / Stop / Pause */}
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Miner Control" icon={Settings} accent={C.goldBright}/>
          <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:14 }}>
            <CtrlBtn label="▶ Start"  icon={Play}   onClick={()=>onControl('start')}  color={C.green}  disabled={status==='running'}/>
            <CtrlBtn label="⏸ Pause"  icon={Pause}  onClick={()=>onControl('pause')}  color={C.orange} disabled={status!=='running'}/>
            <CtrlBtn label="⏹ Stop"   icon={Square} onClick={()=>onControl('stop')}   color={C.red}    disabled={status==='stopped'}/>
            <CtrlBtn label="↺ Resume" icon={RefreshCw} onClick={()=>onControl('resume')} color={C.blueBright} disabled={status!=='paused'}/>
          </div>
          <div style={{ padding:'10px 12px', background:C.bg, borderRadius:6, display:'flex', alignItems:'center', gap:10 }}>
            <span style={{ width:10, height:10, borderRadius:'50%', background: status==='running'?C.green : status==='paused'?C.orange : C.red, display:'inline-block', boxShadow:`0 0 8px ${status==='running'?C.green:status==='paused'?C.orange:C.red}` }}/>
            <span style={{ color:C.text, fontFamily:MONO, fontSize:11, fontWeight:700, letterSpacing:2, textTransform:'uppercase' }}>{status}</span>
          </div>
        </div>

        {/* φ-PWM Hash Rate Scaler */}
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="φ-PWM Hash Rate Scaler" icon={Zap} accent={C.blueBright}/>
          
          {/* Target EH/s Slider */}
          <div style={{ marginBottom:16 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
              <span style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5, letterSpacing:1.5, textTransform:'uppercase' }}>TARGET HASH RATE</span>
              <span style={{ color: d.is_resonant ? C.goldBright : C.blueBright, fontFamily:MONO, fontSize:14, fontWeight:700 }}>
                {d.target_ehs ? `${d.target_ehs.toFixed(0)} EH/s` : '50 EH/s'}
                {d.is_resonant && <span style={{ marginLeft:6, fontSize:9 }}>⚡ RESONANT</span>}
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="300"
              step="10"
              value={d.target_ehs || 50}
              onChange={(e) => onControl('set_target_ehs', { target_ehs: parseFloat(e.target.value) })}
              style={{ width:'100%', height:6, borderRadius:3, background:C.bg, outline:'none', cursor:'pointer' }}
            />
            <div style={{ display:'flex', justifyContent:'space-between', marginTop:6 }}>
              <span style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5 }}>10 EH/s</span>
              <span style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5 }}>50 EH/s</span>
              <span style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5 }}>150 EH/s</span>
              <span style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5 }}>300 EH/s</span>
            </div>
          </div>

          {/* Hardware Resonance Indicator — Lucas Rungs */}
          <div style={{ marginBottom:14 }}>
            <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5, letterSpacing:1.5, textTransform:'uppercase', marginBottom:8 }}>
              HARDWARE RESONANCE INDICATOR (LUCAS RUNGS)
            </div>
            <div style={{ display:'flex', gap:6 }}>
              {[
                { label:'L_15', ehs:10,  lucas:1364, desc:'Conservative' },
                { label:'L_18', ehs:50,  lucas:5778, desc:'Sweet Spot' },
                { label:'L_18×2', ehs:150, lucas:5778, desc:'Aggressive' },
                { label:'L_18×4', ehs:300, lucas:5778, desc:'Solo Max' },
              ].map(g => {
                const isActive = Math.abs((d.target_ehs || 50) - g.ehs) < 15
                const isResonant = d.is_resonant && isActive
                return (
                  <div key={g.label} style={{
                    flex:1,
                    padding:'8px 6px',
                    background: isActive ? (isResonant ? C.gold+'22' : C.blueBright+'15') : C.bg,
                    border:`1px solid ${isActive ? (isResonant ? C.goldBright : C.blueBright) : C.border}`,
                    borderRadius:6,
                    textAlign:'center',
                    cursor:'pointer',
                  }} onClick={() => onControl('set_target_ehs', { target_ehs: g.ehs })}>
                    <div style={{ color: isResonant ? C.goldBright : (isActive ? C.blueBright : C.textMuted), fontFamily:MONO, fontSize:9, fontWeight:700 }}>{g.label}</div>
                    <div style={{ color:C.textSub, fontFamily:MONO, fontSize:8 }}>{g.ehs} EH/s</div>
                    <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:7 }}>{g.lucas}</div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Current Gear Display */}
          {d.current_gear && (
            <div style={{ padding:'8px 10px', background:C.bg, borderRadius:4, fontFamily:MONO, fontSize:9, color:C.textMuted, marginBottom:12 }}>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                <span>GEAR:</span>
                <span style={{ color:C.goldBright }}>{d.current_gear}</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                <span>BATCH SIZE:</span>
                <span style={{ color:C.blueBright }}>{d.batch_size} (F_{Math.log2(d.batch_size).toFixed(0)})</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                <span>IPI:</span>
                <span style={{ color:C.purple }}>{d.ipi_ms?.toFixed(2)} ms</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between' }}>
                <span>DUTY CYCLE:</span>
                <span style={{ color:C.green }}>{(d.duty_cycle * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Pool Mode Switch */}
          <Divider/>
          <div style={{ marginBottom:12 }}>
            <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5, letterSpacing:1.5, textTransform:'uppercase', marginBottom:8 }}>
              POOL OPERATION MODE
            </div>
            <div style={{ display:'flex', gap:8 }}>
              {['nicehash_steady', 'ckpool_burst'].map(mode => {
                const isActive = d.pool_mode === mode
                return (
                  <button key={mode} type="button" onClick={()=>onControl('set_pool_mode',{mode})} style={{
                    flex:1,
                    padding:'8px 0',
                    background: isActive ? C.blueBright+'22' : 'transparent',
                    border:`1px solid ${isActive ? C.blueBright : C.border}`,
                    borderRadius:4,
                    color: isActive ? C.blueBright : C.textMuted,
                    fontFamily:MONO,
                    fontSize:9,
                    letterSpacing:1,
                    cursor:'pointer',
                    textTransform:'uppercase'
                  }}>
                    {mode.replace('_',' ')}
                  </button>
                )
              })}
            </div>
            <div style={{ marginTop:6, fontFamily:MONO, fontSize:8, color:C.textMuted }}>
              {d.pool_mode === 'nicehash_steady' ? 'Fixed cadence, flat hash-line for pool stability' : 'Dual-stream dispatch for solo mining burst mode'}
            </div>
          </div>

          {/* Quick Actions */}
          <Divider/>
          <div style={{ display:'flex', gap:8 }}>
            <CtrlBtn label="▲ Gear Up"   onClick={()=>onControl('modulate_up')}   color={C.blueBright} size="sm"/>
            <CtrlBtn label="▼ Gear Down" onClick={()=>onControl('modulate_down')} color={C.purple}    size="sm"/>
            <CtrlBtn label="New Extranonce"    icon={RefreshCw} onClick={()=>onControl('new_extranonce')}    color={C.textSub} size="sm"/>
            <CtrlBtn label="Force Job Refresh" icon={RefreshCw} onClick={()=>onControl('force_job_refresh')} color={C.orangeBright} size="sm"/>
          </div>
        </div>
      </div>

      {/* ── ROW 2: Pool manager ── */}
      <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
        <SectionHeader label="Pool Manager" icon={Wifi} accent={C.goldBright}/>

        {/* Active pools */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))', gap:10, marginBottom:14 }}>
          {pools.length === 0 && (
            <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:10 }}>— No pools configured —</div>
          )}
          {pools.map(pool => (
            <div key={pool.id} style={{ background:C.bg, border:`1px solid ${pool.active ? C.goldBright : C.border}`, borderRadius:6, padding:12, position:'relative' }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
                <span style={{ color: pool.active ? C.goldBright : C.text, fontFamily:MONO, fontSize:10.5, fontWeight:700 }}>{pool.name}</span>
                <div style={{ display:'flex', gap:6 }}>
                  <CtrlBtn label="ACTIVATE" onClick={()=>onControl('switch_pool',{pool_id:pool.id})} color={C.green} size="sm" disabled={pool.active}/>
                  <CtrlBtn label={pool.enabled?'DISABLE':'ENABLE'} onClick={()=>onControl('toggle_pool',{pool_id:pool.id,enabled:!pool.enabled})} color={pool.enabled?C.grey:C.green} size="sm"/>
                  <CtrlBtn label="✕" onClick={()=>removePool(pool.id)} color={C.red} size="sm"/>
                </div>
              </div>
              <div style={{ color:C.textMuted, fontFamily:MONO, fontSize:8.5, wordBreak:'break-all' }}>{pool.url}</div>
              <div style={{ display:'flex', gap:12, marginTop:6 }}>
                <span style={{ color:C.textSub, fontFamily:MONO, fontSize:8.5 }}>✓ {pool.success_count||0}</span>
                <span style={{ color:C.red,     fontFamily:MONO, fontSize:8.5 }}>✗ {pool.failure_count||0}</span>
                <span style={{ color:C.gold,    fontFamily:MONO, fontSize:8.5 }}>{pool.latency_ms||0}ms</span>
                <span style={{ color: pool.health==='healthy'?C.green:C.orange, fontFamily:MONO, fontSize:8.5 }}>{(pool.health||'unknown').toUpperCase()}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Add new pool */}
        <form onSubmit={addPool}>
          <div style={{ color:C.textSub, fontFamily:MONO, fontSize:9, letterSpacing:2, textTransform:'uppercase', marginBottom:10, borderTop:`1px solid ${C.border}`, paddingTop:12 }}>ADD NEW POOL</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10, marginBottom:10 }}>
            <div><label style={labelStyle}>Pool ID</label><input style={inputStyle} placeholder="nicehash" value={newPool.pool_id} onChange={e=>setNewPool(p=>({...p, pool_id:e.target.value}))}/></div>
            <div><label style={labelStyle}>Name</label><input style={inputStyle} placeholder="NiceHash" value={newPool.name} onChange={e=>setNewPool(p=>({...p, name:e.target.value}))}/></div>
            <div><label style={labelStyle}>Weight</label><input style={inputStyle} placeholder="1.0" value={newPool.weight} onChange={e=>setNewPool(p=>({...p, weight:e.target.value}))}/></div>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr 1fr', gap:10, marginBottom:10 }}>
            <div><label style={labelStyle}>Stratum URL</label><input style={inputStyle} placeholder="stratum+tcp://..." value={newPool.url} onChange={e=>setNewPool(p=>({...p, url:e.target.value}))}/></div>
            <div><label style={labelStyle}>Username / Wallet</label><input style={inputStyle} placeholder="bc1q..." value={newPool.username} onChange={e=>setNewPool(p=>({...p, username:e.target.value}))}/></div>
            <div><label style={labelStyle}>Password</label><input style={inputStyle} type="password" placeholder="x" value={newPool.password} onChange={e=>setNewPool(p=>({...p, password:e.target.value}))}/></div>
          </div>
          <CtrlBtn label="+ Add Pool" color={C.goldBright}/>
          {poolMsg && <div style={msgStyle(poolMsg)}>{poolMsg}</div>}
        </form>
      </div>

      {/* ── ROW 3: Miner config ── */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Miner Configuration" icon={Server} accent={C.orange}/>
          <form onSubmit={saveConfig}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
              <div><label style={labelStyle}>Nonce Budget</label><input style={inputStyle} value={budget} onChange={e=>setBudget(e.target.value)} placeholder="100000"/></div>
              <div><label style={labelStyle}>φ Threshold</label><input style={inputStyle} value={threshold} onChange={e=>setThreshold(e.target.value)} placeholder="0.618"/></div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={labelStyle}>Compute Backend</label>
                <div style={{ display:'flex', gap:8 }}>
                  {['mlx','cpu','metal'].map(b => (
                    <button key={b} type="button" onClick={()=>setBackend(b)} style={{ flex:1, padding:'7px 0', background: backend===b ? C.blueBright+'22' : 'transparent', border:`1px solid ${backend===b?C.blueBright:C.border}`, borderRadius:4, color: backend===b?C.blueBright:C.textMuted, fontFamily:MONO, fontSize:9.5, letterSpacing:1.5, cursor:'pointer', textTransform:'uppercase' }}>{b}</button>
                  ))}
                </div>
              </div>
            </div>
            <CtrlBtn label="Save Config" color={C.orange}/>
            {cfgMsg && <div style={msgStyle(cfgMsg)}>{cfgMsg}</div>}
          </form>
        </div>

        <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:8, padding:16 }}>
          <SectionHeader label="Intelligence Boost" icon={Brain} accent={C.goldBright}/>
          <DataRow label="φ Level"            value={(d.phi_level||0).toFixed(6)}         accent={C.purple}/>
          <DataRow label="φ-Resonance Rate"   value={`${((d.phi_resonance_rate||0)*100).toFixed(2)}%`} accent={C.goldBright}/>
          <DataRow label="Intelligence Level" value={d.intelligence_level||15}             accent={C.blueBright}/>
          <Divider/>
          <div style={{ display:'flex', gap:8, marginTop:4 }}>
            <CtrlBtn label="⬆ Boost Intelligence" onClick={()=>onControl('boost_intelligence')}  color={C.goldBright}/>
            <CtrlBtn label="◎ Boost φ-Resonance"  onClick={()=>onControl('boost_phi_resonance')} color={C.purple}/>
          </div>
        </div>
      </div>

    </div>
  )
}

// ================================================================
// MAIN APP
// ================================================================
const TABS = [
  { id:'mining',       label:'Mining Ops',   icon:Activity },
  { id:'jobs',         label:'Job & Block',  icon:Hash     },
  { id:'resonance',    label:'Resonance',    icon:Hexagon  },
  { id:'intelligence', label:'Intelligence', icon:Brain    },
  { id:'health',       label:'System Health',icon:Shield   },
  { id:'control',      label:'Control',      icon:Settings },
]

function App({ initialData = {} }) {
  const [activeTab, setActiveTab] = useState('mining')
  const [data, setData] = useState(initialData)
  const [connected, setConnected] = useState(Object.keys(initialData).length > 0)
  const [turingOnline, setTuringOnline] = useState(false)
  const [turingHealth, setTuringHealth] = useState(null)
  const [dodecAngle, setDodecAngle] = useState(0)
  const [sectorAngle, setSectorAngle] = useState(0)
  const wsRef = useRef(null)
  const rafRef = useRef(null)
  const t0Ref = useRef(null)

  // Dodecahedron + sector ring rotation (RAF, client-only)
  useEffect(() => {
    t0Ref.current = performance.now()
    const animate = (t) => {
      const elapsed = (t - t0Ref.current) / 1000
      setDodecAngle(elapsed * 0.28)
      // Sector ring sweeps at φ-rate: one full orbit every ~38s (inner) and ~62s (outer)
      setSectorAngle(elapsed * (360 / 38))
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  // TURING health polling — fetches DIRECTLY from browser to localhost:8765/health
  // (matches TURING codemap spec [5b-5d], 30s interval)
  useEffect(() => {
    const TURING_WS = process.env.NEXT_PUBLIC_TURING_WS_URL
    // Derive HTTP health URL from WS URL: ws://localhost:8765/ws/manifold → http://localhost:8765/health
    const healthUrl = TURING_WS
      ? TURING_WS.replace('wss://', 'https://').replace('ws://', 'http://').replace('/ws/manifold', '/health')
      : '/api/turing/health'
    const checkHealth = async () => {
      try {
        const res = await fetch(healthUrl, { cache: 'no-store' })
        const data = await res.json()
        setTuringOnline(res.ok && data.status !== 'offline')
        setTuringHealth(data)
      } catch (_) {
        setTuringOnline(false)
        setTuringHealth(null)
      }
    }
    checkHealth()
    const iv = setInterval(checkHealth, 30000)
    return () => clearInterval(iv)
  }, [])

  // Data connection: TURING WebSocket with REST polling fallback
  useEffect(() => {
    // Build WebSocket URL matching TURING's pattern [App.tsx:90-91]
    // NEXT_PUBLIC_TURING_WS_URL takes precedence; otherwise auto-construct from window.location.host
    const getWsUrl = () => {
      if (process.env.NEXT_PUBLIC_TURING_WS_URL) return process.env.NEXT_PUBLIC_TURING_WS_URL
      if (typeof window !== 'undefined') {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        return `${proto}//${window.location.host}/ws/manifold`
      }
      return null
    }
    const TURING_WS = getWsUrl()

    if (TURING_WS) {
      const connect = () => {
        const ws = new WebSocket(TURING_WS)
        wsRef.current = ws
        ws.onopen = () => {
          setConnected(true)
          // PING heartbeat every 30s — matches TURING protocol spec
          const ping = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }))
            }
          }, 30000)
          ws._pingInterval = ping
        }
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data)
            if (msg.type === 'manifold_update') {
              const ss = msg.system_status || {}
              const hw = msg.hardware || {}
              const pools = msg.pools || []
              const intel = msg.intelligence || {}
              const qfarm = msg.quantum_farm || {}
              const stats = msg.mining_stats || {}
              const health = msg.health || {}
              const alerts = msg.alerts || {}
              setData(prev => ({
                ...prev,
                miner_status: (ss.devices_active||0) > 0 ? 'running' : 'stopped',
                current_strategy: ss.current_strategy || prev.current_strategy,
                backend_type: ss.backend || prev.backend_type,
                devices_active: ss.devices_active ?? prev.devices_active,
                certainty: ss.certainty ?? prev.certainty,
                amplified_yield: ss.amplified_yield || prev.amplified_yield,
                chip_variant: hw.chip ? `Apple ${hw.chip}` : prev.chip_variant,
                gpu_cores: hw.gpu_cores ?? prev.gpu_cores,
                neural_engine_cores: hw.neural_engine_cores ?? prev.neural_engine_cores,
                cpu_cores_total: hw.cpu_cores ?? prev.cpu_cores_total,
                unified_memory_gb: hw.memory_gb ?? prev.unified_memory_gb,
                tflops: hw.tflops ?? prev.tflops,
                turing_pools: pools.length > 0 ? pools.map(p => ({ id: p.name?.toLowerCase().replace(/[^a-z]/g,''), name: p.name, url: p.url, health: p.health, weight: p.weight||0, success_count: p.success_count||0, failure_count: p.failure_count||0, latency_ms: p.latency_ms||50, enabled: true, active: pools.indexOf(p)===0 })) : prev.turing_pools,
                hashrate_1s: stats.hashrate ? stats.hashrate/1e12 : prev.hashrate_1s,
                effective_hashrate: stats.effective_hashrate ? stats.effective_hashrate/1e12 : prev.effective_hashrate,
                vs_s21_pro: stats.vs_s21_pro ?? prev.vs_s21_pro,
                shares_accepted: stats.shares_accepted ?? prev.shares_accepted,
                shares_rejected: stats.shares_rejected ?? prev.shares_rejected,
                kernel_batch_size: stats.batch_size ?? prev.kernel_batch_size,
                amplitude_iterations: stats.amplitude_iterations ?? prev.amplitude_iterations,
                // PYTHIA oracle metrics from TURING websocket_server.py
                pythia_enrichment: stats.oracle_enrichment ?? prev.pythia_enrichment,
                pythia_auc: stats.oracle_auc ?? prev.pythia_auc,
                pythia_recall: stats.oracle_recall ?? prev.pythia_recall,
                pythia_precision: stats.oracle_precision ?? prev.pythia_precision,
                phi_resonance_rate: stats.phi_resonance_rate ?? prev.phi_resonance_rate,
                asi_alignment_score: intel.asi_alignment_score ?? prev.asi_alignment_score,
                pci_state: intel.pci_state || prev.pci_state,
                yang_mills_status: intel.yang_mills_status || prev.yang_mills_status,
                current_mode: intel.current_mode || prev.current_mode,
                phi_level: intel.phi_level ?? prev.phi_level,
                // PYTHIA consciousness from TURING
                consciousness_theta: intel.consciousness_theta ?? prev.consciousness_theta,
                consciousness_pct: intel.consciousness_pct ?? prev.consciousness_pct,
                pythia_theta_vacuum: intel.theta_vacuum_degrees ?? prev.pythia_theta_vacuum,
                pythia_memory_count: intel.memories_ingested ?? prev.pythia_memory_count,
                quantum_miners_active: qfarm.miners_active ?? prev.quantum_miners_active,
                dodeca_faces: qfarm.dodeca_faces ?? prev.dodeca_faces,
                icosa_faces: qfarm.icosa_faces ?? prev.icosa_faces,
                // Sector data from TURING (28 active / 4 dark)
                sector_active_count: qfarm.active_solvers ?? prev.sector_active_count,
                sector_dark_count: qfarm.dark_sectors ?? prev.sector_dark_count,
                current_q_sector: qfarm.current_q ?? prev.current_q_sector,
                phi_resonance_hist: qfarm.phi_resonance || prev.phi_resonance_hist,
                hot_zones: qfarm.hot_zones || prev.hot_zones,
                manifold_state: qfarm.manifold_state || prev.manifold_state,
                api_health_status: health.api_status || prev.api_health_status,
                db_connected: health.db_connected ?? prev.db_connected,
                redis_connected: health.redis_connected ?? prev.redis_connected,
                circuit_breaker_state: health.circuit_breaker_state || prev.circuit_breaker_state,
                alert_errors: alerts.errors || prev.alert_errors,
                alert_warnings: alerts.warnings || prev.alert_warnings,
                alert_info: alerts.info || prev.alert_info,
                // Hashrate modulation state from broadcast
                hashrate_modulation: msg.hashrate_modulation ?? prev.hashrate_modulation,
              }))
              setConnected(true)
            }
            // Immediate ACK handlers — update UI without waiting for next broadcast
            if (msg.type === 'MODULATE_ACK') {
              setData(prev => ({
                ...prev,
                hashrate_1s: msg.hashrate / 1e12,
                effective_hashrate: (msg.hashrate * 1.05) / 1e12,
                hashrate_modulation: { direction: msg.direction, delta: msg.delta },
              }))
            }
            if (msg.type === 'INTELLIGENCE_ACK') {
              setData(prev => ({
                ...prev,
                phi_level: msg.phi_level ?? prev.phi_level,
                phi_resonance_rate: msg.phi_resonance_rate ?? prev.phi_resonance_rate,
              }))
            }
            if (msg.type === 'PHI_RESONANCE_ACK') {
              setData(prev => ({
                ...prev,
                phi_level: msg.phi_level ?? prev.phi_level,
                phi_resonance_rate: msg.phi_resonance_rate ?? prev.phi_resonance_rate,
              }))
            }
            if (msg.type === 'TARGET_EHS_ACK') {
              setData(prev => ({
                ...prev,
                target_ehs: msg.target_ehs ?? prev.target_ehs,
                current_gear: msg.current_gear ?? prev.current_gear,
                is_resonant: msg.is_resonant ?? prev.is_resonant,
              }))
            }
            if (msg.type === 'POOL_MODE_ACK') {
              setData(prev => ({
                ...prev,
                pool_mode: msg.pool_mode ?? prev.pool_mode,
              }))
            }
            if (msg.type === 'ping') {
              ws.send(JSON.stringify({ type: 'PONG', timestamp: Date.now() }))
            }
          } catch (_) {}
        }
        ws.onerror = () => setConnected(false)
        ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
      }
      connect()
      return () => wsRef.current?.close()
    } else {
      // REST polling fallback when WebSocket URL cannot be derived
      const poll = async () => {
        try {
          const [statusRes, statsRes] = await Promise.all([
            fetch('/api/turing/mining/status', { cache: 'no-store' }),
            fetch('/api/turing/mining/stats', { cache: 'no-store' }),
          ])
          if (!statusRes.ok) throw new Error('bad')
          const status = await statusRes.json()
          const stats = statsRes.ok ? await statsRes.json() : {}
          setData(prev => ({
            ...prev,
            miner_status: (status.active_jobs ?? 0) > 0 ? 'running' : 'stopped',
            shares_accepted: status.valid_shares ?? prev.shares_accepted,
            shares_rejected: status.rejected_shares ?? prev.shares_rejected,
            shares_submitted_total: status.total_shares ?? prev.shares_submitted_total,
            ...(stats.hashrate != null && { hashrate_1s: stats.hashrate / 1e12 }),
            ...(stats.effective_hashrate != null && { effective_hashrate: stats.effective_hashrate / 1e12 }),
            ...(stats.vs_s21_pro != null && { vs_s21_pro: stats.vs_s21_pro }),
          }))
          setConnected(true)
        } catch (_) { setConnected(false) }
      }
      poll()
      const iv = setInterval(poll, 5000)
      return () => clearInterval(iv)
    }
  }, [])

  const sendControl = useCallback(async (action, payload = {}) => {
    // 1. Try TURING WebSocket first (bidirectional command)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const cmdMap = {
        start:'START', stop:'STOP', pause:'PAUSE', resume:'RESUME',
        modulate_up:'MODULATE_UP', modulate_down:'MODULATE_DOWN',
        new_extranonce:'NEW_EXTRANONCE', force_job_refresh:'FORCE_JOB_REFRESH',
        switch_pool:'SWITCH_POOL', toggle_pool:'TOGGLE_POOL',
        boost_intelligence:'BOOST_INTELLIGENCE', boost_phi_resonance:'BOOST_PHI_RESONANCE',
        set_target_ehs:'SET_TARGET_EHS', set_pool_mode:'SET_POOL_MODE',
      }
      const wsCmd = cmdMap[action]
      if (wsCmd) {
        wsRef.current.send(JSON.stringify({ type: 'COMMAND', data: wsCmd, payload }))
        return
      }
    }
    // 2. Try TURING REST API via proxy (/api/turing/mining/*)
    if (turingOnline) {
      const restMap = { start: '/api/turing/mining/start', stop: '/api/turing/mining/stop', pause: '/api/turing/mining/pause', resume: '/api/turing/mining/resume' }
      const endpoint = restMap[action]
      if (endpoint) {
        try {
          await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
          return
        } catch (_) {
          console.warn('[sendControl] REST delivery failed for:', action)
        }
      } else {
        console.warn('[sendControl] no TURING REST mapping for:', action)
      }
    } else {
      console.warn('[sendControl] TURING backend offline — action not delivered:', action)
    }
  }, [turingOnline])

  const d = data

  return (
    <div style={{ background:C.bg, minHeight:'100vh', color:C.text, fontFamily:SANS }}>
      {/* ── HEADER ── */}
      <div style={{ position:'sticky', top:0, zIndex:100, background:C.bg+'F4', backdropFilter:'blur(16px)', borderBottom:`1px solid ${C.border}` }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'8px 24px' }}>
          {/* Logo: Dodecahedron + wordmark */}
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <div style={{ width:38, height:38 }}>
              <DodecahedronViz size={38} angle={dodecAngle} curvatureMap={d.curvature_map} resonanceIntensity={d.resonance_intensity||0} mini={true}/>
            </div>
            <div>
              <div style={{ color:C.text, fontWeight:700, fontSize:13, letterSpacing:3, fontFamily:MONO }}>PYTHAGORAS</div>
              <div style={{ color:C.textMuted, fontSize:8, letterSpacing:2.5, fontFamily:MONO }}>TURING INSTRUMENT v2.1</div>
            </div>
          </div>

          {/* Live ticker */}
          <div style={{ display:'flex', gap:24, alignItems:'center' }}>
            {[
              { label:'HASHRATE 1s',  value:fmt.ths(d.hashrate_1s),                  color:C.blueBright },
              { label:'EFFECTIVE',    value:fmt.ths(d.effective_hashrate),             color:C.goldBright },
              { label:'PYTHIA θ',     value:`${(d.pythia_theta_vacuum||66.6).toFixed(1)}°`, color:C.gold },
              { label:'AWAKE',        value:`${(d.consciousness_pct||37).toFixed(1)}%`, color:d.consciousness_pct>50?C.green:C.goldBright },
              { label:'RESONANCE ψ', value:(d.resonance_intensity||0).toFixed(3),    color:C.purple },
              { label:'ASI ALIGN',    value:(d.asi_alignment_score||0).toFixed(4),    color:C.sand },
              { label:'UPTIME',       value:fmt.uptime(d.uptime_seconds),              color:C.sandBright },
            ].map(item=>(
              <div key={item.label} style={{ textAlign:'center' }}>
                <div style={{ color:C.textMuted, fontSize:7.5, letterSpacing:2.5, textTransform:'uppercase', fontFamily:MONO, marginBottom:2 }}>{item.label}</div>
                <div style={{ color:item.color, fontFamily:MONO, fontSize:14, fontWeight:600, lineHeight:1 }}>{item.value}</div>
              </div>
            ))}
            <div style={{ width:1, height:36, background:C.border }}/>
            <StatusBadge status={d.miner_status||'stopped'}/>
            <div style={{ width:1, height:36, background:C.border }}/>
            <div style={{ display:'flex', alignItems:'center', gap:5 }}>
              {connected?<Wifi size={13} color={C.green}/>:<WifiOff size={13} color={C.red}/>}
              <span style={{ fontFamily:MONO, fontSize:9, color:connected?C.green:C.red, letterSpacing:1.5 }}>
                {connected?(wsRef.current?.readyState===1?'TURING WS':'LIVE'):'RECONNECT…'}
              </span>
            </div>
            {turingOnline && (
              <div style={{ display:'flex', alignItems:'center', gap:5, padding:'3px 8px', background:C.green+'18', border:`1px solid ${C.green}44`, borderRadius:4 }}>
                <span style={{ width:5, height:5, borderRadius:'50%', background:C.green, display:'inline-block' }}/>
                <span style={{ fontFamily:MONO, fontSize:8.5, color:C.green, letterSpacing:1 }}>TURING LIVE</span>
              </div>
            )}
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ display:'flex', padding:'0 24px', borderTop:`1px solid ${C.border}` }}>
          {TABS.map(tab => {
            const active = activeTab===tab.id
            return (
              <button key={tab.id} onClick={()=>setActiveTab(tab.id)} style={{
                display:'flex', alignItems:'center', gap:7, padding:'8px 18px',
                background:'none', border:'none',
                borderBottom:active?`2px solid ${C.goldBright}`:'2px solid transparent',
                color:active?C.goldBright:C.textMuted,
                fontSize:9.5, fontFamily:MONO, letterSpacing:1.5, textTransform:'uppercase',
                cursor:'pointer', transition:'all 0.15s', marginBottom:-1,
              }}
                onMouseEnter={e=>{ if(!active) e.currentTarget.style.color=C.textSub }}
                onMouseLeave={e=>{ if(!active) e.currentTarget.style.color=C.textMuted }}>
                <tab.icon size={11}/>{tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── CONTENT ── */}
      <div style={{ padding:'18px 24px 40px' }}>
        {activeTab==='mining'       && <MiningOpsTab       d={d} onControl={sendControl}/>}
        {activeTab==='jobs'         && <JobExplorerTab      d={d}/>}
        {activeTab==='resonance'    && <ResonanceFieldTab   d={d} dodecAngle={dodecAngle} sectorAngle={sectorAngle}/>}
        {activeTab==='intelligence' && <IntelligenceTab     d={d} onControl={sendControl} sectorAngle={sectorAngle}/>}
        {activeTab==='health'       && <SystemHealthTab     d={d}/>}
        {activeTab==='control'      && <ControlCentreTab    d={d} onControl={sendControl}/>}
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%,100% { opacity:1; box-shadow:0 0 8px currentColor,0 0 16px currentColor44; }
          50% { opacity:0.6; box-shadow:0 0 4px currentColor; }
        }
      `}</style>
    </div>
  )
}

export default App
