import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { authAPI } from '../services/api';

function Select() {
  const router = useRouter();
  const [userName, setUserName] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  useEffect(() => {
    // Read from sessionStorage (client-side only)
    setUserName(sessionStorage.getItem('user_name'));
    setSessionId(sessionStorage.getItem('session_id'));

    // Reset viewport zoom on mobile when entering select page
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (viewportMeta) {
      viewportMeta.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=1.0');
      setTimeout(() => {
        viewportMeta.setAttribute('content', 'width=device-width, initial-scale=1.0');
      }, 100);
    }

    // 페이지 로드 시 포커스 제거
    if (document.activeElement) {
      document.activeElement.blur();
    }
  }, []);

  const handleLogout = async () => {
    try {
      await authAPI.logout(sessionId);
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      sessionStorage.clear();
      router.push('/login')
    }
  };

  return (
    <div className="select-container">
      <div className="select-box">
        <h1>RAG CHATBOT</h1>
        <p className="select-subtitle">원하는 서비스를 선택해 주세요</p>

        <div className="select-buttons">
          <button
            className="select-button"
            onClick={() => router.push('/chat')}
          >
            <span className="button-title">📄 HR 가이드</span>
            <span className="button-desc">휴가/출산휴가 신청, 퇴직금, 4대보험 등 <br className="mobile-br" />인사 제도를 알려드려요</span>
          </button>

          <button
            className="select-button"
            onClick={() => router.push('/work-guide')}
          >
            <span className="button-title">🏢 업무 가이드</span>
            <span className="button-desc">Teams, 복합기 등 사내 시스템 설치 및 <br className="mobile-br" />사용 방법을 알려드려요</span>
          </button>

          <button
            className="select-button"
            onClick={() => router.push('/glossary')}
          >
            <span className="button-title">📖 용어 가이드</span>
            <span className="button-desc">업무 중 모르는 사내 용어나 <br className="mobile-br" />약어의 뜻을 알려드려요</span>
          </button>
        </div>

        <div className="select-footer">
          <span className="user-id">사용자: {userName}</span>
          <button onClick={handleLogout} className="logout-button">
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );
}

export default Select;
