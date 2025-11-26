import React, { useEffect, useState } from 'react';
import io from 'socket.io-client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, AlertTriangle, Heart, Zap } from 'lucide-react';
import './Dashboard.css';

// Connect to the Core Service (port 8000)
const socket = io('http://localhost:8000', {
  transports: ['websocket', 'polling']
});

const Dashboard = () => {
  const [connected, setConnected] = useState(false);
  const [currentData, setCurrentData] = useState(null);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    socket.on('connect', () => {
      setConnected(true);
      console.log('Connected to WebSocket');
    });

    socket.on('disconnect', () => {
      setConnected(false);
      console.log('Disconnected from WebSocket');
    });

    socket.on('new_measurement', (data) => {
      setCurrentData(data);
      setHistory(prev => {
        const newHistory = [...prev, { ...data, time: new Date(data.measured_at).toLocaleTimeString() }];
        return newHistory.slice(-20); // Keep last 20 points
      });
    });

    socket.on('alert', (alert) => {
      setAlerts(prev => [alert, ...prev].slice(0, 5)); // Keep last 5 alerts
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('new_measurement');
      socket.off('alert');
    };
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'CRITICAL': return '#ef4444'; // Red
      case 'WARNING': return '#f59e0b'; // Orange
      default: return '#10b981'; // Green
    }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>
          <Activity className="icon" />
          Health Monitor
        </h1>
        <div className={`status-badge ${connected ? 'online' : 'offline'}`}>
          {connected ? 'System Online' : 'Connecting...'}
        </div>
      </header>

      <div className="stats-grid">
        {/* Heart Rate Card */}
        <div className="stat-card">
          <div className="stat-header">
            <Heart className="stat-icon" color="#ef4444" />
            <span>Heart Rate</span>
          </div>
          <div className="stat-value">
            {currentData ? currentData.heart_rate : '--'}
            <span className="unit">BPM</span>
          </div>
        </div>

        {/* Status Card */}
        <div className="stat-card" style={{ borderColor: currentData ? getStatusColor(currentData.status) : '#333' }}>
          <div className="stat-header">
            <Activity className="stat-icon" color={currentData ? getStatusColor(currentData.status) : '#fff'} />
            <span>Status</span>
          </div>
          <div className="stat-value" style={{ color: currentData ? getStatusColor(currentData.status) : '#fff' }}>
            {currentData ? currentData.status : '--'}
          </div>
        </div>

        {/* Inactivity Card */}
        <div className="stat-card">
          <div className="stat-header">
            <Zap className="stat-icon" color="#f59e0b" />
            <span>Inactivity</span>
          </div>
          <div className="stat-value">
            {currentData ? currentData.inactivity_seconds : '--'}
            <span className="unit">sec</span>
          </div>
        </div>
      </div>

      <div className="main-content">
        <div className="chart-section">
          <h2>Live Heart Rate</h2>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="time" stroke="#888" />
                <YAxis domain={[40, 160]} stroke="#888" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Line
                  type="monotone"
                  dataKey="heart_rate"
                  stroke="#ef4444"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 8 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="alerts-section">
          <h2>Recent Alerts</h2>
          <div className="alerts-list">
            {alerts.length === 0 ? (
              <div className="no-alerts">No active alerts</div>
            ) : (
              alerts.map((alert, idx) => (
                <div key={idx} className="alert-item">
                  <AlertTriangle className="alert-icon" />
                  <div className="alert-content">
                    <span className="alert-msg">{alert.message}</span>
                    <span className="alert-time">{new Date(alert.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
