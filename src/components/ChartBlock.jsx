import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart, BarChart, PieChart, AreaChart,
  Line, Bar, Pie, Area, Cell,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from 'recharts';

/**
 * Renders a chart from a JSON spec embedded in a fenced ```chart block.
 *
 * Spec shape (locked contract for the AI to emit):
 *   {
 *     "type": "line" | "bar" | "pie" | "area",
 *     "title"?: string,
 *     "data": [{ "name": "Jan", "revenue": 100, ... }, ...],
 *     "series": [{ "key": "revenue", "label": "Revenue", "color": "#fbbf24" }, ...],
 *     "xAxis"?: "name"        // ignored for pie
 *   }
 *
 * Parses the JSON inside the component (so a malformed AI output shows a
 * friendly error instead of crashing the whole note).
 */

const PALETTE = [
  '#fbbf24', '#4ade80', '#60a5fa', '#f87171',
  '#a78bfa', '#34d399', '#fb923c', '#f472b6',
];

const TICK = { fill: 'rgba(255,255,255,0.6)', fontSize: 11 };
const AXIS_LINE = { stroke: 'rgba(255,255,255,0.20)' };
const TOOLTIP_CONTENT = {
  background: 'rgba(15, 15, 18, 0.96)',
  border: '1px solid rgba(255,255,255,0.16)',
  borderRadius: '8px',
  color: 'rgba(255,255,255,0.92)',
  fontSize: '12px',
};
const TOOLTIP_LABEL = { color: 'rgba(255,255,255,0.55)', fontSize: '11px' };
const GRID_STROKE = 'rgba(255,255,255,0.07)';

function ChartError({ message }) {
  return (
    <div className="chart-error">
      <div className="chart-error-label">Chart error</div>
      <div className="chart-error-detail">{message}</div>
    </div>
  );
}

export default function ChartBlock({ source }) {
  const parsed = useMemo(() => {
    try {
      const spec = JSON.parse(source);
      // Minimal validation.
      if (!spec || typeof spec !== 'object') {
        return { error: 'spec must be a JSON object' };
      }
      const type = spec.type;
      if (!['line', 'bar', 'pie', 'area'].includes(type)) {
        return { error: `unsupported chart type "${type}"` };
      }
      if (!Array.isArray(spec.data) || spec.data.length === 0) {
        return { error: 'data must be a non-empty array' };
      }
      const series = Array.isArray(spec.series) && spec.series.length > 0
        ? spec.series
        : null;
      if (!series && type !== 'pie') {
        return { error: 'series array is required (key/label/color per series)' };
      }
      return {
        spec: {
          ...spec,
          xAxis: spec.xAxis || 'name',
          series: series || [],
        },
      };
    } catch (err) {
      return { error: `invalid JSON: ${err.message}` };
    }
  }, [source]);

  if (parsed.error) return <ChartError message={parsed.error} />;

  const { type, title, data, series, xAxis } = parsed.spec;

  const decorated = series.map((s, i) => ({
    ...s,
    color: s.color || PALETTE[i % PALETTE.length],
  }));

  let chart;
  if (type === 'line') {
    chart = (
      <LineChart data={data}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
        <XAxis dataKey={xAxis} tick={TICK} {...AXIS_LINE} />
        <YAxis tick={TICK} {...AXIS_LINE} />
        <Tooltip contentStyle={TOOLTIP_CONTENT} labelStyle={TOOLTIP_LABEL} />
        <Legend wrapperStyle={{ fontSize: '11px' }} />
        {decorated.map((s) => (
          <Line
            key={s.key}
            dataKey={s.key}
            name={s.label || s.key}
            stroke={s.color}
            strokeWidth={1.6}
            dot={false}
          />
        ))}
      </LineChart>
    );
  } else if (type === 'bar') {
    chart = (
      <BarChart data={data}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
        <XAxis dataKey={xAxis} tick={TICK} {...AXIS_LINE} />
        <YAxis tick={TICK} {...AXIS_LINE} />
        <Tooltip contentStyle={TOOLTIP_CONTENT} labelStyle={TOOLTIP_LABEL} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <Legend wrapperStyle={{ fontSize: '11px' }} />
        {decorated.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.label || s.key} fill={s.color} radius={[2, 2, 0, 0]} />
        ))}
      </BarChart>
    );
  } else if (type === 'area') {
    chart = (
      <AreaChart data={data}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
        <XAxis dataKey={xAxis} tick={TICK} {...AXIS_LINE} />
        <YAxis tick={TICK} {...AXIS_LINE} />
        <Tooltip contentStyle={TOOLTIP_CONTENT} labelStyle={TOOLTIP_LABEL} />
        <Legend wrapperStyle={{ fontSize: '11px' }} />
        {decorated.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label || s.key}
            stroke={s.color}
            fill={s.color}
            fillOpacity={0.18}
            strokeWidth={1.6}
          />
        ))}
      </AreaChart>
    );
  } else {
    // pie
    const pieKey = decorated[0]?.key || Object.keys(data[0] || {}).find((k) => k !== xAxis);
    if (!pieKey) return <ChartError message="pie chart needs at least one series key" />;
    chart = (
      <PieChart>
        <Tooltip contentStyle={TOOLTIP_CONTENT} labelStyle={TOOLTIP_LABEL} />
        <Legend wrapperStyle={{ fontSize: '11px' }} />
        <Pie data={data} dataKey={pieKey} nameKey={xAxis} outerRadius="78%" labelLine={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={decorated[i]?.color || PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
      </PieChart>
    );
  }

  return (
    <div className="chart-block">
      {title && <div className="chart-title">{title}</div>}
      {/* Parent MUST have explicit pixel height — ResponsiveContainer
          measures via ResizeObserver and collapses to 0 otherwise. */}
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
