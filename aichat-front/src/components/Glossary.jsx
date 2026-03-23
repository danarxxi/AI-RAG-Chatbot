import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { glossaryAPI, authAPI, sessionAPI, historyAPI } from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import HistoryPanel from './HistoryPanel';

const quickPrompts = [
  '어떤 카테고리의 용어가 있나요?',
  '귀돌이 뜻을 알려주세요',
  'MOQ가 궁금해요',
];

function Glossary() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState({});
  const [closingTab, setClosingTab] = useState({});
  const [isResetting, setIsResetting] = useState(false);
  const [viewingSession, setViewingSession] = useState(null);
  const [viewingMessages, setViewingMessages] = useState([]);
  const [loadingViewMessages, setLoadingViewMessages] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [starHovers, setStarHovers] = useState({});
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const router = useRouter();
  const [sessionId, setSessionId] = useState(null);
  const [userId, setUserId] = useState(null);
  const [userName, setUserName] = useState(null);

  useEffect(() => {
    // Read from sessionStorage (client-side only)
    const storedSessionId = sessionStorage.getItem('session_id');
    const storedUserId = sessionStorage.getItem('user_id');

    setSessionId(storedSessionId);
    setUserId(storedUserId);
    setUserName(sessionStorage.getItem('user_name'));

    // Reset viewport zoom on mobile when entering glossary page
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (viewportMeta) {
      viewportMeta.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=1.0');
      setTimeout(() => {
        viewportMeta.setAttribute('content', 'width=device-width, initial-scale=1.0');
      }, 100);
    }

    // Redirect to login if not authenticated (check stored values, not state)
    if (!storedSessionId || !storedUserId) {
      router.push('/login');
      return;
    }
  }, [router]);

  // Fetch history in separate useEffect (after sessionId is set)
  useEffect(() => {
    if (!sessionId || !userId) return;

    const fetchHistory = async () => {
      setLoadingHistory(true);
      try {
        const historyData = await glossaryAPI.getHistory(sessionId);

        if (historyData.messages && historyData.messages.length > 0) {
          // Convert backend messages to frontend format
          const formattedMessages = historyData.messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            timestamp: new Date(msg.timestamp),
            sources: []  // Sources not stored in history
          }));
          setMessages(formattedMessages);
        } else {
          // No history, show welcome message
          setMessages([{
            role: 'assistant',
            content: 'RAG 챗봇에 오신 것을 환영합니다!\n\n저는 등록된 용어에 대해서만 정확한 답변을 제공할 수 있어요.\n\n처음 사용하시는 경우 "어떤 카테고리의 용어가 있나요?"라고 물어보세요😊',
            timestamp: new Date(),
            sources: []
          }]);
        }
      } catch (err) {
        console.error('Error fetching history:', err);
        // On error, show welcome message
        setMessages([{
          role: 'assistant',
          content: 'RAG 챗봇에 오신 것을 환영합니다!\n\n저는 등록된 용어에 대해서만 정확한 답변을 제공할 수 있어요.\n\n처음 사용하시는 경우 "어떤 카테고리의 용어가 있나요?"라고 물어보세요😊',
          timestamp: new Date(),
          sources: []
        }]);
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();

    // Focus on input field after history loads
    setTimeout(() => inputRef.current?.focus(), 100);
  }, [sessionId, userId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, viewingMessages]);

  const adjustTextareaHeight = () => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && inputMessage.trim()) {
        handleSendMessage(e);
      }
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();

    if (!inputMessage.trim()) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setError('');

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    // Add user message and placeholder assistant message to UI immediately
    setMessages(prev => [...prev,
      {
        role: 'user',
        content: userMessage,
        timestamp: new Date()
      },
      {
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        sources: [],
        isLoading: true
      }
    ]);

    setLoading(true);

    try {
      const response = await glossaryAPI.query(userMessage, sessionId);

      // Update the placeholder message with actual response
      setMessages(prev => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        updated[lastIndex] = {
          role: 'assistant',
          content: response.answer,
          timestamp: new Date(response.timestamp),
          sources: response.source_terms || [],
          isLoading: false,
          message_id: response.message_id,
          rating: null,
          executed_query: response.executed_query || null
        };
        return updated;
      });
      setHistoryRefreshKey(prev => prev + 1);
    } catch (err) {
      setError(err.response?.data?.detail || '메시지 전송에 실패했습니다. 다시 시도해주세요.');
      console.error('Glossary error:', err);
      // Remove placeholder message on error
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  const handleTabClick = (index, tab) => {
    if (activeTab[index] === tab) {
      // 같은 탭 클릭 → 닫기 애니메이션
      setClosingTab(prev => ({ ...prev, [index]: true }));
      setTimeout(() => {
        setActiveTab(prev => ({ ...prev, [index]: null }));
        setClosingTab(prev => ({ ...prev, [index]: false }));
      }, 150);
    } else {
      // 다른 탭 클릭 → 즉시 전환 (애니메이션 없이)
      setActiveTab(prev => ({ ...prev, [index]: tab }));
      setClosingTab(prev => ({ ...prev, [index]: false }));
    }
  };

  const handleNewChat = async () => {
    // 기록 보기 모드 해제
    setViewingSession(null);
    setViewingMessages([]);

    // Start fade animation
    setIsResetting(true);

    try {
      // Wait for fade animation to complete
      await new Promise(resolve => setTimeout(resolve, 150));

      // Clear only Glossary service history (keeps same session, preserves other services)
      await sessionAPI.clearServiceHistory('glossary');

      // Clear messages and show welcome message
      setMessages([{
        role: 'assistant',
        content: 'RAG 챗봇에 오신 것을 환영합니다!\n\n저는 등록된 용어에 대해서만 정확한 답변을 제공할 수 있어요.\n\n처음 사용하시는 경우 "어떤 카테고리의 용어가 있나요?"라고 물어보세요😊',
        timestamp: new Date(),
        sources: []
      }]);

      // Clear error and tab state
      setError('');
      setActiveTab({});
      setClosingTab({});

    } catch (err) {
      console.error('Failed to clear chat history:', err);
      setError('새 대화를 시작하는데 실패했습니다. 다시 시도해주세요.');
    } finally {
      // End fade animation
      setTimeout(() => setIsResetting(false), 50);
    }
  };

  const handleSelectSession = async (sessionId) => {
    // 같은 세션 클릭 시 현재 대화로 복귀
    if (viewingSession === sessionId) {
      setViewingSession(null);
      setViewingMessages([]);
      setIsMobileHistoryOpen(false);
      return;
    }

    setViewingSession(sessionId);
    setIsMobileHistoryOpen(false);
    setLoadingViewMessages(true);
    try {
      const data = await historyAPI.getSessionMessages(sessionId, 'glossary');
      setViewingMessages(data.messages || []);
    } catch (err) {
      console.error('메시지 로드 실패:', err);
      setViewingMessages([]);
    } finally {
      setLoadingViewMessages(false);
    }
  };

  const handleReturnToChat = () => {
    setViewingSession(null);
    setViewingMessages([]);
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout(sessionId);
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      sessionStorage.clear();
      router.push('/login');
    }
  };

  const handleQuickPrompt = (promptText) => {
    setInputMessage(promptText);
    setTimeout(() => {
      setInputMessage('');
      setError('');

      setMessages(prev => [...prev,
        { role: 'user', content: promptText, timestamp: new Date() },
        { role: 'assistant', content: '', timestamp: new Date(), sources: [], isLoading: true }
      ]);

      setLoading(true);

      glossaryAPI.query(promptText, sessionId)
        .then(response => {
          setMessages(prev => {
            const updated = [...prev];
            const lastIndex = updated.length - 1;
            updated[lastIndex] = {
              role: 'assistant',
              content: response.answer,
              timestamp: new Date(response.timestamp),
              sources: response.source_terms || [],
              isLoading: false,
              message_id: response.message_id,
              rating: null,
              executed_query: response.executed_query || null
            };
            return updated;
          });
          setHistoryRefreshKey(prev => prev + 1);
        })
        .catch(err => {
          setError(err.response?.data?.detail || '메시지 전송에 실패했습니다. 다시 시도해주세요.');
          console.error('Glossary error:', err);
          setMessages(prev => prev.slice(0, -1));
        })
        .finally(() => {
          setLoading(false);
          setTimeout(() => inputRef.current?.focus(), 0);
        });
    }, 0);
  };

  const handleRating = async (index, messageId, rating) => {
    try {
      await glossaryAPI.submitFeedback(messageId, rating);
      // 별점 저장 → "피드백 감사합니다" 표시
      setMessages(prev => {
        const updated = [...prev];
        updated[index] = { ...updated[index], rating };
        return updated;
      });
      // 2.5초 후 페이드아웃 시작
      setTimeout(() => {
        setMessages(prev => {
          const updated = [...prev];
          updated[index] = { ...updated[index], ratingFading: true };
          return updated;
        });
        // 페이드아웃 애니메이션(0.6초) 완료 후 완전히 제거
        setTimeout(() => {
          setMessages(prev => {
            const updated = [...prev];
            updated[index] = { ...updated[index], rating: 'done' };
            return updated;
          });
        }, 600);
      }, 2500);
    } catch (err) {
      console.error('별점 저장 실패:', err);
    }
  };

  const handleBack = () => {
    router.push('/select');
  };

  return (
    <div className="glossary-container">
      <div className="glossary-header">
        <div className="header-left">

          <div className="header-titles">
            <h1>RAG CHATBOT</h1>
            <p className="header-subtitle">신입사원을 위한 <span className="subtitle-break">용어 가이드 챗봇</span></p>
          </div>
        </div>
        <div className="user-info">
          <span>사용자: {userName}</span>
          <button onClick={handleLogout} className="logout-button">로그아웃</button>
        </div>
      </div>

      <div className="feedback-bar">
        <span className="feedback-text">챗봇 사용 중 불편한 점이 있다면?</span>
        <a
          href="https://sparkling-son-018.notion.site/2efcd9780fdc805fae2dd7d14cd8662a?pvs=105"
          target="_blank"
          rel="noopener noreferrer"
          className="feedback-button"
        >
          ✏️ 피드백 제출하기
        </a>
      </div>

      <div className="chat-top-spacer" />

      <div className={`glossary-messages ${isResetting ? 'resetting' : ''}`}>
        {viewingSession ? (
          loadingViewMessages ? (
            <div className="loading-history">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <p>대화 기록을 불러오는 중...</p>
            </div>
          ) : (
            viewingMessages.map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                <div className="message-content">
                  <div className="message-role">
                    {message.role === 'user' ? '나' : '용어 어시스턴트'}
                  </div>
                  <div className="message-text">
                    {message.role === 'assistant' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{message.content}</ReactMarkdown>
                    ) : (
                      <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
                    )}
                  </div>
                  <div className="message-time">
                    {new Date(message.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            ))
          )
        ) : (
          loadingHistory ? (
            <div className="loading-history">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <p>대화 기록을 불러오는 중...</p>
            </div>
          ) : (
            messages.map((message, index) => (
            <div key={index} className={`message ${message.role} ${message.isLoading ? 'loading-appear' : ''}`}>
              <div className="message-content">
                <div className="message-role">
                  {message.role === 'user' ? '나' : '용어 어시스턴트'}
                </div>
                <div className="message-text">
                  {message.role === 'assistant' && message.isLoading ? (
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  ) : message.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{message.content}</ReactMarkdown>
                  ) : (
                    <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
                  )}
                </div>

                {/* 별점 피드백 — 현재 세션의 AI 답변에만 표시 */}
                {message.role === 'assistant' && !message.isLoading && message.message_id && message.rating !== 'done' && (
                  <div className={`star-rating${message.ratingFading ? ' fading' : ''}`}>
                    {!message.rating && (
                      <span className="star-label">이 답변이 도움이 되었나요?</span>
                    )}
                    {[1, 2, 3, 4, 5].map(star => (
                      <button
                        key={star}
                        className={`star-button ${(message.rating >= star || (!message.rating && starHovers[index] >= star)) ? 'filled' : ''}`}
                        onClick={() => handleRating(index, message.message_id, star)}
                        onMouseEnter={() => !message.rating && setStarHovers(prev => ({ ...prev, [index]: star }))}
                        onMouseLeave={() => !message.rating && setStarHovers(prev => ({ ...prev, [index]: 0 }))}
                        disabled={!!message.rating}
                      >
                        ★
                      </button>
                    ))}
                    {message.rating && (
                      <span className="star-thanks">피드백 감사합니다</span>
                    )}
                  </div>
                )}

                {/* 참고 용어 / 실행 쿼리 탭 — 하나라도 있을 때 표시 */}
                {message.role === 'assistant' && (message.sources?.length > 0 || message.executed_query) && (
                  <div className="info-tabs-section">
                    <div className="info-tabs-bar">
                      {message.sources?.length > 0 && (
                        <button
                          className={`info-tab-btn${activeTab[index] === 'sources' ? ' active' : ''}`}
                          onClick={() => handleTabClick(index, 'sources')}
                        >
                          참고 용어 보기 ({message.sources.length})
                        </button>
                      )}
                      {message.executed_query && (
                        <button
                          className={`info-tab-btn${activeTab[index] === 'query' ? ' active' : ''}`}
                          onClick={() => handleTabClick(index, 'query')}
                        >
                          실행 쿼리 보기
                        </button>
                      )}
                    </div>

                    {activeTab[index] && (
                      <div className={`info-tab-panel${closingTab[index] ? ' closing' : ''}`}>
                        {activeTab[index] === 'sources' && (
                          <div className="sources-list">
                            {message.sources.map((source, sourceIndex) => (
                              <div key={sourceIndex} className="source-item">
                                <div className="source-header">
                                  📖 {source.word_name}
                                  {source.word_english_name && (
                                    <span className="source-english"> ({source.word_english_name})</span>
                                  )}
                                </div>
                                <div className="source-category">분류: {source.category}</div>
                                <div className="source-content">{source.definition}</div>
                              </div>
                            ))}
                          </div>
                        )}
                        {activeTab[index] === 'query' && (
                          <pre className="sql-code">{message.executed_query}</pre>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <div className="message-time">
                  {new Date(message.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
            ))
          )
        )}

        {/* Quick Prompts - 웰컴 메시지만 있을 때 표시 */}
        {!viewingSession && messages.length === 1 && messages[0].role === 'assistant' && !messages[0].isLoading && (
          <div className="quick-prompts">
            {quickPrompts.map((prompt, index) => (
              <button
                key={index}
                className="quick-prompt-chip"
                onClick={() => handleQuickPrompt(prompt)}
                disabled={loading}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {error && <div className="glossary-error">{error}</div>}

      <HistoryPanel
        serviceType="glossary"
        onNewChat={handleNewChat}
        activeSessionId={viewingSession}
        onSelectSession={handleSelectSession}
        refreshKey={historyRefreshKey}
        isMobileOpen={isMobileHistoryOpen}
        onToggleMobile={() => setIsMobileHistoryOpen(p => !p)}
        onMobileClose={() => setIsMobileHistoryOpen(false)}
      />

      <div className="glossary-input-container">
        <div className="guide-info-bar">
          <span className="guide-change-link" onClick={handleBack}>← 다른 가이드 선택</span>
          <span className="guide-separator">·</span>
          <span className="guide-current">현재 가이드: 용어 어시스턴트</span>
        </div>
        {viewingSession ? (
          <div className="history-view-bar">
            <span className="history-view-text">과거 대화 기록을 보는 중입니다</span>
            <button onClick={handleReturnToChat} className="return-to-chat-btn">현재 대화로 돌아가기</button>
          </div>
        ) : (
          <>
            <form className="glossary-input-form" onSubmit={handleSendMessage}>
              <textarea
                ref={inputRef}
                value={inputMessage}
                onChange={(e) => { setInputMessage(e.target.value); adjustTextareaHeight(); }}
                onKeyDown={handleKeyDown}
                placeholder="궁금한 용어에 대해 물어보세요"
                disabled={loading}
                className="glossary-input"
                rows={1}
              />
              <button type="submit" disabled={loading || !inputMessage.trim()} className="send-button">
                ↑
              </button>
            </form>
            <div className="glossary-disclaimer">
              본 답변은 사내 용어집을 기반으로 하며, 정확한 정보는 담당 부서에 확인하세요.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default Glossary;
