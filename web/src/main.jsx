import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import {
  FlaskConical,
  LayoutDashboard,
  Table2,
  ChartScatter,
  Sparkles,
  FileText,
  Database,
  Layers3,
  Columns3,
  CircleCheck,
  Upload,
  ArrowRight,
  ArrowUpRight,
  ChevronRight,
  X,
  Menu,
  BookOpen,
  Search,
  SlidersHorizontal,
  ChartSpline,
  ChartColumn,
  ChartNoAxesColumn,
  Microscope,
  Download,
  Send,
  Activity,
  FileSpreadsheet,
  Sprout,
  Crosshair,
  LoaderCircle,
  PanelLeft,
  FolderOpen,
} from 'lucide-react';
import '@fontsource-variable/geist';
import Plot, { fmt } from './Plot';
import TrialReplay from './TrialReplay';
import Surface from './Surface';
import './style.css';

const pages = [
  ['Overview', LayoutDashboard, 'workspace'],
  ['Data Explorer', Table2, 'explorer'],
  ['Analysis Studio', ChartScatter, 'studio'],
  ['AI Assistant', Sparkles, 'assistant'],
  ['Findings', FileText, 'findings'],
];
const samples = {
  growth: {
    title: 'Biomass growth',
    name: 'synthetic_exponential_growth.csv',
    desc: '76 trials · Time and biomass',
    icon: Sprout,
    question: 'How does biomass change over time?',
  },
  spring: {
    title: 'Spring extension',
    name: 'sample.csv',
    desc: '9 trials · Mass and extension',
    icon: Activity,
    question: 'How does added mass relate to spring extension?',
  },
  influence: {
    title: 'Five-trial experiment',
    name: 'five_trials.csv',
    desc: '5 trials · A change in trend',
    icon: Crosshair,
    question: 'How much does the final trial affect the fitted slope?',
  },
};
const modes = [
  ['Scatter', ChartScatter],
  ['Line', ChartSpline],
  ['Bar', ChartColumn],
  ['Distribution', ChartNoAxesColumn],
];
function route() {
  return pages.find((p) => p[2] === location.hash.slice(1))?.[0] || 'Overview';
}
async function api(action, body, signal) {
  const r = await fetch('/api/' + action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  const data = await r.json().catch(() => ({ error: 'The analysis server is unavailable. Please try again.' }));
  if (!r.ok || data.error) throw new Error(data.error || 'The request failed. Please try again.');
  return data;
}
function Modal({ title, close, children }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current.showModal();
  }, []);
  return (
    <dialog
      aria-label={title}
      ref={ref}
      onCancel={close}
      onClick={(e) => {
        if (e.target === ref.current) close();
      }}
    >
      <div className="dialog-head">
        <h2>{title}</h2>
        <button className="icon-btn" aria-label="Close dialog" onClick={close}>
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function SampleList({ load, loading }) {
  return (
    <div className="sample-list">
      {Object.entries(samples).map(([key, s]) => (
        <button key={key} disabled={loading} onClick={() => load(key)}>
          <i className="tile teal">
            <s.icon size={20} />
          </i>
          <span>
            <b>{s.title}</b>
            <small>{s.desc}</small>
          </span>
          <ChevronRight size={16} />
        </button>
      ))}
    </div>
  );
}
function Pane({ title, icon: Icon, action, children, sub }) {
  return (
    <section className="pane">
      <div className="pane-head">
        <div>
          <h2>
            {Icon && <Icon size={18} />} {title}
          </h2>
          {sub && <p>{sub}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function AxisSelect({ numeric, x, y, change }) {
  return (
    <div className="axis-select">
      {[
        ['Independent variable', x, 'x'],
        ['Dependent variable', y, 'y'],
      ].map(([label, value, axis]) => (
        <label key={axis}>
          {label}
          <select value={value} disabled={numeric.length < 2} onChange={(e) => change(axis, e.target.value)}>
            {!value && <option value="">Choose a variable</option>}
            {numeric.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
function Table({ headers, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((c, i) => (
              <th key={i}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j}>{v ?? <span className="muted">Missing</span>}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Explorer({ d, axis, go }) {
  const [query, search] = useState(''),
    [filter, setFilter] = useState('All rows'),
    [page, setPage] = useState(0);
  const rows = d.rows
    .map((r, i) => [i + 1, ...r])
    .filter(
      (r) =>
        (filter === 'All rows' || r.slice(1).some((v) => v == null || v === '∞' || v === '−∞')) &&
        (!query ||
          r.some((v) =>
            String(v ?? 'Missing')
              .toLowerCase()
              .includes(query.toLowerCase()),
          )),
    );
  return (
    <>
      <Pane title="Data table" sub={d.name} action={<span className="tag">{d.rows.length} rows</span>}>
        <div className="toolbar">
          <label className="search">
            <Search size={16} />
            <input
              placeholder="Search rows…"
              aria-label="Search rows"
              value={query}
              onChange={(e) => {
                search(e.target.value);
                setPage(0);
              }}
            />
          </label>
          <select
            aria-label="Row filter"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setPage(0);
            }}
          >
            <option>All rows</option>
            <option>Missing or nonfinite</option>
          </select>
        </div>
        {d.columns.some((c) => c.missing + c.infinite > 0) && (
          <p className="annotation">
            Missing or nonfinite cells appear in{' '}
            {d.columns
              .filter((c) => c.missing + c.infinite)
              .map((c) => c.name)
              .join(', ')}
            . Use the row filter to inspect them.
          </p>
        )}
        <Table headers={['Trial', ...d.columns.map((c) => c.name)]} rows={rows.slice(page * 12, page * 12 + 12)} />
        <div className="pager">
          <span>
            {rows.length
              ? page * 12 + 1 + '–' + Math.min(rows.length, page * 12 + 12) + ' of ' + rows.length
              : 'No matching rows'}
          </span>
          <button disabled={!page} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <button disabled={(page + 1) * 12 >= rows.length} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      </Pane>
      <Pane title="Column profile" sub="Ranges and means use finite numeric cells.">
        <Table
          headers={['Column', 'Type', 'Missing', 'Nonfinite', 'Min', 'Mean', 'Max']}
          rows={d.columns.map((c) => [
            c.name,
            c.type,
            c.missing,
            c.infinite,
            ...['min', 'mean', 'max'].map((k) => (c[k] == null ? '—' : fmt(c[k]))),
          ])}
        />
      </Pane>
      <Pane
        title="Analysis variables"
        action={
          <button className="text-btn" onClick={() => go('Analysis Studio')}>
            Open studio <ArrowRight />
          </button>
        }
      >
        {axis}
      </Pane>
    </>
  );
}
function App() {
  const [page, setPage] = useState(route),
    [mobile, setMobile] = useState(false),
    [modal, setModal] = useState(''),
    [d, setD] = useState(null),
    [x, setX] = useState(''),
    [y, setY] = useState(''),
    [excluded, setExcluded] = useState([]),
    [research, setResearch] = useState(''),
    [analysis, setAnalysis] = useState(null),
    [analysisError, setAnalysisError] = useState(''),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(''),
    [mode, setMode] = useState('Scatter'),
    [trend, setTrend] = useState(true),
    [bars, setBars] = useState(false),
    [selected, setSelected] = useState(''),
    [history, setHistory] = useState([]),
    [draft, setDraft] = useState(''),
    [asking, setAsking] = useState(false),
    [chatError, setChatError] = useState('');
  const upload = useRef(null),
    loadId = useRef(0),
    chatId = useRef(0);
  useEffect(() => {
    const nav = () => {
      setPage(route());
      setMobile(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', nav);
    return () => window.removeEventListener('hashchange', nav);
  }, []);
  function go(name) {
    location.hash = pages.find((p) => p[0] === name)[2];
    setMobile(false);
  }
  function resetChat() {
    chatId.current++;
    setHistory([]);
    setDraft('');
    setChatError('');
    setAsking(false);
  }
  async function load(source, file) {
    const id = ++loadId.current;
    setLoading(true);
    setError('');
    setModal('');
    try {
      let csv;
      if (file) {
        if (file.size > 1000000) throw new Error('Choose a CSV up to 1 MB.');
        try {
          csv = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
        } catch {
          throw new Error('Save the file as a UTF-8 CSV and upload it again.');
        }
      } else {
        const response = await fetch('/api/sample/' + source);
        if (!response.ok) throw new Error('Could not open the sample dataset.');
        csv = await response.text();
      }
      const data = await api('dataset', { csv });
      if (id !== loadId.current) return;
      const s = samples[source],
        nums = data.columns.filter((c) => c.numeric);
      setD({
        ...data,
        csv,
        name: file?.name || s.name,
        title: file ? file.name.replace(/\.csv$/i, '') : s.title,
        sample: !file,
      });
      setX(nums[0]?.name || '');
      setY(nums[1]?.name || '');
      setExcluded([]);
      setSelected('');
      setAnalysis(null);
      setMode('Scatter');
      setTrend(true);
      setBars(false);
      setResearch(s?.question || '');
      resetChat();
    } catch (e) {
      if (id === loadId.current) setError(e.message);
    } finally {
      if (id === loadId.current) setLoading(false);
      if (upload.current) upload.current.value = '';
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    setAnalysis(null);
    setAnalysisError('');
    if (d && x && y)
      api('analysis', { csv: d.csv, x, y, excluded }, controller.signal)
        .then((a) => {
          if (!controller.signal.aborted) setAnalysis(a);
        })
        .catch((e) => {
          if (!controller.signal.aborted) setAnalysisError(e.message);
        });
    return () => controller.abort();
  }, [d, x, y, excluded]);
  function changeAxis(axis, value) {
    if (axis === 'x') {
      if (value === y) setY(x);
      setX(value);
    } else {
      if (value === x) setX(y);
      setY(value);
    }
    setExcluded([]);
    setSelected('');
    setAnalysis(null);
    resetChat();
  }
  function exclude(row) {
    setExcluded((prev) => (prev.includes(row) ? prev.filter((i) => i !== row) : [...prev, row]));
    setAnalysis(null);
    resetChat();
  }
  async function ask(e) {
    e.preventDefault();
    const q = draft.trim();
    if (!q || asking) return;
    const id = ++chatId.current;
    setAsking(true);
    setChatError('');
    try {
      const r = await api('chat', {
        csv: d.csv,
        x,
        y,
        excluded,
        research,
        history: history.slice(-8),
        question: q,
      });
      if (id === chatId.current) {
        setHistory([...history, { role: 'user', content: q }, { role: 'assistant', content: r.answer }]);
        setDraft('');
      }
    } catch (e) {
      if (id === chatId.current) setChatError(e.message);
    } finally {
      if (id === chatId.current) setAsking(false);
    }
  }
  const updateResearch = (v) => {
    setResearch(v);
    resetChat();
  };
  const numeric = d?.columns.filter((c) => c.numeric).map((c) => c.name) || [];
  const axis = <AxisSelect {...{ numeric, x, y }} change={changeAxis} />;
  const fit = analysis?.fit,
    missing = d?.columns.reduce((t, c) => t + c.missing + c.infinite, 0) || 0;
  const cells = d ? d.rows.length * d.columns.length : 0,
    quality = cells ? fmt((100 * (cells - missing)) / cells, 4) + '%' : '—';
  const noPlot =
    analysisError ||
    (!x || !y
      ? 'Choose a dataset with at least two numeric columns for relationship analysis.'
      : 'Calculating the current selection…');
  const plot = analysis ? (
    <Plot {...{ analysis, x, y, mode, trend, bars }} />
  ) : (
    <div className="plot-empty" role="status">
      {noPlot}
    </div>
  );
  const descriptions = {
    'Data Explorer': 'Inspect measurements and choose the variables for your analysis.',
    'Analysis Studio': 'Visualize relationships and test how individual trials affect the result.',
    'AI Assistant': 'Ask questions grounded in your current dataset and calculated results.',
    Findings: 'Review the evidence and export a summary of your current analysis.',
  };
  const slug = pages.find((p) => p[0] === page)[2];
  const metrics = [
    ['Total rows', d?.rows.length, Layers3, 'teal', 'Measurements'],
    ['Variables', d?.columns.length, Columns3, 'blue', 'Dataset columns'],
    [
      'Mean response',
      d?.columns.find((c) => c.name === y)?.mean == null ? '—' : fmt(d.columns.find((c) => c.name === y).mean),
      Activity,
      'violet',
      y || 'No numeric response',
    ],
    ['Completeness', quality, CircleCheck, 'sand', 'Finite or present cells'],
  ];
  const metricsFit = [
    ['Slope', fit?.slope],
    ['Intercept', fit?.intercept],
    ['Pearson r', fit?.r],
    ['R²', fit?.r2],
  ];
  const notes = [
    ...(analysis?.warnings || []),
    'The linear fit describes association over the observed range. Causation requires evidence about the experimental design.',
  ];
  const selectedRow = Number(selected),
    original = selectedRow ? d?.rows[selectedRow - 1] : null;
  const availableRows = analysis ? [...analysis.points.map((p) => p.row), ...excluded].sort((a, b) => a - b) : [];
  const chatAnswer = history.filter((m) => m.role === 'assistant').at(-1)?.content;
  function download() {
    const text = [
      '# ' + d.title,
      'Dataset: ' + d.name,
      'Research question: ' + (research || 'Unspecified'),
      '',
      '## Computed evidence',
      'Variables: ' + d.columns.length,
      'Uploaded rows: ' + d.rows.length,
      'Completeness: ' + quality,
      'X: ' + (x || 'Unselected'),
      'Y: ' + (y || 'Unselected'),
      'Finite pairs used: ' + (analysis?.points.length ?? 0),
      'Missing/nonfinite pairs: ' + (analysis?.missing ?? 'Unavailable'),
      'Manually excluded trials: ' + (excluded.join(', ') || 'None'),
      ...metricsFit.map(([k, v]) => k + ': ' + fmt(v, 8)),
      '',
      '## Limitations',
      ...notes,
      ...(chatAnswer
        ? ['', '## AI-generated interpretation', 'Question: ' + history.at(-2).content, chatAnswer]
        : []),
    ].join('\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'EvidenceLab-findings.md';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="app">
      <input
        hidden
        ref={upload}
        type="file"
        accept=".csv,text/csv"
        aria-label="Upload CSV file"
        onChange={(e) => e.target.files[0] && load(null, e.target.files[0])}
      />
      {mobile && <button aria-label="Close navigation" className="scrim" onClick={() => setMobile(false)} />}
      <aside className={mobile ? 'sidebar open' : 'sidebar'}>
        <a href="#workspace" className="brand">
          <span>
            <FlaskConical size={23} />
          </span>
          Evidence<span className="brand-lab">Lab</span>
        </a>
        <div className="rail-caption">WORKSPACE</div>
        <nav>
          {pages.map(([name, Icon, id]) => (
            <a
              key={id}
              aria-current={page === name ? 'page' : undefined}
              href={'#' + id}
              className={page === name ? 'active' : ''}
            >
              <Icon size={18} />
              {name}
              {page === name && <span className="nav-dot" />}
            </a>
          ))}
        </nav>
        <div className="rail-bottom">
          <button className="guide" onClick={() => setModal('guide')}>
            <BookOpen size={17} />
            Workspace guide
            <ChevronRight size={14} />
          </button>
          <div className="session">
            <span className="avatar">
              <Microscope size={19} />
            </span>
            <div>
              <b>Local workspace</b>
              <small>Research session</small>
            </div>
            <i />
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="crumb">
            <button className="mobile-btn icon-btn" aria-label="Open navigation" onClick={() => setMobile(true)}>
              <Menu />
            </button>
            <PanelLeft size={16} />
            <span>Workspace</span>
            <ChevronRight size={13} />
            <b>{page}</b>
          </div>
          {d && (
            <button className="button small" onClick={() => setModal('samples')} disabled={loading}>
              <FolderOpen size={15} /> Change dataset
            </button>
          )}
        </header>
        <main>
          <div key={slug} className="page-body">
            {error && (
              <div role="alert" className="notice">
                {error}{' '}
                <button onClick={() => setError('')} aria-label="Dismiss upload error">
                  <X size={14} />
                </button>
              </div>
            )}
            {loading && (
              <div className="loading-line" role="status">
                <LoaderCircle size={15} className="spin" /> Opening dataset…
              </div>
            )}
            {!d || page === 'Overview' ? (
              <section className="hero">
                <Surface />
                <div className="hero-content">
                  <div className="hero-label">
                    <i /> RESEARCH WORKSPACE
                  </div>
                  <h1>{d ? 'Workspace overview' : 'Choose your dataset'}</h1>
                  <p>
                    {d
                      ? 'Explore your measurements and build a report from the evidence.'
                      : 'Upload your own CSV or select a sample experiment below.'}
                  </p>
                  <div className="actions">
                    {d ? (
                      <button className="button primary" onClick={() => go('Data Explorer')}>
                        <Table2 /> Explore dataset <ArrowRight />
                      </button>
                    ) : (
                      <button className="button primary" onClick={() => upload.current.click()} disabled={loading}>
                        <Upload /> Upload CSV
                      </button>
                    )}
                  </div>
                </div>
              </section>
            ) : (
              <div className="page-title">
                <div className="eyebrow">
                  <i />
                  RESEARCH WORKSPACE
                </div>
                <h1>{page}</h1>
                <p>{descriptions[page]}</p>
              </div>
            )}
            {d ? (
              <>
                {page === 'Overview' && (
                  <>
                    <div className="section-title">
                      <h2>Dataset overview</h2>
                      <span className="dataset-label">
                        <i />
                        {d.sample ? 'Sample dataset' : 'Uploaded CSV'}
                      </span>
                    </div>
                    <div className="metrics">
                      {metrics.map(([k, v, Icon, color, desc]) => (
                        <article className="metric" key={k}>
                          <div>
                            <span>{k}</span>
                            <i className={'tile ' + color}>
                              <Icon size={16} />
                            </i>
                          </div>
                          <strong>{v}</strong>
                          <small>{desc}</small>
                        </article>
                      ))}
                    </div>
                    <div className="overview-grid">
                      <Pane
                        title="Relationship preview"
                        sub={x && y ? y + ' by ' + x : 'Select numeric variables to plot.'}
                        action={
                          <button
                            className="icon-btn studio-link"
                            aria-label="Open Analysis Studio"
                            onClick={() => go('Analysis Studio')}
                          >
                            <ArrowUpRight size={17} />
                          </button>
                        }
                      >
                        {analysis ? <Plot {...{ analysis, x, y }} /> : plot}
                        <div className="pane-foot">
                          <span>
                            <i className="dot" /> {analysis?.points.length ?? 0} finite pairs
                          </span>
                          <button className="text-btn" onClick={() => go('Analysis Studio')}>
                            Analysis Studio <ArrowRight />
                          </button>
                        </div>
                      </Pane>
                      <div className="stack">
                        <Pane title="Active dataset" icon={Database}>
                          <div className="file-card">
                            <i className="file-icon">
                              <FileSpreadsheet size={20} />
                            </i>
                            <div>
                              <b>{d.title}</b>
                              <small>{d.name}</small>
                            </div>
                          </div>
                          <dl className="details">
                            <div>
                              <dt>Source</dt>
                              <dd>{d.sample ? 'Sample library' : 'CSV upload'}</dd>
                            </div>
                            <div>
                              <dt>Missing / nonfinite cells</dt>
                              <dd>{missing}</dd>
                            </div>
                          </dl>
                          <button className="text-btn" onClick={() => setModal('samples')}>
                            Change dataset <ArrowRight />
                          </button>
                        </Pane>
                        <Pane title="Research question" icon={BookOpen}>
                          <label className="sr-only" htmlFor="rq">
                            Research question
                          </label>
                          <textarea
                            id="rq"
                            rows={2}
                            maxLength={500}
                            value={research}
                            onChange={(e) => updateResearch(e.target.value)}
                            placeholder="What do you want to investigate?"
                          />
                          <small className="field-note">Used as context for your assistant and report.</small>
                        </Pane>
                      </div>
                    </div>
                  </>
                )}
                {page === 'Data Explorer' && <Explorer key={d.csv} {...{ d, axis, go }} />}
                {page === 'Analysis Studio' && (
                  <>
                    <Pane title="Chart controls" icon={SlidersHorizontal}>
                      {axis}
                      <div className="chart-tools">
                        <div className="segments">
                          {modes.map(([m, I]) => (
                            <button aria-pressed={mode === m} key={m} onClick={() => setMode(m)}>
                              <I size={15} />
                              {m}
                            </button>
                          ))}
                        </div>
                        {(mode === 'Scatter' || mode === 'Line') && (
                          <label className="check">
                            <input type="checkbox" checked={trend} onChange={(e) => setTrend(e.target.checked)} />
                            Trendline
                          </label>
                        )}
                        {(mode === 'Bar' || mode === 'Line') && (
                          <label className="check">
                            <input type="checkbox" checked={bars} onChange={(e) => setBars(e.target.checked)} />
                            Sample SD
                          </label>
                        )}
                      </div>
                    </Pane>
                    <Pane
                      title={mode === 'Distribution' ? 'Distribution of ' + y : (y || 'Y') + ' by ' + (x || 'X')}
                      sub={
                        mode === 'Line' || mode === 'Bar'
                          ? 'Means grouped by exact X. Sample SD requires repeated trials.'
                          : 'Each included trial contributes to the analysis.'
                      }
                    >
                      {plot}
                    </Pane>
                    {analysis && (
                      <>
                        <Pane
                          title="Linear relationship"
                          sub={analysis.points.length + ' included trials · Ordinary least squares'}
                        >
                          <div className="fit-metrics">
                            {metricsFit.map(([k, v]) => (
                              <div key={k}>
                                <small>{k}</small>
                                <b>{fmt(v)}</b>
                              </div>
                            ))}
                          </div>
                          {analysis.warnings.map((n) => (
                            <p className="annotation" key={n}>
                              {n}
                            </p>
                          ))}
                        </Pane>
                        <Pane
                          title="Trial inspection"
                          sub="Review any trial and exclude it from this analysis. Restore it at any time."
                        >
                          <p className="annotation">
                            Y values beyond 1.5 × IQR from the quartiles are flagged using all finite pairs. An
                            unusual trial can still be valid.
                          </p>
                          <div className="toolbar">
                            <select
                              aria-label="Inspect trial"
                              value={selected}
                              onChange={(e) => setSelected(e.target.value)}
                            >
                              <option value="">Choose a trial</option>
                              {availableRows.map((i) => (
                                <option key={i} value={i}>
                                  Trial {i}
                                  {analysis.flags.includes(i) ? ' · IQR flag' : ''}
                                  {excluded.includes(i) ? ' · Excluded' : ''}
                                </option>
                              ))}
                            </select>
                            <button className="button" disabled={!selected} onClick={() => exclude(selectedRow)}>
                              {excluded.includes(selectedRow) ? 'Restore trial' : 'Exclude trial'}
                            </button>
                          </div>
                          {original && (
                            <p>
                              {x} = {fmt(original[d.columns.findIndex((c) => c.name === x)])} · {y} ={' '}
                              {fmt(original[d.columns.findIndex((c) => c.name === y)])}
                            </p>
                          )}
                          {excluded.length > 0 && (
                            <p className="annotation">
                              Slope with all finite trials: {fmt(analysis.original_slope)} · Current slope:{' '}
                              {fmt(fit?.slope)}
                            </p>
                          )}
                          <small className="field-note">
                            Flagged trials · {analysis.flags.join(', ') || 'None'}
                            <br />
                            Manually excluded · {excluded.join(', ') || 'None'}
                          </small>
                        </Pane>
                        <TrialReplay {...{ api, csv: d.csv, x, y, excluded, analysis }} />
                        <details className="pane">
                          <summary>Grouped statistics</summary>
                          <Table
                            headers={[x, 'Mean ' + y, 'Sample SD', 'Trials']}
                            rows={analysis.groups.map((g) => [g.x, fmt(g.mean), fmt(g.sd), g.count])}
                          />
                        </details>
                      </>
                    )}
                  </>
                )}
                {page === 'AI Assistant' && (
                  <Pane
                    title="Research conversation"
                    icon={Sparkles}
                    sub={d.title + ' · ' + (x && y ? x + ' / ' + y : 'Dataset overview')}
                  >
                    {research && (
                      <div className="question-context">
                        <BookOpen size={16} />
                        <span>{research}</span>
                      </div>
                    )}
                    {!history.length && (
                      <div className="chat-intro">
                        <i className="tile teal">
                          <Sparkles />
                        </i>
                        <h3>What would you like to investigate?</h3>
                        <p>Choose a question or write your own.</p>
                      </div>
                    )}
                    <div className="messages" aria-live="polite">
                      {history.map((m, i) => (
                        <article key={i} className={'message ' + m.role}>
                          <b>{m.role === 'user' ? 'You' : 'AI-generated interpretation'}</b>
                          <p>{m.content}</p>
                        </article>
                      ))}
                    </div>
                    <div className="suggestions">
                      {[
                        'What does the fitted slope tell me?',
                        'What limits my conclusion?',
                        'How could I improve this experiment?',
                      ].map((q) => (
                        <button key={q} disabled={asking} onClick={() => setDraft(q)}>
                          {q}
                          <ArrowUpRight size={13} />
                        </button>
                      ))}
                    </div>
                    <form className="composer" onSubmit={ask}>
                      <label htmlFor="chat">Your question</label>
                      <textarea
                        id="chat"
                        rows={3}
                        value={draft}
                        maxLength={1000}
                        disabled={asking}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder="Ask about your dataset or findings…"
                      />
                      <div className="composer-foot">
                        <small>
                          Sending shares your question, selected summary and recent conversation with OpenRouter.
                        </small>
                        <button className="button primary" disabled={asking || !draft.trim()}>
                          {asking ? <LoaderCircle size={16} className="spin" /> : <Send size={15} />}{' '}
                          {asking ? 'Asking…' : 'Send question'}
                        </button>
                      </div>
                    </form>
                    {chatError && (
                      <p className="notice" role="alert">
                        {chatError}
                      </p>
                    )}
                  </Pane>
                )}
                {page === 'Findings' && (
                  <>
                    <Pane
                      title="Research summary"
                      icon={FileText}
                      sub={d.title}
                      action={
                        <button className="button" onClick={download} disabled={Boolean(x && y && !analysis)}>
                          <Download size={16} />
                          Export summary
                        </button>
                      }
                    >
                      <div className="question-context">
                        <BookOpen size={17} />
                        {research || 'Add a research question on the overview.'}
                      </div>
                      <h3>Computed evidence</h3>
                      <p className="annotation">
                        {analysis
                          ? analysis.points.length +
                            ' of ' +
                            d.rows.length +
                            ' trials included · ' +
                            analysis.missing +
                            ' incomplete pairs · ' +
                            excluded.length +
                            ' manually excluded'
                          : noPlot}
                      </p>
                      <div className="fit-metrics">
                        {metricsFit.map(([k, v]) => (
                          <div key={k}>
                            <small>{k}</small>
                            <b>{fmt(v)}</b>
                          </div>
                        ))}
                      </div>
                    </Pane>
                    <Pane title="Visual evidence" sub={y + ' by ' + x}>
                      {plot}
                    </Pane>
                    <Pane title="Interpretation and limitations">
                      {fit && (
                        <p>
                          The fitted line predicts a {fmt(Math.abs(fit.slope))}-unit{' '}
                          {fit.slope < 0 ? 'decrease' : fit.slope > 0 ? 'increase' : 'change'} in {y} per unit
                          increase in {x} within the observed range.
                        </p>
                      )}
                      {notes.map((n) => (
                        <p className="annotation" key={n}>
                          {n}
                        </p>
                      ))}
                    </Pane>
                    <Pane title="AI-generated interpretation" icon={Sparkles}>
                      {chatAnswer ? (
                        <p className="preserve">{chatAnswer}</p>
                      ) : (
                        <button className="text-btn" onClick={() => go('AI Assistant')}>
                          Ask the assistant about your results <ArrowRight />
                        </button>
                      )}
                    </Pane>
                  </>
                )}
              </>
            ) : (
              <div className="start-samples">
                <Pane title="Sample datasets">
                  <SampleList load={load} loading={loading} />
                </Pane>
              </div>
            )}
          </div>
        </main>
      </div>
      {modal === 'samples' && (
        <Modal title="Change dataset" close={() => setModal('')}>
          <p>Choose a sample or upload a CSV to start a new analysis.</p>
          <SampleList load={load} loading={loading} />
          <button
            className="button"
            onClick={() => {
              setModal('');
              upload.current.click();
            }}
          >
            <Upload size={15} />
            Upload your own CSV
          </button>
        </Modal>
      )}
      {modal === 'guide' && (
        <Modal title="Workspace guide" close={() => setModal('')}>
          <ol className="guide-list">
            <li>Open a sample or upload a UTF-8 CSV, up to 1 MB, 5,000 rows and 100 columns.</li>
            <li>Inspect column quality in Data Explorer and select two numeric variables.</li>
            <li>Compare charts in Analysis Studio and inspect the effect of excluding a trial.</li>
            <li>Send a question for an AI interpretation or export computed results from Findings.</li>
          </ol>
          <p className="field-note">
            Your workspace lives in this tab. Opening a dataset starts a new analysis. Refreshing returns to
            dataset selection.
          </p>
        </Modal>
      )}
    </div>
  );
}
createRoot(document.getElementById('root')).render(<App />);
