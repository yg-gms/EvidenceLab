import React, { useEffect, useState } from 'react';
import Plot, { fmt } from './Plot';

export default function TrialReplay({ api, csv, x, y, excluded, analysis }) {
  const [open, setOpen] = useState(false),
    [count, setCount] = useState(1),
    [frame, setFrame] = useState(null),
    [playing, setPlaying] = useState(false),
    [error, setError] = useState('');
  const total = analysis.points.length;
  useEffect(() => {
    if (!open || !total) return;
    const controller = new AbortController();
    setFrame(null);
    setError('');
    api('analysis', { csv, x, y, excluded, first_trials: count }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setFrame(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e.message);
          setPlaying(false);
        }
      });
    return () => controller.abort();
  }, [api, csv, x, y, excluded, open, total, count]);
  useEffect(() => {
    if (!open || !playing || !frame) return;
    if (count >= total) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setCount((n) => n + 1), 850);
    return () => clearTimeout(timer);
  }, [count, total, open, playing, frame]);
  if (!total) return null;
  return (
    <details
      className="pane"
      onToggle={(e) => {
        setOpen(e.currentTarget.open);
        setPlaying(false);
      }}
    >
      <summary>Experiment replay</summary>
      <p className="annotation">
        Follow included trials in CSV order. Each frame refits the line using only the trials shown.
      </p>
      <div className="toolbar">
        <button
          className="button"
          disabled={total === 1}
          onClick={() => {
            if (!playing && count >= total) setCount(1);
            setPlaying(!playing);
          }}
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        <label>
          Trials shown{' '}
          <input
            type="range"
            min={1}
            max={total}
            value={count}
            onChange={(e) => {
              setPlaying(false);
              setCount(Number(e.target.value));
            }}
          />{' '}
          {count} / {total}
        </label>
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : frame ? (
        <>
          <Plot analysis={frame} x={x} y={y} domain={analysis.points} />
          <p className="annotation">Fitted slope · {fmt(frame.fit?.slope)}</p>
        </>
      ) : (
        <p role="status">Calculating frame…</p>
      )}
    </details>
  );
}
