import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { authAPI } from '../services/api';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const router = useRouter();
  const usernameInputRef = useRef(null);

  useEffect(() => {
    const savedUsername = localStorage.getItem('saved_username');
    if (savedUsername) {
      setUsername(savedUsername);
      setRememberMe(true);
    }
    setTimeout(() => usernameInputRef.current?.focus(), 100);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await authAPI.login(username, password);

      // Save or remove username based on checkbox
      if (rememberMe) {
        localStorage.setItem('saved_username', username);
      } else {
        localStorage.removeItem('saved_username');
      }

      // Store authentication data
      sessionStorage.setItem('access_token', response.access_token);
      sessionStorage.setItem('session_id', response.session_id);
      sessionStorage.setItem('user_id', response.user_id);
      sessionStorage.setItem('user_name', response.user_name);

      // DEBUG: 저장 확인
      console.log('Token saved:', sessionStorage.getItem('access_token'));
      console.log('Session ID:', sessionStorage.getItem('session_id'));
      console.log('User ID:', sessionStorage.getItem('user_id'));
      console.log('User Name:', sessionStorage.getItem('user_name'));

      // Clear error on success and redirect
      setError('');
      document.activeElement?.blur();
      router.push('/select');
    } catch (err) {
      setError(err.response?.data?.detail || '로그인에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>RAG CHATBOT</h1>
        <p className="login-subtitle">신입사원의 첫 업무 파트너</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">아이디</label>
            <input
              ref={usernameInputRef}
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="아이디를 입력하세요"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">비밀번호</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
              required
              disabled={loading}
            />
          </div>

          <div className="remember-id">
            <input
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              disabled={loading}
            />
            <label htmlFor="rememberMe">아이디 저장</label>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="login-button">
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div className="logo-container">
          <img src="/logo.png" alt="Logo" className="login-logo" />
        </div>

      </div>
    </div>
  );
}

export default Login;
