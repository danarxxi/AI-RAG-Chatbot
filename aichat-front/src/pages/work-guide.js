import Head from 'next/head';
import WorkGuide from '../components/WorkGuide';

export default function WorkGuidePage() {
  return (
    <>
      <Head>
        <title>RAG Chatbot</title>
      </Head>
      <WorkGuide />
    </>
  );
}