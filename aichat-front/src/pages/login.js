import Head from 'next/head';
import Login from '../components/Login';

export default function LoginPage() {
  return (
    <>
      <Head>
        <title>RAG Chatbot</title>
      </Head>
      <Login />
    </>
  );
}