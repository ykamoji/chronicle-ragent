"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import "./AnalyticsDashboard.css";

import { API_URL } from "../../api";
import { LOCAL_TIMEZONE } from "../../timezone";

const TOOL_COLORS = {
  Vector: "#6366f1",
  Keyword: "#f59e0b",
  Character: "#06b6d4",
  Summary: "#10b981",
  default: "#f59e0b"
};

const getToolColor = (toolName) => TOOL_COLORS[toolName] || TOOL_COLORS.default;

const splitWordsIntoThreeLines = (text) => {
  const words = text.split(" ");
  const chunkSize = Math.ceil(words.length / 2);

  return [
    words.slice(0, chunkSize).join(" "),
    words.slice(chunkSize, 2 * chunkSize).join(" "),
    words.slice(2 * chunkSize).join(" "),
  ];
};

const CustomTick = ({ x, y, payload }) => {
  const lines = splitWordsIntoThreeLines(payload.value);

  return (
    <text x={x} y={y} textAnchor="middle" fill="#64748b" fontSize={12}>
      {lines.map((line, index) => (
        <tspan key={index} x={x} dy={index === 0 ? 10 : 14}>
          {line}
        </tspan>
      ))}
    </text>
  );
};

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
        if (customFromDate) {
          const from = new Date(customFromDate);
          from.setSeconds(0, 0);
          fromDate = from.toISOString();
        }
        if (customToDate) {
          const to = new Date(customToDate);
          to.setSeconds(59, 999);
          toDate = to.toISOString();
        }
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
  const modelAvgAnswerTime = (messagesAnalytics?.models || [])
    .filter(model => modelFilters.length === 0 || modelFilters.includes(model))
    .map(model => {
      const modelMessages = processedMessageData.filter(d => d.model_name === model);
      const avgSecond = modelMessages.length > 0
        ? modelMessages.reduce((sum, d) => sum + (d.total_time || 0), 0) / modelMessages.length
        : 0;
      return { model, avgSecond: parseFloat(avgSecond.toFixed(2)), count: modelMessages.length };
    }).sort((a, b) => b.avgSecond - a.avgSecond);

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

  const errorRateData = (analytics?.tool_names || [])
    .filter(tool => toolFilters.length === 0 || toolFilters.includes(tool))
    .map(tool => {
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
    .map((d, idx) => ({
      idx,
      timestamp: new Date(d.timestamp).toLocaleDateString("en-US", {
        timeZone: LOCAL_TIMEZONE,
      }),
      time: d.time_taken
    }));

  const trendDateTicks = responseTimeTrendData.reduce((acc, d) => {
    if (!acc.seen.has(d.timestamp)) {
      acc.seen.add(d.timestamp);
      acc.ticks.push(d.idx);
    }
    return acc;
  }, { seen: new Set(), ticks: [] }).ticks;

  const queryVolumeBySession = (analytics?.sessions || []).map(sessionId => {
    const volume = processedToolData.filter(d => d.session_id === sessionId).length;
    return { session: analytics.session_map[sessionId], volume };
  }).sort((a, b) => b.volume - a.volume);

  const avgAnswerTime = processedMessageData.length > 0
    ? (processedMessageData.reduce((sum, d) => sum + (d.total_time || 0), 0) / processedMessageData.length).toFixed(2)
    : 0;

  return (
    <div className="adp-root">
      {/* Header */}
      <div className="adp-header">
        <div className="adp-logo" onClick={() => router.push('/')}>
          <div className="adp-logo-dot" />
          <span>Chronicle</span>
        </div>
        <h1>Activity Dashboard</h1>
        <button className="adp-back-btn" onClick={() => router.back()}>← Return</button>
      </div>

      {/* Horizontal Filter Bar */}
      <div className="adp-filter-bar">

        <div className="adp-filter-level">

          <div className="adp-filter-group">
            <span className="adp-filter-label">Session</span>
            <select className="adp-filter-select" value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)}>
              <option value="all">All Sessions</option>
              {Object.entries(analytics?.session_map || []).map(([sessionId, label]) => (
                <option key={sessionId} value={sessionId}>{label}</option>
              ))}
            </select>
          </div>

          <div className="adp-filter-divider" />

          <div className="adp-filter-group">
            <span className="adp-filter-label">Tools</span>
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

          <div className="adp-filter-divider" />
          <div className="adp-filter-group">
            <span className="adp-filter-label">Models</span>
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
        </div>

        <div className="adp-filter-level">
          <div className="adp-filter-group">
            <div className="adp-filter-group">
              <span className="adp-filter-label">Time</span>
              <select className="adp-filter-select" value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
                <option value="all">All Time</option>
                <option value="7days">Last 7 Days</option>
                <option value="30days">Last 30 Days</option>
                <option value="custom">Custom</option>
              </select>
              {timeRange === "custom" && (
                <>
                  <div className="adp-filter-divider" />
                  <div className="adp-filter-group">
                    <span className="adp-filter-label">From</span>
                    <input type="datetime-local" className="adp-filter-input" value={customFromDate} onChange={(e) => setCustomFromDate(e.target.value)} />
                  </div>
                  <div className="adp-filter-group">
                    <span className="adp-filter-label">To</span>
                    <input type="datetime-local" className="adp-filter-input" value={customToDate} onChange={(e) => setCustomToDate(e.target.value)} />
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="adp-body">
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
            <div className="adp-section-label" onClick={() => toggleSection('agentPerformance')}>Agent Performance</div>
            <button
              className="adp-section-toggle"
              aria-label="Toggle Agent Performance section"
            >
            </button>
          </div>
          {!collapsedSections.agentPerformance && (
            <div className="adp-hero-chart">
              {modelAvgAnswerTime.length > 0 ? (
                <div className="adp-chart-card">
                  <h3>Query Response Time</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={modelAvgAnswerTime}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                      <XAxis dataKey="model" fontSize={12} stroke="#64748b" />
                      <YAxis fontSize={12} stroke="#64748b" label={{ value: "Avg Seconds (s)", angle: -90, position: "insideLeft" }} />
                      <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                      <Bar dataKey="avgSecond" fill="#6366f1" radius={0} barSize={30} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="adp-empty">
                  <span>No data available</span>
                </div>
              )}
              {queryVolumeBySession.length > 0 ? (
                <div className="adp-chart-card">
                  <h3>Query Volume</h3>
                  <ResponsiveContainer width="100%" height={330}>
                    <BarChart data={queryVolumeBySession}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
                      <XAxis dataKey="session" fontSize={12} stroke="#64748b" height={60} textAnchor="middle" tick={<CustomTick />} />
                      <YAxis fontSize={12} stroke="#64748b" label={{ value: "Volume", angle: -90, position: "insideLeft" }} />
                      <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '8px' }} />
                      <Bar dataKey="volume" fill="#8b5cf6" radius={0} barSize={30} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="adp-empty"><span>No data</span></div>
              )}
            </div>
          )}

          {/* Tool Metrics Section */}
          <div className="adp-section-header">
            <div className="adp-section-label" onClick={() => toggleSection('toolMetrics')}>Tool Metrics</div>
            <button
              className="adp-section-toggle"
              aria-label="Toggle Tool Metrics section"
            >
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
            <div className="adp-section-label" onClick={() => toggleSection('trends')}>Trends</div>
            <button
              className="adp-section-toggle"
              aria-label="Toggle Trends section"
            >
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
                      <XAxis
                        dataKey="idx"
                        type="number"
                        domain={[0, responseTimeTrendData.length - 1]}
                        ticks={trendDateTicks}
                        tickFormatter={(idx) => responseTimeTrendData[idx]?.timestamp ?? ''}
                        fontSize={10}
                        angle={-45}
                        textAnchor="end"
                        height={80}
                        stroke="#64748b"
                      />
                      <YAxis fontSize={12} stroke="#64748b" label={{ value: "Res Time", angle: -90, position: "insideLeft" }} />
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
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
