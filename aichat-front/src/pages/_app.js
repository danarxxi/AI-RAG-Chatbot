import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import "@/styles/globals.css";
import "../components/Login.css";
import "../components/Select.css";
import "../components/Chat.css";
import "../components/Glossary.css";
import "../components/WorkGuide.css";
import "../components/HistoryPanel.css";

// Protected routes list
const protectedRoutes = ['/select', '/chat', '/glossary', '/work-guide'];

export default function App({ Component, pageProps }) {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    // 페이지 로드 시 토큰 체크
    const checkAuth = () => {
      const token = sessionStorage.getItem('access_token');

      // DEBUG
      console.log('[_app.js] Current path:', router.pathname);
      console.log('[_app.js] Token check:', token ? 'EXISTS' : 'NULL');
      console.log('[_app.js] All sessionStorage:', {
        access_token: sessionStorage.getItem('access_token'),
        session_id: sessionStorage.getItem('session_id'),
        user_id: sessionStorage.getItem('user_id')
      });

      // 보호된 페이지인데 토큰 없으면 로그인으로
      if (protectedRoutes.includes(router.pathname) && !token) {
        console.log('[_app.js] Redirecting to /login - no token found');
        router.replace('/login');
        return; // 리다이렉트 중에는 isChecking을 false로 바꾸지 않아 컴포넌트가 렌더링되지 않음
      }

      setIsChecking(false);
    };

    checkAuth();
  }, [router.pathname]);

  // 로딩 중에는 아무것도 렌더링하지 않음
  if (isChecking && protectedRoutes.includes(router.pathname)) {
    return null;
  }

  return <Component {...pageProps} />;
}
