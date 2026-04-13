"use client";
import { useState, useEffect } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import "./AnalyticsDashboard.css";
import {API_URL} from "../api.ts";

const TOOL_COLORS = {
  vector_search: "#1f77b4",
  keyword_search: "#ff7f0e",
  character_lookup: "#2ca02c",
  summary: "#d62728",
  default: "#9467bd"
};

const getToolColor = (toolName) => TOOL_COLORS[toolName] || TOOL_COLORS.default;

export default function AnalyticsDashboard({ onClose }) {
  const [analytics, setAnalytics] = useState(null);
  const [messagesAnalytics, setMessagesAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionFilter, setSessionFilter] = useState("all");
  const [toolFilters, setToolFilters] = useState([]);
  const [modelFilters, setModelFilters] = useState([]);
  const [timeRange, setTimeRange] = useState("all");
  const [customFromDate, setCustomFromDate] = useState("");
  const [customToDate, setCustomToDate] = useState("");

  // Fetch analytics on mount and when filters change
  useEffect(() => {
    fetchAllAnalytics();
  }, [sessionFilter, toolFilters, modelFilters, timeRange, customFromDate, customToDate]);

  const fetchAllAnalytics = async () => {
    setLoading(true);
    try {
      let params = new URLSearchParams();
      if (sessionFilter !== "all") params.append("session_id", sessionFilter);

      // Calculate date range
      let fromDate = null;
      let toDate = null;

      if (timeRange === "7days") {
        const now = new Date();
        fromDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      } else if (timeRange === "30days") {
        const now = new Date();
        fromDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
      } else if (timeRange === "custom") {
        if (customFromDate) fromDate = new Date(customFromDate).toISOString();
        if (customToDate) toDate = new Date(customToDate).toISOString();
      }

      if (fromDate) params.append("from", fromDate);
      if (toDate) params.append("to", toDate);

      const [analyticsRes, messagesRes] = await Promise.all([
        fetch(`${API_URL}/analytics?${params}`),
        fetch(`${API_URL}/messages-analytics?${params}`)
      ]);

      if (analyticsRes.ok) {
        const data = await analyticsRes.json();
        setAnalytics(data);
      }

      if (messagesRes.ok) {
        const data = await messagesRes.json();
        setMessagesAnalytics(data);
      }
    } catch (err) {
      console.error("Failed to fetch analytics", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToolFilterToggle = (toolName) => {
    setToolFilters(prev =>
      prev.includes(toolName)
        ? prev.filter(t => t !== toolName)
        : [...prev, toolName]
    );
  };

  const handleModelFilterToggle = (modelName) => {
    setModelFilters(prev =>
      prev.includes(modelName)
        ? prev.filter(m => m !== modelName)
        : [...prev, modelName]
    );
  };

  // Filter tool data
  const filteredToolData = analytics?.raw || [];
  const processedToolData = toolFilters.length > 0
    ? filteredToolData.filter(d => toolFilters.includes(d.tool_name))
    : filteredToolData;

  // Filter message data
  const filteredMessageData = messagesAnalytics?.raw || [];
  const processedMessageData = modelFilters.length > 0
    ? filteredMessageData.filter(d => modelFilters.includes(d.model_name))
    : filteredMessageData;

  // ===== HERO CHART: Model vs Query Answer Time =====
  const modelAvgAnswerTime = (messagesAnalytics?.models || []).map(model => {
    const modelMessages = processedMessageData.filter(d => d.model_name === model);
    const avgTime = modelMessages.length > 0
      ? modelMessages.reduce((sum, d) => sum + (d.total_time || 0), 0) / modelMessages.length
      : 0;
    return { model, avgTime: parseFloat(avgTime.toFixed(2)), count: modelMessages.length };
  }).sort((a, b) => b.avgTime - a.avgTime);

  // Tool response time
  const toolResponseTimeData = processedToolData.reduce((acc, d) => {
    const existing = acc.find(x => x.tool === d.tool_name);
    if (existing) {
      existing.time = (existing.time + d.time_taken) / 2;
      existing.count = (existing.count || 1) + 1;
    } else {
      acc.push({ tool: d.tool_name, time: d.time_taken, count: 1 });
    }
    return acc;
  }, []).sort((a, b) => b.time - a.time);

  const docsRetrievedData = processedToolData.reduce((acc, d) => {
    const existing = acc.find(x => x.tool === d.tool_name);
    if (existing) {
      existing.docs = existing.docs + (d.docs_retrieved || 0);
    } else {
      acc.push({ tool: d.tool_name, docs: d.docs_retrieved || 0 });
    }
    return acc;
  }, []).sort((a, b) => b.docs - a.docs);

  const errorRateData = (analytics?.tool_names || []).map(tool => {
    const toolDocs = processedToolData.filter(d => d.tool_name === tool);
    const errors = toolDocs.filter(d => d.error).length;
    const total = toolDocs.length;
    return {
      name: tool,
      errors,
      success: total - errors,
      total,
      errorRate: total > 0 ? (errors / total * 100).toFixed(1) : 0
    };
  });

  const toolUsageData = processedToolData.reduce((acc, d) => {
    const existing = acc.find(x => x.name === d.tool_name);
    if (existing) {
      existing.value += 1;
    } else {
      acc.push({ name: d.tool_name, value: 1 });
    }
    return acc;
  }, []).sort((a, b) => b.value - a.value);

  const responseTimeTrendData = processedToolData
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .slice(-50)
    .map((d, idx) => ({
      id: idx,
      timestamp: new Date(d.timestamp).toLocaleString(),
      tool: d.tool_name,
      time: d.time_taken
    }));

  const queryVolumeBySession = (analytics?.sessions || []).map(sessionId => {
    const count = processedToolData.filter(d => d.session_id === sessionId).length;
    return { session: sessionId.slice(0, 8), count };
  }).sort((a, b) => b.count - a.count);

  return (
    <div className="analytics-dashboard-page">
      {/* Header */}
      <div className="analytics-page-header">
        <h1>Activity Dashboard</h1>
        <button className="analytics-back-btn" onClick={onClose}>← Return</button>
      </div>

      {/* Filters */}
      <div className="analytics-filters">
        <div className="filter-group">
          <label>Session</label>
          <select value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)}>
            <option value="all">All Sessions</option>
            {(analytics?.sessions || []).map(s => (
              <option key={s} value={s}>{s.slice(0, 8)}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Tools</label>
          <div className="tool-checkboxes">
            {(analytics?.tool_names || []).map(tool => (
              <label key={tool} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={toolFilters.includes(tool)}
                  onChange={() => handleToolFilterToggle(tool)}
                />
                <span>{tool}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <label>Models</label>
          <div className="tool-checkboxes">
            {(messagesAnalytics?.models || []).map(model => (
              <label key={model} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={modelFilters.includes(model)}
                  onChange={() => handleModelFilterToggle(model)}
                />
                <span>{model}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <label>Time Range</label>
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
            <option value="all">All Time</option>
            <option value="7days">Last 7 Days</option>
            <option value="30days">Last 30 Days</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        {timeRange === "custom" && (
          <>
            <div className="filter-group">
              <label>From</label>
              <input
                type="datetime-local"
                value={customFromDate}
                onChange={(e) => setCustomFromDate(e.target.value)}
              />
            </div>
            <div className="filter-group">
              <label>To</label>
              <input
                type="datetime-local"
                value={customToDate}
                onChange={(e) => setCustomToDate(e.target.value)}
              />
            </div>
          </>
        )}
      </div>

      {/* Hero Chart: Model Answer Time */}
      <div className="chart-card hero-chart">
        <h3>Query Answer Time by Model</h3>
        {modelAvgAnswerTime.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={modelAvgAnswerTime}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
              <XAxis dataKey="model" fontSize={12} />
              <YAxis fontSize={12} label={{ value: "Avg Time (s)", angle: -90, position: "insideLeft" }} />
              <Tooltip formatter={(value) => value.toFixed(2)} />
              <Bar dataKey="avgTime" fill="#1f77b4" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
            No data available
          </div>
        )}
      </div>

      {/* Charts Grid */}
      <div className="analytics-charts-grid">
        {/* Tool Response Time */}
        <div className="chart-card">
          <h3>Response Time by Tool (ms)</h3>
          {toolResponseTimeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={toolResponseTimeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
                <XAxis dataKey="tool" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(value) => value.toFixed(2)} />
                <Bar dataKey="time" fill="#1f77b4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>

        {/* Docs Retrieved */}
        <div className="chart-card">
          <h3>Documents Retrieved by Tool</h3>
          {docsRetrievedData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={docsRetrievedData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
                <XAxis dataKey="tool" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="docs" fill="#ff7f0e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>

        {/* Error Rate */}
        <div className="chart-card">
          <h3>Success vs Error Rate</h3>
          {errorRateData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={errorRateData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
                <XAxis dataKey="name" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="success" fill="#2ca02c" radius={[4, 4, 0, 0]} />
                <Bar dataKey="errors" fill="#d62728" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>

        {/* Tool Usage Frequency */}
        <div className="chart-card">
          <h3>Tool Usage Frequency</h3>
          {toolUsageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={toolUsageData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {toolUsageData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={getToolColor(entry.name)} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>

        {/* Response Time Trend */}
        <div className="chart-card chart-card-wide">
          <h3>Response Time Trend</h3>
          {responseTimeTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={responseTimeTrendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
                <XAxis dataKey="timestamp" fontSize={10} angle={-45} textAnchor="end" height={80} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="time"
                  stroke="#1f77b4"
                  dot={false}
                  isAnimationActive={false}
                  name="Response Time (ms)"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>

        {/* Query Volume by Session */}
        <div className="chart-card chart-card-wide">
          <h3>Query Volume by Session</h3>
          {queryVolumeBySession.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={queryVolumeBySession}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />
                <XAxis dataKey="session" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" fill="#9467bd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 250, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary, #555)' }}>
              No data available
            </div>
          )}
        </div>
      </div>

      {/* Stats Summary */}
      <div className="analytics-stats">
        <div className="stat-item">
          <span className="stat-label">Total Tool Records</span>
          <span className="stat-value">{analytics?.total_records || 0}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Sessions</span>
          <span className="stat-value">{analytics?.sessions?.length || 0}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Tools</span>
          <span className="stat-value">{analytics?.tool_names?.length || 0}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Models</span>
          <span className="stat-value">{messagesAnalytics?.models?.length || 0}</span>
        </div>
        {processedMessageData.length > 0 && (
          <>
            <div className="stat-item">
              <span className="stat-label">Avg Answer Time</span>
              <span className="stat-value">
                {(processedMessageData.reduce((sum, d) => sum + (d.total_time || 0), 0) / processedMessageData.length).toFixed(2)}s
              </span>
            </div>
          </>
        )}
      </div>

      {/* Loading state */}
      {loading && <div className="analytics-loading">Loading analytics...</div>}
    </div>
  );
}
