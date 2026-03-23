import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 홈 페이지 접속 시 로그인으로 리다이렉트
    router.replace('/login');
  }, [router]);

  return null;
}
