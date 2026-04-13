"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import "./AnalyticsDashboard.css";

const API_URL = "";

const TOOL_COLORS = {
  vector_search: "#6366f1",
  keyword_search: "#8b5cf6",
  character_lookup: "#06b6d4",
  summary: "#10b981",
  default: "#f59e0b"
};

const getToolColor = (toolName) => TOOL_COLORS[toolName] || TOOL_COLORS.default;

export default function AnalyticsDashboard() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState(null);
  const [messagesAnalytics, setMessagesAnalytics] = useState(null);
  const [sessionFilter, setSessionFilter] = useState("all");
  const [toolFilters, setToolFilters] = useState([]);
  const [modelFilters, setModelFilters] = useState([]);
  const [timeRange, setTimeRange] = useState("all");
  const [customFromDate, setCustomFromDate] = useState("");
  const [customToDate, setCustomToDate] = useState("");
  const [collapsedSections, setCollapsedSections] = useState({
    agentPerformance: false,
    toolMetrics: false,
    trends: false
  });

  useEffect(() => {
    fetchAllAnalytics();
  }, [sessionFilter, toolFilters, modelFilters, timeRange, customFromDate, customToDate]);

  const fetchAllAnalytics = async () => {
    try {
      let params = new URLSearchParams();
      if (sessionFilter !== "all") params.append("session_id", sessionFilter);

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

      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
      if (messagesRes.ok) setMessagesAnalytics(await messagesRes.json());
    } catch (err) {
      console.error("Failed to fetch analytics", err);
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

  const toggleSection = (sectionName) => {
    setCollapsedSections(prev => ({
      ...prev,
      [sectionName]: !prev[sectionName]
    }));
  };

  const filteredToolData = analytics?.raw || [];
  const processedToolData = toolFilters.length > 0
    ? filteredToolData.filter(d => toolFilters.includes(d.tool_name))
    : filteredToolData;

  const filteredMessageData = messagesAnalytics?.raw || [];
  const processedMessageData = modelFilters.length > 0
    ? filteredMessageData.filter(d => modelFilters.includes(d.model_name))
    : filteredMessageData;

  // Data calculations
  const modelAvgAnswerTime = (messagesAnalytics?.models || []).map(model => {
    const modelMessages = processedMessageData.filter(d => d.model_name === model);
    const avgTime = modelMessages.length > 0
      ? modelMessages.reduce((sum, d) => sum + (d.total_time || 0), 0) / modelMessages.length
      : 0;
    return { model, avgTime: parseFloat(avgTime.toFixed(2)), count: modelMessages.length };
  }).sort((a, b) => b.avgTime - a.avgTime);

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

  const avgAnswerTime = processedMessageData.length > 0
    ? (processedMessageData.reduce((sum, d) => sum + (d.total_time || 0), 0) / processedMessageData.length).toFixed(2)
    : 0;

  return (
    <div className="adp-root">
      {/* Header */}
      <div className="adp-header">
        <div className="adp-logo">
          <div className="adp-logo-dot" />
          <span>Chronicle</span>
        </div>
        <h1>Activity Dashboard</h1>
        <button className="adp-back-btn" onClick={() => router.back()}>← Return</button>
      </div>

      <div className="adp-body">
        {/* Sidebar Filters */}
        <aside className="adp-sidebar">
          <div className="adp-filter-section">
            <label className="adp-filter-label">Session</label>
            <select className="adp-filter-select" value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)}>
              <option value="all">All Sessions</option>
              {(analytics?.sessions || []).map(s => (
                <option key={s} value={s}>{s.slice(0, 8)}</option>
              ))}
            </select>
          </div>

          <div className="adp-filter-section">
            <label className="adp-filter-label">Tools</label>
            <div className="adp-filter-pills">
              {(analytics?.tool_names || []).map(tool => (
                <button
                  key={tool}
                  className={`adp-filter-pill ${toolFilters.includes(tool) ? 'active' : ''}`}
                  onClick={() => handleToolFilterToggle(tool)}
                >
                  {tool}
                </button>
              ))}
            </div>
          </div>

          <div className="adp-filter-section">
            <label className="adp-filter-label">Models</label>
            <div className="adp-filter-pills">
              {(messagesAnalytics?.models || []).map(model => (
                <button
                  key={model}
                  className={`adp-filter-pill ${modelFilters.includes(model) ? 'active' : ''}`}
                  onClick={() => handleModelFilterToggle(model)}
                >
                  {model}
                </button>
              ))}
            </div>
          </div>

          <div className="adp-filter-section">
            <label className="adp-filter-label">Time Range</label>
            <select className="adp-filter-select" value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="all">All Time</option>
              <option value="7days">Last 7 Days</option>
              <option value="30days">Last 30 Days</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          {timeRange === "custom" && (
            <>
              <div className="adp-filter-section">
                <label className="adp-filter-label">From</label>
                <input
                  type="datetime-local"
                  className="adp-filter-input"
                  value={customFromDate}
                  onChange={(e) => setCustomFromDate(e.target.value)}
                />
              </div>
              <div className="adp-filter-section">
                <label className="adp-filter-label">To</label>
                <input
                  type="datetime-local"
                  className="adp-filter-input"
                  value={customToDate}
                  onChange={(e) => setCustomToDate(e.target.value)}
                />
              </div>
            </>
          )}
        </aside>

        {/* Main Content */}
        <main className="adp-main">
          {/* KPI Row */}
          <div className="adp-kpi-row">
            <div className="adp-kpi-card">
              <div className="adp-kpi-icon">⚡</div>
              <div>
                <div className="adp-kpi-value">{analytics?.total_records || 0}</div>
                <div className="adp-kpi-label">Total Queries</div>
              </div>
            </div>
            <div className="adp-kpi-card">
              <div className="adp-kpi-icon">🗂</div>
              <div>
                <div className="adp-kpi-value">{analytics?.sessions?.length || 0}</div>
                <div className="adp-kpi-label">Sessions</div>
              </div>
            </div>
            <div className="adp-kpi-card">
              <div className="adp-kpi-icon">🔧</div>
              <div>
                <div className="adp-kpi-value">{analytics?.tool_names?.length || 0}</div>
                <div className="adp-kpi-label">Tools Active</div>
              </div>
            </div>
            <div className="adp-kpi-card">
              <div className="adp-kpi-icon">🤖</div>
              <div>
                <div className="adp-kpi-value">{messagesAnalytics?.models?.length || 0}</div>
                <div className="adp-kpi-label">Models</div>
              </div>
            </div>
            <div className="adp-kpi-card">
              <div className="adp-kpi-icon">⏱</div>
              <div>
                <div className="adp-kpi-value">{avgAnswerTime}s</div>
                <div className="adp-kpi-label">Avg Answer Time</div>
              </div>
            </div>
          </div>

          {/* Agent Performance Section */}
          <div className="adp-section-header">
            <div className="adp-section-label">Agent Performance</div>
            <button
              className="adp-section-toggle"
              onClick={() => toggleSection('agentPerformance')}
              aria-label="Toggle Agent Performance section"
            >
              {collapsedSections.agentPerformance ? '▶' : '▼'}
            </button>
          </div>
          {!collapsedSections.agentPerformance && (
            <div className="adp-hero-chart adp-chart-card">
              <h3>Query Answer Time by Model</h3>
              {modelAvgAnswerTime.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={modelAvgAnswerTime}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="model" fontSize={12} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" label={{ value: "Avg Time (s)", angle: -90, position: "insideLeft" }} />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Bar dataKey="avgTime" fill="#6366f1" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty">
                  <span>No data available</span>
                </div>
              )}
            </div>
          )}

          {/* Tool Metrics Section */}
          <div className="adp-section-header">
            <div className="adp-section-label">Tool Metrics</div>
            <button
              className="adp-section-toggle"
              onClick={() => toggleSection('toolMetrics')}
              aria-label="Toggle Tool Metrics section"
            >
              {collapsedSections.toolMetrics ? '▶' : '▼'}
            </button>
          </div>
          {!collapsedSections.toolMetrics && (
          <div className="adp-charts-grid">
            <div className="adp-chart-card">
              <h3>Response Time by Tool</h3>
              {toolResponseTimeData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={toolResponseTimeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="tool" fontSize={12} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Bar dataKey="time" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>

            <div className="adp-chart-card">
              <h3>Documents Retrieved</h3>
              {docsRetrievedData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={docsRetrievedData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="tool" fontSize={12} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Bar dataKey="docs" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>

            <div className="adp-chart-card">
              <h3>Success vs Error Rate</h3>
              {errorRateData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={errorRateData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="name" fontSize={12} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Bar dataKey="success" fill="#10b981" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="errors" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>

            <div className="adp-chart-card">
              <h3>Tool Usage Frequency</h3>
              {toolUsageData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={toolUsageData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, value }) => `${name}: ${value}`}
                      outerRadius={70}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {toolUsageData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={getToolColor(entry.name)} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>
          </div>
          )}

          {/* Trends Section */}
          <div className="adp-section-header">
            <div className="adp-section-label">Trends</div>
            <button
              className="adp-section-toggle"
              onClick={() => toggleSection('trends')}
              aria-label="Toggle Trends section"
            >
              {collapsedSections.trends ? '▶' : '▼'}
            </button>
          </div>
          {!collapsedSections.trends && (
          <div className="adp-charts-grid">
            <div className="adp-chart-card adp-wide">
              <h3>Response Time Trend</h3>
              {responseTimeTrendData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={responseTimeTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="timestamp" fontSize={10} angle={-45} textAnchor="end" height={80} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Line
                      type="monotone"
                      dataKey="time"
                      stroke="#6366f1"
                      dot={false}
                      isAnimationActive={false}
                      name="Response Time (ms)"
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>

            <div className="adp-chart-card adp-wide">
              <h3>Query Volume by Session</h3>
              {queryVolumeBySession.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={queryVolumeBySession}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                    <XAxis dataKey="session" fontSize={12} stroke="#64748b" />
                    <YAxis fontSize={12} stroke="#64748b" />
                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>
          </div>
          )}
        </main>
      </div>
    </div>
  );
}
