import json
import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings
from app.models.glossary import GlossaryTerm, GlossaryQueryRequest, GlossaryQueryResponse
from app.models.session import Message
from app.services.database.postgresql_repository import PostgreSQLGlossaryRepository
from app.utils.logger import setup_logger
from datetime import datetime

settings = get_settings()
logger = setup_logger(__name__, service_type="GLOSSARY")

# Thread pool for running blocking calls (Bedrock API, Oracle DB)
executor = ThreadPoolExecutor(max_workers=10)


class GlossaryService:
    """Service for handling glossary queries with LLM-based term extraction."""

    def __init__(self):
        self.repository = PostgreSQLGlossaryRepository()
        self.bedrock_client = None
        # Use glossary_model_id if set, otherwise fall back to main bedrock_model_id
        self.model_id = settings.glossary_model_id or settings.bedrock_model_id

        if settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key
                )
                logger.info(f"Bedrock client initialized for glossary service (model: {self.model_id})")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock client: {e}")
        else:
            logger.warning("AWS credentials not configured - glossary service will not work")

    def _extract_terms_simple(self, query: str) -> List[str]: #백업 로직
        """Simple term extraction by removing common question words and particles."""
        import re
        # Remove common Korean question patterns and particles
        cleaned = query
        # Remove question words
        patterns_to_remove = [
            r'이?가?\s*뭐야\??', r'이?가?\s*뭔가요\??', r'이?가?\s*무엇인가요\??',
            r'이?가?\s*무엇이야\??', r'뭐예요\??', r'무엇이에요\??',
            r'알려\s*줘\??', r'알려\s*주세요\??', r'설명해\s*줘\??',
            r'에\s*대해', r'이?란\??', r'이?라는\??',
            r'\?', r'!'
        ]
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned)

        # Clean up whitespace
        cleaned = ' '.join(cleaned.split()).strip()

        if cleaned:
            return [cleaned]
        return [query]

    def _classify_and_extract_terms(self, query: str, conversation_history: List[Message]) -> Dict[str, Any]:
        """
        Classify query type and extract terms if applicable.
        Returns: {"query_type": str, "terms": List[str]}
        """
        if not self.bedrock_client:
            logger.warning("Bedrock client not available, using simple extraction")
            return {"query_type": "glossary_lookup", "terms": self._extract_terms_simple(query)}

        # Build conversation context for better understanding
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-6:]  # Last 3 turns
            history_context = "\n\nPrevious conversation:\n"
            for msg in recent_messages:
                history_context += f"{msg.role}: {msg.content}\n"

        prompt = f"""\
        You are an intelligent assistant that analyzes user queries to understand their intent.

        Your task is to classify the query type and extract glossary terms if applicable.

        {history_context}

        Current User Query: {query}

        Query Type Classification:
        1. "greeting" - Simple greetings like "hello", "hi", "thank you", etc.
        2. "summary_request" - User asks for a summary or recap of the conversation (e.g., "summarize what we discussed", "정리해줘")
        3. "metadata_query" - User asks for statistics/metadata about the glossary itself:
           - "total_count": Total word count (e.g., "몇 개", "how many words", "단어 수", "전체 개수")
           - "category_list": Category list (e.g., "what categories", "어떤 카테고리", "분류 목록", "카테고리 종류")
           - "count_by_category": Count per category (e.g., "category별 개수", "카테고리마다", "각 분류별", "통계")
        4. "followup_question" - User asks about a term mentioned in previous conversation but not explicitly stated in current query
        5. "glossary_lookup" - User asks about specific company terminology that needs database lookup
        6. "general_question" - General questions not related to company glossary (including help/usage questions like "어떤 질문 가능?", "what can you do?")

        Important Rules:
        - Pay close attention to the CONTEXT of the conversation history
        - If user says "정리해줘" or "요약해줘" or "summarize", it's a summary_request, NOT a glossary lookup
        - If user asks about glossary statistics (개수, 몇 개, 카테고리, etc.), it's a metadata_query
        - Only extract terms when the user is clearly asking for their definition/explanation
        - For greetings, summary requests, and metadata queries, return empty terms list
        - For followup questions, extract the term being referenced from context
        - For metadata_query, you MUST specify the metadata_type based on what user is asking

        Respond only in JSON format:
        {{
            "query_type": "greeting|summary_request|metadata_query|followup_question|glossary_lookup|general_question",
            "metadata_type": "total_count|category_list|count_by_category|null",
            "terms": ["term1", "term2"]
        }}
        """

        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.1
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                text = content[0].get('text', '{}')
                try:
                    result = json.loads(text)
                    query_type = result.get('query_type', 'glossary_lookup')
                    metadata_type = result.get('metadata_type', None)
                    terms = result.get('terms', [])
                    logger.info(f"Query classified as '{query_type}' (metadata: {metadata_type}) with terms: {terms}")
                    return {
                        "query_type": query_type,
                        "metadata_type": metadata_type,
                        "terms": terms
                    }
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM response as JSON: {text}")

            # Fallback
            return {"query_type": "glossary_lookup", "metadata_type": None, "terms": self._extract_terms_simple(query)}

        except ClientError as e:
            logger.error(f"Bedrock API error during classification: {e}")
            return {"query_type": "glossary_lookup", "metadata_type": None, "terms": self._extract_terms_simple(query)}
        except Exception as e:
            logger.error(f"Unexpected error during classification: {e}")
            return {"query_type": "glossary_lookup", "metadata_type": None, "terms": self._extract_terms_simple(query)}

    def _generate_response(self, query: str, terms: List[GlossaryTerm], conversation_history: List[Message]) -> str:
        """Generate natural language response using LLM with glossary context and conversation history."""
        if not self.bedrock_client:
            return "용어집 서비스가 현재 사용 불가능합니다."

        # Build context from glossary terms
        context = self._build_glossary_context(terms)

        # Build conversation history
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-6:]  # Last 3 turns
            history_context = "\n[Previous Conversation]\n"
            for msg in recent_messages:
                history_context += f"{msg.role}: {msg.content}\n"

        prompt = f"""\
        You are an AI assistant helping employees understand internal terminology based on the company's glossary. Your role is to explain hard-to-understand terms in an easy and friendly manner.

        [Glossary Information]
        {context}
        {history_context}

        [Response Rules]
        1. **Answer using only the information provided in the glossary.**
        2. **Do not speculate or guess information not found in the glossary.**
        3. If the glossary definitions are stiff or dictionary-like, rephrase them into natural spoken language (conversational style).
        4. If there are multiple related terms, please provide them together.
        5. Keep the answer concise but include sufficient explanation.
        6. Use conversation history to provide contextually relevant answers.

        [Tone & Style]
        1. Language: Always respond in Korean.
        2. Tone: Maintain a conversational, helpful colleague attitude. Be warm and approachable. Use approximately one emoji appropriate for the context.
        3. Sentence Endings: Use soft and friendly endings like "~에요/해요", "~인 것 같아요", or "~라고 해요". Avoid dry, dictionary-style endings like "~임", "~함", "~하는 것", or "~하여야 함".
        4. **Never use stiff or robotic pronouns.**
        5. Do not simply copy and paste the definition. refine the sentences as if explaining to a coworker.

        [Formatting Rules for Readability]
        1. Structure: Use bullet points or numbered lists if there are multiple meanings or related terms.
        2. Spacing: Add blank lines between paragraphs so the text does not look dense.
        3. Highlighting: Mark key terms or important concepts in bold.

        [User Question]
        {query}

        [Answer]
        """

        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2048,
                "temperature": 0.3
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                return content[0].get('text', '응답 생성에 실패했습니다.')

            return '응답 생성에 실패했습니다.'

        except ClientError as e:
            logger.error(f"Bedrock API error during response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        except Exception as e:
            logger.error(f"Unexpected error during response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다."

    def _generate_contextual_response(self, query: str, query_type: str, conversation_history: List[Message]) -> str:
        """Generate response based on query type and conversation history."""
        if not self.bedrock_client:
            return "용어집 서비스가 현재 사용 불가능합니다."

        # Build conversation history
        history_context = ""
        if conversation_history:
            history_context = "\n[Conversation History]\n"
            for msg in conversation_history:
                history_context += f"{msg.role}: {msg.content}\n"

        # Different prompts based on query type
        if query_type == "greeting":
            prompt = f"""\
            You are a friendly AI assistant for the company glossary service.
            The user has sent a greeting or expression of gratitude.

            Respond warmly and briefly. Let them know you're here to help with company terminology questions.

            [Tone & Style]
            1. Language: Always respond in Korean.
            2. Be warm, friendly, and concise.
            3. Use one appropriate emoji.
            4. Use friendly endings like "~에요/해요".

            [User Message]
            {query}

            [Your Response]
            """

        elif query_type == "summary_request":
            prompt = f"""\
            You are an AI assistant helping employees with company terminology.
            The user has requested a summary of the conversation.

            {history_context}

            Task: Provide a concise summary of what was discussed, including:
            - What terms the user asked about
            - Brief recap of the definitions provided
            - Keep it natural and conversational

            [Tone & Style]
            1. Language: Always respond in Korean.
            2. Be conversational and helpful.
            3. Use one appropriate emoji.
            4. Use friendly endings like "~에요/해요", "~했어요".

            [User Request]
            {query}

            [Your Summary]
            """

        elif query_type == "general_question":
            prompt = f"""\
            You are an AI assistant for the company's internal glossary service.
            The user has asked about a term that is not found in the company glossary.

            {history_context}

            Task: Politely inform the user that the term is not in the company glossary.
            You may briefly mention what it generally means in common usage, but make it clear this is not from the company glossary.

            [Response Guidelines]
            1. Be polite and helpful
            2. Clearly state the term is not in the company glossary
            3. You may provide general knowledge briefly, but emphasize it's not official company definition
            4. Suggest they check the spelling or try different terms

            [Tone & Style]
            1. Language: Always respond in Korean.
            2. Be warm and helpful.
            3. Use one appropriate emoji.
            4. Use friendly endings like "~에요/해요".

            [User Question]
            {query}

            [Your Response]
            """

        else:  # followup_question or glossary_lookup with no results
            prompt = f"""\
            You are an AI assistant for the company's internal glossary service.
            The user has asked about a term that is not found in the company glossary.

            {history_context}

            Task: Politely inform the user that the term is not in the company glossary.
            You may briefly mention what it generally means in common usage, but make it clear this is not from the company glossary.

            [Response Guidelines]
            1. Be polite and helpful
            2. Clearly state the term is not in the company glossary
            3. You may provide general knowledge briefly, but emphasize it's not official company definition
            4. Suggest they check the spelling or try different terms

            [Tone & Style]
            1. Language: Always respond in Korean.
            2. Be warm and helpful.
            3. Use one appropriate emoji.
            4. Use friendly endings like "~에요/해요".

            [User Question]
            {query}

            [Your Response]
            """

        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.4
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                return content[0].get('text', '응답 생성에 실패했습니다.')

            return '응답 생성에 실패했습니다.'

        except ClientError as e:
            logger.error(f"Bedrock API error during contextual response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        except Exception as e:
            logger.error(f"Unexpected error during contextual response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다."

    def _generate_metadata_response(self, query: str, metadata_type: str) -> str:
        """
        Generate response for metadata queries about the glossary.

        This method handles questions about the glossary itself (not specific terms),
        such as statistics and category information.

        Args:
            query: The user's original question
            metadata_type: Type of metadata requested (total_count, category_list,
                          count_by_category, or None for general overview)

        Returns:
            Natural language response with requested metadata
        """
        if not self.bedrock_client:
            return "용어집 서비스가 현재 사용 불가능합니다."

        # Step 1: Fetch metadata from database based on type
        metadata_info = ""

        try:
            if metadata_type == "total_count":
                # Query: "몇 개의 단어가 있어요?"
                total_count = self.repository.get_total_word_count()
                metadata_info = f"총 단어 수: {total_count}개"

            elif metadata_type == "category_list":
                # Query: "어떤 카테고리가 있나요?"
                categories = self.repository.get_all_categories()
                category_names = [cat['category_name'] for cat in categories]
                metadata_info = f"카테고리 목록 ({len(categories)}개):\n" + "\n".join([f"- {name}" for name in category_names])

            elif metadata_type == "count_by_category":
                # Query: "카테고리별로 몇 개씩 있어요?"
                counts = self.repository.get_count_by_category()
                metadata_info = "카테고리별 단어 수:\n" + "\n".join([f"- {item['category_name']}: {item['word_count']}개" for item in counts])

            else:
                # General metadata query - provide comprehensive information
                # Useful when classification is unclear or user asks broadly
                total_count = self.repository.get_total_word_count()
                counts = self.repository.get_count_by_category()
                metadata_info = f"총 단어 수: {total_count}개\n\n카테고리별 단어 수:\n"
                metadata_info += "\n".join([f"- {item['category_name']}: {item['word_count']}개" for item in counts])

        except Exception as e:
            logger.error(f"Error fetching metadata from database: {e}")
            return "용어집 정보를 가져오는 중 오류가 발생했습니다."

        # Step 2: Use LLM to generate natural, conversational response
        # Why LLM? Could just return the data, but LLM makes it friendlier and more natural
        prompt = f"""\
        You are an AI assistant for the company's internal glossary service.
        The user has asked about glossary statistics/metadata.

        [Glossary Metadata]
        {metadata_info}

        [Task]
        Provide a friendly, conversational response about the glossary statistics.
        Format the information in an easy-to-read way.

        [Response Guidelines]
        1. Present the statistics clearly with appropriate formatting (bullet points, numbers)
        2. Be conversational and helpful
        3. Use one appropriate emoji (📊, 📚, 📖, or 💡)
        4. Add a friendly closing remark encouraging them to search for terms
        5. Keep it concise but complete

        [Tone & Style]
        1. Language: Always respond in Korean
        2. Be warm and helpful
        3. Use friendly endings like "~에요/해요"
        4. Make statistics easy to understand

        [User Question]
        {query}

        [Your Response]
        """

        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.3  # Low temperature for consistent, factual responses
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                return content[0].get('text', '응답 생성에 실패했습니다.')

            return '응답 생성에 실패했습니다.'

        except ClientError as e:
            logger.error(f"Bedrock API error during metadata response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        except Exception as e:
            logger.error(f"Unexpected error during metadata response generation: {e}")
            return "응답 생성 중 오류가 발생했습니다."

    def _build_glossary_context(self, terms: List[GlossaryTerm]) -> str:
        """Build context string from glossary terms."""
        if not terms:
            return "검색된 용어가 없습니다."

        context_parts = []
        for term in terms:
            part = f"【{term.word_name}】"
            if term.word_english_name:
                part += f" ({term.word_english_name})"
            part += f"\n분류: {term.category}"
            part += f"\n정의: {term.definition}"
            context_parts.append(part)

        return "\n\n".join(context_parts)

    def query_glossary(self, query: str, session_id: str, conversation_history: List[Message]) -> Dict[str, Any]:
        """
        Main glossary query pipeline with conversation history support:
        1. Classify query type and extract terms using LLM
        2. Route to appropriate handler based on query type
        3. Generate natural language response

        Handles 6 query types:
        - metadata_query: Statistics about the glossary itself
        - glossary_lookup: Search for specific term definitions
        - greeting/summary_request/general_question: Conversational responses
        - followup_question: Context-aware term lookup
        """
        logger.info(f"Processing glossary query: {query[:100]}...")

        # Step 1: Classify query type and extract terms/metadata
        classification = self._classify_and_extract_terms(query, conversation_history)
        query_type = classification['query_type']
        metadata_type = classification.get('metadata_type')
        extracted_terms = classification['terms']

        logger.info(f"Query type: {query_type}, Metadata type: {metadata_type}, Extracted terms: {extracted_terms}")

        # Step 2: Route to appropriate handler based on query type
        found_terms = []

        # Route 1: Metadata queries (statistics, categories, help)
        if query_type == 'metadata_query':
            # NEW: Handle questions about the glossary itself
            # Examples: "몇 개?", "어떤 카테고리?", "사용법?"
            answer = self._generate_metadata_response(query, metadata_type)

        # Route 2: Conversational queries (no database lookup needed)
        elif query_type in ['greeting', 'summary_request', 'general_question']:
            # Handle greetings, conversation summaries, general chat
            answer = self._generate_contextual_response(query, query_type, conversation_history)

        # Route 3: Term lookup queries (search database for definitions)
        elif query_type in ['glossary_lookup', 'followup_question']:
            # Search database for terms
            if extracted_terms:
                found_terms = self.repository.search_terms(extracted_terms)

            if found_terms:
                # Found terms - generate response with definitions
                answer = self._generate_response(query, found_terms, conversation_history)
            else:
                # No terms found - generate "not found" response
                answer = self._generate_contextual_response(query, query_type, conversation_history)

        # Route 4: Unknown/fallback
        else:
            # Safety fallback for any unhandled query types
            logger.warning(f"Unknown query type '{query_type}', falling back to general question handler")
            answer = self._generate_contextual_response(query, 'general_question', conversation_history)

        # glossary_lookup으로 실제 DB 조회가 발생한 경우에만 쿼리 노출
        executed_query = None
        if query_type in ['glossary_lookup', 'followup_question'] and found_terms:
            executed_query = getattr(self.repository, 'last_executed_query', None)

        return {
            "answer": answer,
            "source_terms": found_terms,
            "session_id": session_id,
            "timestamp": datetime.now(),
            "executed_query": executed_query
        }

    async def query_glossary_async(
        self,
        request: GlossaryQueryRequest,
        conversation_history: List[Message]
    ) -> GlossaryQueryResponse:
        """
        Async wrapper for query_glossary with conversation history support.
        Runs blocking calls in thread pool to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            executor,
            self.query_glossary,
            request.query,
            request.session_id,
            conversation_history
        )

        return GlossaryQueryResponse(**result)

    def close(self):
        """Close database connection."""
        self.repository.close()


# Singleton instance
glossary_service = GlossaryService()
