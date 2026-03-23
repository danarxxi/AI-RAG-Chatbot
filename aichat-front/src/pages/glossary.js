import Head from 'next/head';
import Glossary from '../components/Glossary';

export default function GlossaryPage() {
  return (
    <>
      <Head>
        <title>RAG Chatbot</title>
      </Head>
      <Glossary />
    </>
  );
}