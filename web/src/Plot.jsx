import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Scatter,
  Line,
  BarChart,
  Bar,
  ErrorBar,
} from 'recharts';

export const fmt = (n, digits = 4) =>
  n == null
    ? 'Undefined'
    : Number(n.toPrecision(digits)).toLocaleString('en-US', { maximumSignificantDigits: digits });
const teal = '#168e79';
const orange = '#c87a42';
const axis = { axisLine: false, tickLine: false, tick: { fill: '#6a7b80', fontSize: 11 }, tickMargin: 8 };

function Readout({ active, payload, x, y, mode }) {
  const d = payload?.[0]?.payload;
  if (!active || !d) return null;
  return (
    <div className="readout">
      <b>{d.row ? 'Trial ' + d.row : mode === 'Distribution' ? 'Distribution bin' : 'Group summary'}</b>
      {mode === 'Distribution' ? (
        <>
          <span>
            {y} · {fmt(d.low)} – {fmt(d.high)}
          </span>
          <span>{d.count} trials</span>
        </>
      ) : (
        <>
          <span>
            {x} · {fmt(d.x)}
          </span>
          <span>
            {y} · {fmt(d.y ?? d.mean)}
          </span>
          {d.count != null && (
            <span>
              {d.count} trials · SD {fmt(d.sd)}
            </span>
          )}
        </>
      )}
    </div>
  );
}

export default function Plot({ analysis, x, y, mode = 'Scatter', trend = true, bars = false, domain }) {
  if (!analysis?.points.length)
    return <div className="plot-empty">Choose two numeric variables with finite measurements to see a chart.</div>;
  const xDomain = domain
    ? [Math.min(...domain.map((p) => p.x)), Math.max(...domain.map((p) => p.x))]
    : ['auto', 'auto'];
  const yDomain = domain
    ? [Math.min(...domain.map((p) => p.y)), Math.max(...domain.map((p) => p.y))]
    : ['auto', 'auto'];
  const groups = analysis.groups;
  const bins = analysis.histogram.map((d) => ({ ...d, bin: fmt(d.low, 3) }));
  const distribution = mode === 'Distribution',
    grouped = mode === 'Bar' || mode === 'Line';
  const tooltip = (
    <Tooltip
      isAnimationActive={false}
      cursor={{ stroke: '#afc5c0', strokeDasharray: '3 4', fill: '#e9f4ef' }}
      content={<Readout x={x} y={y} mode={mode} />}
    />
  );
  const grid = <CartesianGrid stroke="#e5edeb" strokeDasharray="3 4" vertical={false} />;
  const margins = { left: 1, right: 18, top: 14, bottom: 4 };
  let chart;
  if (mode === 'Bar' || distribution) {
    chart = (
      <BarChart data={distribution ? bins : groups} margin={margins}>
        {grid}
        <XAxis {...axis} dataKey={distribution ? 'bin' : 'x'} minTickGap={20} />
        <YAxis {...axis} width={48} />
        {tooltip}
        <Bar dataKey={distribution ? 'count' : 'mean'} fill={teal} radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {bars && !distribution && <ErrorBar dataKey="sd" width={5} stroke="#354b52" />}
        </Bar>
      </BarChart>
    );
  } else {
    chart = (
      <ComposedChart margin={margins} data={grouped ? groups : analysis.points}>
        {grid}
        <XAxis {...axis} type="number" dataKey="x" domain={xDomain} allowDuplicatedCategory={false} />
        <YAxis {...axis} type="number" domain={yDomain} width={48} />
        {tooltip}
        {grouped ? (
          <Line dataKey="mean" stroke={teal} strokeWidth={2.3} dot={{ r: 3 }} isAnimationActive={false}>
            {bars && <ErrorBar dataKey="sd" width={4} />}
          </Line>
        ) : (
          <Scatter dataKey="y" fill={teal} fillOpacity={0.8} isAnimationActive={false} />
        )}
        {trend && analysis.fit && (
          <Line
            data={analysis.fit.line}
            dataKey="y"
            name="Linear fit"
            stroke={orange}
            strokeDasharray="6 5"
            dot={false}
            activeDot={false}
            tooltipType="none"
            isAnimationActive={false}
          />
        )}
      </ComposedChart>
    );
  }
  const showFit = trend && analysis.fit && !distribution && mode !== 'Bar';
  return (
    <figure className="plot">
      <figcaption>{distribution ? 'Trial count' : grouped ? 'Mean ' + y : y}</figcaption>
      <div
        className="chart-area"
        role="img"
        aria-label={mode + ' plot of ' + y + (distribution ? '' : ' by ' + x)}
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          {chart}
        </ResponsiveContainer>
      </div>
      <div className="axis-title">{distribution ? y + ' · bin lower bound' : x}</div>
      <div className="legend">
        <span>
          <i />
          {distribution ? 'Frequency' : grouped ? 'Group mean' : 'Observed trials'}
        </span>
        {showFit && (
          <span>
            <i className="dash" />
            Linear fit
          </span>
        )}
        {bars && grouped && <span>±1 sample SD</span>}
      </div>
    </figure>
  );
}
