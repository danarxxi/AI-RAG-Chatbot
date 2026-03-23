import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { historyAPI } from '../services/api';

const GUIDE_TABS = [
  { label: 'HR 가이드',  icon: '📋', path: '/chat',       type: 'hr' },
  { label: '업무 가이드', icon: '🏢', path: '/work-guide', type: 'work_guide' },
  { label: '용어 가이드', icon: '📖', path: '/glossary',   type: 'glossary' },
];

// 세션을 날짜 기준으로 그룹화
function groupSessionsByDate(sessions) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups = {};
  sessions.forEach(s => {
    const d = new Date(s.created_at);
    d.setHours(0, 0, 0, 0);
    let label;
    if (d.getTime() === today.getTime()) {
      label = '오늘';
    } else if (d.getTime() === yesterday.getTime()) {
      label = '어제';
    } else {
      label = d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
    }
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  });
  return groups;
}

function HistoryPanel({ serviceType, onNewChat, activeSessionId, onSelectSession, refreshKey, isMobileOpen, onToggleMobile, onMobileClose }) {
  const router = useRouter();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    fetchSessions();
  }, [serviceType, refreshKey]);

  const fetchSessions = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await historyAPI.getSessions(serviceType);
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('대화 기록 로드 실패:', err);
      setError('대화 기록을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const groupedSessions = groupSessionsByDate(sessions);

  return (
    <>
      {isMobileOpen && <div className="history-overlay" onClick={onMobileClose} />}
      <div className={`history-panel${isMobileOpen ? ' mobile-open' : ''}`}>
        <div className="history-mobile-tab" onClick={onToggleMobile}>
          <span className="history-mobile-arrow">{isMobileOpen ? '◀' : '▶'}</span>
        </div>
      <div className="guide-tabs">
        {GUIDE_TABS.map(tab => (
          <button
            key={tab.type}
            className={`guide-tab${serviceType === tab.type ? ' active' : ''}`}
            onClick={() => router.push(tab.path)}
          >
            <span className="guide-tab-icon">{tab.icon}</span>
            <span className="guide-tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="history-panel-header">
        <span className="history-panel-title">대화 기록</span>
        <button className="history-new-chat-btn" onClick={onNewChat}>+ 새 대화</button>
      </div>

      <div className="history-panel-body">
        {error && <div className="history-error">{error}</div>}

        {loading ? (
          <div className="history-loading">
            <div className="typing-indicator"><span/><span/><span/></div>
            <p>불러오는 중...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="history-empty">
            <p>최근 10일 이내의</p>
            <p>대화 기록이 없습니다.</p>
          </div>
        ) : (
          Object.entries(groupedSessions).map(([dateLabel, dateSessions]) => (
            <div key={dateLabel} className="history-date-group">
              <div className="history-date-label">{dateLabel}</div>
              <ul className="history-session-list">
                {dateSessions.map((s) => (
                  <li
                    key={s.session_id}
                    className={`history-session-card ${activeSessionId === s.session_id ? 'active' : ''}`}
                    onClick={() => onSelectSession(s.session_id)}
                  >
                    <div className="history-session-preview">
                      {s.message_preview || '(내용 없음)'}
                    </div>
                    <div className="history-session-count">{s.message_count}개 메시지</div>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
    </div>
    </>
  );
}

export default HistoryPanel;
