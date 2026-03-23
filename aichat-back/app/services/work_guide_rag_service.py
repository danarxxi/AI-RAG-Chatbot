import os
import json
import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings
from app.models.session import Message
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger(__name__, service_type="WORK_GUIDE")

# Thread pool for running blocking Bedrock calls
# max_workers=20 allows up to 20 concurrent Bedrock API calls
executor = ThreadPoolExecutor(max_workers=20)


class WorkGuideRAGService:
    """RAG service for Work Guide using Amazon Bedrock Knowledge Base and Nova model."""

    def __init__(self):
        # Initialize Bedrock clients
        self.bedrock_agent_runtime = None
        self.bedrock_runtime = None

        if settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                self.bedrock_agent_runtime = boto3.client(
                    'bedrock-agent-runtime',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key
                )
                self.bedrock_runtime = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key
                )
                logger.info("Bedrock clients initialized successfully for Work Guide")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock clients: {e}")
        else:
            logger.warning("AWS credentials not configured - Work Guide service will use mock responses")

    def retrieve_context(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from Work Guide Knowledge Base.
        """
        if not self.bedrock_agent_runtime or not settings.work_guide_knowledge_base_id:
            logger.warning("Work Guide Knowledge Base not configured, returning empty context")
            return []

        try:
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=settings.work_guide_knowledge_base_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results
                    }
                }
            )

            results = response.get('retrievalResults', [])

            # Log all document scores for threshold tuning
            if results:
                scores = []
                for idx, result in enumerate(results, 1):
                    score = result.get('score', 0)
                    scores.append(f"Doc{idx}: {score:.3f}")
                logger.info(f"Retrieved {len(results)} documents - Scores: [{', '.join(scores)}]")
            else:
                logger.info("Retrieved 0 documents from Knowledge Base")

            return results

        except ClientError as e:
            logger.error(f"Error retrieving from Knowledge Base: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in retrieve_context: {e}")
            return []

    def build_prompt(
        self,
        query: str,
        context_documents: List[Dict[str, Any]],
        conversation_history: List[Message]
    ) -> Dict[str, str]:
        """
        Build prompt with context and conversation history for Work Guide.
        Returns dict with 'system' and 'user_message' keys.
        """
        # System instruction for Work Guide (different from HR service)
        system_prompt = """\
        You are an AI assistant providing internal work guides for new employees. Your role is to help new hires understand work manuals (such as internal system installation and usage manuals) while maintaining a friendly and supportive attitude.

        ## Core Principle: Truthfulness

        **Never provide unverified or uncertain information.**

        ## CRITICAL: Handling Questions Without Knowledge Base Context

        If no relevant documents are retrieved from the knowledge base, or if the retrieved context does not contain information related to the user's question, you **MUST** respond with:

        현재 제공된 자료에서는 해당 정보를 찾을 수 없습니다.
        관련 부서에 직접 문의해 주시기 바랍니다.

        Never attempt to answer questions based on general knowledge or assumptions when the information is not explicitly present in the retrieved work guide documents.

        **DO NOT:**
        - ❌ Make assumptions or guesses
        - ❌ Provide information that is not explicitly in the retrieved documents
        - ❌ Attempt to answer based on general knowledge
        - ❌ Use phrases like "일반적으로..." (generally...), "보통..." (usually...), "아마도..." (Probably...), "~일 것 같습니다" (It seems like...)
        - ❌ Reference document markers or repeat prompt structure in your response

        **Instead:**
        - ✅ Naturally refer to information as coming from "업무 가이드" or "업무 매뉴얼"
        - ✅ Clearly state when you don't know: "알 수 없습니다" / "확실하지 않습니다"
        - ✅ Provide clear, direct answers **only when the information is explicitly found** in the retrieved work guide documentation

        ## Language and Tone

        - **Language**: Always respond in **Korean** (한국어).
        - **Tone**: Use a **soft, gentle, and friendly tone**. Be warm and approachable. Use approximately 1 appropriate emoji based on the context.
        - **Natural Speech**: Vary your expressions to sound natural and human. Avoid robotic patterns.
        - **CRITICAL - Tone Override**: The work guide documents may be written in formal language. You MUST NOT copy this formal tone. Instead:
            - Translate formal procedures into warm, conversational Korean
            - Use friendly endings: ~하시면 돼요, ~해 주세요, ~하실 수 있어요
            - Avoid stiff endings: ~하여야 합니다, ~할 것, ~하는 바입니다
            - Speak like a helpful senior colleague, NOT like a procedure manual
            - Make information accessible and easy to understand

        ## Formatting Rules

        - When presenting structured or comparative data (e.g. system specs, settings, schedules), use **Markdown table format**:
            ```
            | 항목 | 내용 | 비고 |
            |------|------|------|
            | 설치 경로 | C:\\Program | 기본값 |
            ```
        - Use bullet points or numbered lists for step-by-step procedures
        - Use **bold** for key terms or important values
        - Add blank lines between paragraphs for readability

        ## Critical Rules

        1. Check if the retrieved context actually contains relevant information
        2. If context is empty or irrelevant, use the standard "cannot find" response
        3. Before answering, verify that every piece of information is supported by the retrieved context
        4. NEVER include <document>, </document>, or any XML-like tags in your response
        5. NEVER generate fake "User question:" or simulate user messages
        6. ONLY answer the current question - do NOT continue the conversation
        7. Your response should contain ONLY your answer, nothing else
        """

        # Build user message with context and query only
        user_parts = []

        # Add context from Knowledge Base
        user_parts.append("Here are the relevant work guide documents:\n")
        for idx, doc in enumerate(context_documents, 1):
            content = doc.get('content', {}).get('text', '')
            if content:
                user_parts.append(f"<document>\n{content}\n</document>\n")

        # Add conversation history (last few turns) if exists
        if conversation_history:
            user_parts.append("\nPrevious conversation:")
            for msg in conversation_history[-6:]:  # Last 3 turns
                user_parts.append(f"{msg.content}")

        # Add current query
        user_parts.append(f"\nUser question: {query}")

        return {
            "system": system_prompt,
            "user_message": "\n".join(user_parts)
        }

    def generate_response(self, system: str, user_message: str) -> str:
        """
        Generate response using Bedrock Claude model with proper system parameter.
        """
        if not self.bedrock_runtime:
            logger.warning("Bedrock runtime not configured, returning mock response")
            return "I'm a mock response. Please configure AWS Bedrock to get real answers from the work guide manual."

        try:
            # Prepare request for Bedrock Claude model with system parameter
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system,  # System instructions sent separately
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_message}]
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.3,
                "top_p": 0.9
            }

            response = self.bedrock_runtime.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Extract text from response format (Claude format)
            # Claude returns: {"content": [{"type": "text", "text": "..."}], ...}
            content = response_body.get('content', [])

            if content and len(content) > 0:
                answer = content[0].get('text', 'Sorry, I could not generate a response.')
            else:
                answer = 'Sorry, I could not generate a response.'

            logger.info(f"Successfully generated response using {settings.bedrock_model_id}")
            return answer

        except ClientError as e:
            error_message = str(e)
            logger.error(f"Error invoking Bedrock model: {error_message}")
            return f"Sorry, I encountered an error generating a response. Please try again later."
        except Exception as e:
            logger.error(f"Unexpected error in generate_response: {e}")
            return "Sorry, an unexpected error occurred. Please try again later."

    def get_rag_response(
        self,
        query: str,
        conversation_history: List[Message]
    ) -> Dict[str, Any]:
        """
        Main RAG pipeline: retrieve context, build prompt, generate response.
        Returns both the response and source documents.
        """
        logger.info(f"Processing Work Guide RAG query: {query[:100]}...")

        # Step 1: Retrieve relevant context from Knowledge Base
        context_documents = self.retrieve_context(query)

        # Early return: If no documents found, return fixed message without calling LLM
        if not context_documents:
            logger.info("No documents above threshold - returning 'cannot find' message without LLM call")
            return {
                'response': '현재 제공된 자료에서는 해당 정보를 찾을 수 없습니다. 관련 부서에 직접 문의해 주시기 바랍니다.',
                'sources': []
            }

        # Step 2: Build prompt with context and history (only when documents exist)
        prompt_dict = self.build_prompt(query, context_documents, conversation_history)

        # Step 3: Generate response using Claude model with proper system parameter
        response = self.generate_response(
            system=prompt_dict['system'],
            user_message=prompt_dict['user_message']
        )

        # Step 4: Format sources for frontend (filter by display threshold)
        sources = []
        hidden_count = 0

        for doc in context_documents:
            score = doc.get('score')

            # Handle missing score field
            if score is None:
                logger.warning(f"Document missing score field, defaulting to 0")
                score = 0

            content = doc.get('content', {}).get('text', '')
            content = content.replace('*', '')  # Remove asterisks for better readability
            metadata = doc.get('metadata', {})

            # Extract document name from metadata or S3 URI
            document_name = metadata.get('document-title', '')
            if not document_name:
                # Fallback to filename from S3 URI
                s3_uri = doc.get('location', {}).get('s3Location', {}).get('uri', '')
                if s3_uri:
                    document_name = s3_uri.split('/')[-1]
                else:
                    document_name = '출처 문서'

            # Clean document name: remove file extension
            document_name = os.path.splitext(document_name)[0]

            # Apply display threshold
            if score >= settings.rag_display_threshold:
                sources.append({
                    'content': content,
                    'document_name': document_name,
                    'score': score
                })
            else:
                hidden_count += 1
                logger.debug(f"Hiding source '{document_name}' from display (score: {score:.3f} < {settings.rag_display_threshold})")

        # Log summary for debugging
        if hidden_count > 0:
            logger.info(f"Sources: {len(sources)} displayed, {hidden_count} hidden (below threshold {settings.rag_display_threshold})")
        else:
            logger.info(f"Returning response with {len(sources)} source documents")

        return {
            'response': response,
            'sources': sources
        }

    async def get_rag_response_async(
        self,
        query: str,
        conversation_history: List[Message]
    ) -> Dict[str, Any]:
        """
        Async wrapper for get_rag_response.
        Runs blocking Bedrock calls in thread pool to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()

        # Run the blocking method in thread pool
        result = await loop.run_in_executor(
            executor,
            self.get_rag_response,
            query,
            conversation_history
        )

        return result
