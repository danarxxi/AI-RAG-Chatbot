from typing import List
from sqlalchemy import text
from app.config import get_settings
from app.models.glossary import GlossaryTerm
from app.services.database.base import GlossaryRepository
from app.database.engine import engine
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger(__name__)


class PostgreSQLGlossaryRepository(GlossaryRepository):
    """PostgreSQL database implementation of GlossaryRepository using SQLAlchemy Core."""

    def __init__(self):
        self.last_executed_query: str = ""

    def search_terms(self, keywords: List[str]) -> List[GlossaryTerm]:
        """Search glossary terms by keywords using ILIKE pattern matching."""
        if not keywords:
            return []

        try:
            with engine.connect() as conn:
                # Build WHERE clause for multiple keywords with OR
                where_conditions = []
                readable_conditions = []
                params = {}
                for idx, keyword in enumerate(keywords):
                    a_key = f"kw{idx}_a"
                    b_key = f"kw{idx}_b"
                    where_conditions.append(
                        f"(w.WORD_NAME ILIKE :{a_key} OR w.WORD_ENGLISH_NAME ILIKE :{b_key})"
                    )
                    readable_conditions.append(
                        f"(w.WORD_NAME ILIKE '%{keyword}%' OR w.WORD_ENGLISH_NAME ILIKE '%{keyword}%')"
                    )
                    pattern = f"%{keyword}%"
                    params[a_key] = pattern
                    params[b_key] = pattern

                where_clause = " OR ".join(where_conditions)
                readable_where = " OR ".join(readable_conditions)
                params["limit"] = settings.glossary_search_limit

                # 화면 표시용 readable 쿼리 저장 (실제 값 치환)
                self.last_executed_query = (
                    "SELECT\n"
                    "    w.WORD_ID,\n"
                    "    w.WORD_NAME,\n"
                    "    w.WORD_ENGLISH_NAME,\n"
                    "    w.TEXT_CONTENTS,\n"
                    "    d.DICTIONARY_NAME\n"
                    "FROM aichat.tb_glossary_term w\n"
                    "JOIN aichat.tb_glossary_category d\n"
                    "  ON w.DICTIONARY_ID = d.DICTIONARY_ID\n"
                    f"WHERE {readable_where}\n"
                    f"LIMIT {settings.glossary_search_limit}"
                )

                query = text(f"""
                    SELECT
                        w.WORD_ID,
                        w.WORD_NAME,
                        w.WORD_ENGLISH_NAME,
                        w.TEXT_CONTENTS,
                        d.DICTIONARY_NAME
                    FROM aichat.tb_glossary_term w
                    JOIN aichat.tb_glossary_category d ON w.DICTIONARY_ID = d.DICTIONARY_ID
                    WHERE {where_clause}
                    LIMIT :limit
                """)

                rows = conn.execute(query, params).fetchall()

            terms = [
                GlossaryTerm(
                    word_id=row[0],
                    word_name=row[1],
                    word_english_name=row[2],
                    definition=row[3] or "",
                    category=row[4],
                )
                for row in rows
            ]

            logger.info(f"Found {len(terms)} glossary terms for keywords: {keywords}")
            return terms

        except Exception as e:
            logger.error(f"Error searching glossary terms: {e}")
            return []

    def get_term_by_name(self, term_name: str) -> List[GlossaryTerm]:
        """Get glossary terms matching the exact or partial name."""
        return self.search_terms([term_name])

    def get_total_word_count(self) -> int:
        """Get total number of words in the glossary."""
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM aichat.tb_glossary_term")
                ).fetchone()
                count = result[0] if result else 0
                logger.info(f"Total word count: {count}")
                return count
        except Exception as e:
            logger.error(f"Error getting total word count: {e}")
            return 0

    def get_all_categories(self) -> List[dict]:
        """Get all unique categories from the glossary."""
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT DISTINCT
                        d.DICTIONARY_ID,
                        d.DICTIONARY_NAME
                    FROM aichat.tb_glossary_category d
                    ORDER BY d.DICTIONARY_NAME
                """)).fetchall()

            categories = [
                {"category_id": row[0], "category_name": row[1]}
                for row in rows
            ]
            logger.info(f"Found {len(categories)} categories")
            return categories
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def get_count_by_category(self) -> List[dict]:
        """Get word count grouped by category."""
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        d.DICTIONARY_NAME,
                        COUNT(w.WORD_ID) as word_count
                    FROM aichat.tb_glossary_term w
                    JOIN aichat.tb_glossary_category d ON w.DICTIONARY_ID = d.DICTIONARY_ID
                    GROUP BY d.DICTIONARY_NAME
                    ORDER BY word_count DESC, d.DICTIONARY_NAME
                """)).fetchall()

            results = [
                {"category_name": row[0], "word_count": row[1]}
                for row in rows
            ]
            logger.info(f"Word count by category: {len(results)} categories")
            return results
        except Exception as e:
            logger.error(f"Error getting count by category: {e}")
            return []

    def close(self) -> None:
        """SQLAlchemy 엔진은 풀을 자체 관리하므로 별도 종료 불필요."""
        pass
