# RAG Chatbot

AWS Bedrock 기반 RAG(Retrieval-Augmented Generation) 챗봇 시스템입니다. 문서 기반 질의응답, 용어 검색, 대화 이력 관리 기능을 제공합니다.

## Overview

Amazon Bedrock Knowledge Base를 활용하여 업로드된 문서에서 정확한 답변을 검색·생성합니다.

### 주요 기능

| 기능 | 설명 | Frontend Route | Backend Route |
|------|------|----------------|---------------|
| **가이드 챗봇** | Knowledge Base 기반 질의응답 | `/chat` | `/api/chat` |
| **업무 가이드** | 업무 절차 및 시스템 안내 | `/work-guide` | `/api/work-guide` |
| **용어 가이드** | LLM 기반 용어 추출 후 DB 검색 | `/glossary` | `/api/glossary/query` |
| **인증** | JWT 기반 로그인/로그아웃 | `/login` | `/api/auth` |
| **대화 이력** | 서비스별 독립 대화 이력 영구 저장 및 조회 | - | `/api/history` |

## Architecture

```
┌──────────────────────┐
│      Browser         │
│   Next.js (WEB)      │
│   Port: 3000         │
└──────────┬───────────┘
           │ HTTP/HTTPS
           ▼
┌──────────────────────┐       ┌─────────────────────┐
│      FastAPI         │─────> │      PostgreSQL     │
│   Port: 8000         │       │    - chat logs      │
└──────────┬───────────┘       │    - Glossary       │
           │                   └─────────────────────┘
           ▼
┌──────────────────────┐
│    AWS Bedrock       │
│  - Knowledge Base    │
│  - Nova Lite/ Claude │
└──────────────────────┘
```

## Tech Stack

### Backend
- **Python 3.13 / FastAPI 0.115** — 비동기 웹 프레임워크
- **Uvicorn** — ASGI 서버
- **Pydantic 2.10** — 설정 및 요청/응답 모델
- **python-jose / passlib** — JWT 인증
- **SQLAlchemy 2.0** — ORM (대화 이력 영구 저장)
- **Boto3** — AWS Bedrock Knowledge Base + LLM

### Frontend
- **Next.js 16** (Pages Router, Static Export)
- **React 19** — 컴포넌트 기반 UI
- **Axios** — HTTP 클라이언트 (JWT 인터셉터 포함)
- **React Markdown** — 마크다운 응답 렌더링

### Infrastructure
- **AWS Bedrock** — RAG Knowledge Base + LLM 추론
- **PostgreSQL** — 대화 이력 + 용어 사전 저장
- **Nginx** — 리버스 프록시 (정적 파일 서빙 + API 프록시)
- **systemd** — 백엔드 서비스 관리

## Prerequisites

- Python 3.13+
- Node.js 18+
- PostgreSQL 14+
- AWS 계정 (Bedrock Knowledge Base 설정 필요)

## Getting Started

### 1. Clone & Setup

```bash
git clone <repository-url> C:\rag-chatbot
```

### 2. Backend Setup

```bash
cd C:\rag-chatbot
py -3.13 -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
# source .venv/bin/activate     # Linux/Mac

cd aichat-back
pip install -r requirements.txt
```

환경 변수 설정:

```bash
cp .env.example .env
# .env 파일을 열고 실제 값으로 채워주세요
```

### 3. Frontend Setup

```bash
cd C:\rag-chatbot\aichat-front
npm install
```

`.env.development` 파일 생성:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 4. AWS Bedrock Setup

1. **Knowledge Base 생성 (2개)**
   - 가이드용 Knowledge Base → ID를 `BEDROCK_KNOWLEDGE_BASE_ID`에 설정
   - 업무 가이드용 Knowledge Base → ID를 `WORK_GUIDE_KNOWLEDGE_BASE_ID`에 설정
2. **S3 버킷에 문서 업로드 후 Knowledge Base와 동기화**
3. **모델 활성화** — Bedrock 콘솔에서 사용할 모델 활성화
4. **IAM 권한 설정** — Bedrock, S3 접근 권한

### 5. Database Setup

```sql
CREATE SCHEMA IF NOT EXISTS aichat;

-- 용어 사전 테이블 (Glossary 기능 사용 시)
CREATE TABLE aichat.tb_glossary_category (
    DICTIONARY_ID   SERIAL PRIMARY KEY,
    DICTIONARY_NAME VARCHAR(100) NOT NULL
);

CREATE TABLE aichat.tb_glossary_term (
    WORD_ID             SERIAL PRIMARY KEY,
    DICTIONARY_ID       INTEGER REFERENCES aichat.tb_glossary_category(DICTIONARY_ID),
    WORD_NAME           VARCHAR(200) NOT NULL,
    WORD_ENGLISH_NAME   VARCHAR(200),
    TEXT_CONTENTS       TEXT
);

-- 대화 이력 테이블은 앱 시작 시 자동 생성됩니다 (SQLAlchemy auto-create)
```

## Running the Application

### Backend

```bash
cd C:\rag-chatbot
.\.venv\Scripts\Activate.ps1    # Windows PowerShell

cd aichat-back
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd C:\rag-chatbot\aichat-front

# 개발 모드 (port 3000)
npm run dev

# 프로덕션 빌드 (out/ 폴더에 정적 파일 생성)
npm run build
```

## Deployment

배포 설정 파일은 [aichat-back/deployment/](aichat-back/deployment/) 폴더에 있습니다.

- `rag-chatbot-backend.service` — systemd 서비스 유닛
- `rag-chatbot.conf` — Nginx 설정

## Project Structure

```
rag-chatbot/
├── aichat-back/              # Backend (FastAPI)
│   ├── app/
│   │   ├── api/              # 라우트 핸들러
│   │   ├── models/           # Pydantic 모델
│   │   ├── services/         # 비즈니스 로직 + Repository 패턴
│   │   ├── database/         # SQLAlchemy ORM
│   │   ├── utils/            # 로거 (PII 마스킹 포함)
│   │   ├── config.py         # Pydantic BaseSettings
│   │   └── main.py           # FastAPI 앱 초기화
│   ├── deployment/           # systemd / Nginx 설정
│   ├── requirements.txt
│   └── .env.example          # 환경변수 템플릿
└── aichat-front/             # Frontend (Next.js)
    ├── src/
    │   ├── pages/            # Next.js Pages Router
    │   ├── components/       # React 컴포넌트
    │   └── services/api.js   # Axios API 클라이언트
    └── next.config.mjs       # output: 'export' (정적 빌드)
```

## Environment Variables

전체 환경변수 목록은 [aichat-back/.env.example](aichat-back/.env.example)을 참고하세요.

주요 변수:

| 변수 | 설명 |
|------|------|
| `SECRET_KEY` | JWT 서명 키 |
| `ADMIN_USER_ID` | 로그인 아이디 |
| `ADMIN_PASSWORD` | 로그인 비밀번호 |
| `AWS_ACCESS_KEY_ID` | AWS 자격 증명 |
| `AWS_SECRET_ACCESS_KEY` | AWS 자격 증명 |
| `BEDROCK_KNOWLEDGE_BASE_ID` | 가이드용 Knowledge Base ID |
| `WORK_GUIDE_KNOWLEDGE_BASE_ID` | 업무 가이드용 Knowledge Base ID |
| `PG_HOST` / `PG_DATABASE` | PostgreSQL 연결 정보 |

## Security Notes

- `.env` 파일은 절대 커밋하지 않습니다 (`.gitignore`에 등록됨)
- `ADMIN_PASSWORD`는 반드시 강력한 값으로 변경하세요
- 프로덕션 환경에서는 `SECRET_KEY`를 안전한 랜덤값으로 설정하세요
