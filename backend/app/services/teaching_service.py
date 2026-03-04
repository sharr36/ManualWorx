"""Teaching mode service — teach-then-troubleshoot, lessons, quizzes, learning paths."""

import json
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from ..config import settings
from ..database import set_tenant_context
from .ai_service import AIService
from .retrieval_service import RetrievalService


class TeachingService:
    """Handles teach-then-troubleshoot flow, lessons, quizzes, and learning paths."""

    def __init__(self):
        self.ai = AIService()
        self.retrieval = RetrievalService()

    # ── Teaching ──────────────────────────────────────────────

    async def explain_system(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        manual_id: str,
        system_area: str,
        depth: str = "standard",
    ) -> dict:
        """Generate a lesson explaining a system area from a manual."""
        # Retrieve pages relevant to the system area
        chunks = await self.retrieval.retrieve_chunks(
            pool,
            tenant_id,
            f"{system_area} system overview components operation",
            [manual_id],
            top_k=settings.MAX_PAGES_PER_QUERY,
        )

        lesson = await self.ai.generate_lesson(system_area, chunks, depth=depth)

        # Record familiarity if there's a mechanic context
        return {
            "system_area": system_area,
            "manual_id": manual_id,
            "depth": depth,
            "lesson_text": lesson["lesson_text"],
            "key_concepts": lesson["key_concepts"],
            "diagrams_referenced": lesson["diagrams_referenced"],
            "quiz_hooks": lesson["quiz_hooks"],
            "model_used": lesson["model_used"],
            "input_tokens": lesson["input_tokens"],
            "output_tokens": lesson["output_tokens"],
            "latency_ms": lesson["latency_ms"],
        }

    async def system_walkthrough(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        manual_id: str,
        system_area: str,
    ) -> dict:
        """Generate an interactive walkthrough with diagram references."""
        # Get diagram-enriched context
        chunks = await self.retrieval.retrieve_with_diagram_context(
            pool,
            tenant_id,
            f"{system_area} schematic diagram components flow",
            [manual_id],
            top_k=settings.MAX_PAGES_PER_QUERY,
        )

        lesson = await self.ai.generate_lesson(system_area, chunks, depth="full")

        # Find diagram pages in the context
        diagram_pages = [
            {
                "page_id": c["page_id"],
                "page_number": c.get("page_number", 0),
                "classification": c.get("classification", ""),
            }
            for c in chunks
            if c.get("classification", "").endswith(("_schematic", "_diagram", "_flowchart"))
        ]

        return {
            **lesson,
            "diagram_pages": diagram_pages,
            "walkthrough": True,
        }

    # ── Teach-Then-Troubleshoot Assist ───────────────────────

    async def start_assist(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        problem_description: str,
        machine_model: str | None = None,
        manual_ids: list[str] | None = None,
    ) -> dict:
        """Start a teach-then-troubleshoot session.

        1. Identify the system area from the problem description.
        2. Retrieve relevant manual pages.
        3. Return system info + three path choices.
        """
        # Identify the system area
        system_info = await self.ai.identify_system_area(problem_description)
        system_area = system_info["system_area"]

        # Retrieve context about this system
        search_query = f"{system_area} system {problem_description}"
        chunks = await self.retrieval.retrieve_chunks(
            pool, tenant_id, search_query, manual_ids, top_k=5
        )

        # Create an assist session record
        session_id = uuid4()
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """
                INSERT INTO queries (id, tenant_id, session_id, query_text, query_mode,
                                     manual_ids, response_text, model_used,
                                     input_tokens, output_tokens, cost_estimate, latency_ms)
                VALUES ($1, $2, $3, $4, 'troubleshoot', $5, $6, $7, 0, 0, 0, 0)
                """,
                session_id,
                tenant_id,
                session_id,
                problem_description,
                [UUID(m) for m in manual_ids] if manual_ids else None,
                json.dumps({"type": "assist_start", "system_area": system_area}),
                settings.DEFAULT_MODEL,
            )

        # Summary from top pages
        page_summary = []
        for c in chunks[:3]:
            page_summary.append({
                "page_number": c.get("page_number", 0),
                "classification": c.get("classification", "text"),
                "preview": (c.get("chunk_text", "") or "")[:150],
            })

        return {
            "session_id": str(session_id),
            "system_area": system_area,
            "system_confidence": system_info["confidence"],
            "related_systems": system_info["related_systems"],
            "manual_pages_found": len(chunks),
            "page_summary": page_summary,
            "choices": [
                {
                    "id": "teach_first",
                    "label": "Teach Me First",
                    "description": f"5-minute interactive lesson on the {system_area} system before troubleshooting",
                    "duration": "~5 min",
                },
                {
                    "id": "quick_overview",
                    "label": "Quick Overview",
                    "description": f"60-second brief on how the {system_area} system works",
                    "duration": "~1 min",
                },
                {
                    "id": "skip_to_fix",
                    "label": "Skip to Fix",
                    "description": "Jump straight to troubleshooting steps",
                    "duration": "immediate",
                },
            ],
        }

    async def assist_choice(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        session_id: UUID,
        choice: str,
        mechanic_id: UUID | None = None,
    ) -> dict:
        """Process the user's assist mode choice."""
        # Fetch the assist session
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                "SELECT query_text, response_text, manual_ids FROM queries WHERE id = $1 AND tenant_id = $2",
                session_id,
                tenant_id,
            )

        if not row:
            raise ValueError("Assist session not found")

        session_data = json.loads(row["response_text"])
        system_area = session_data["system_area"]
        problem = row["query_text"]
        manual_ids = [str(m) for m in row["manual_ids"]] if row["manual_ids"] else None

        if choice == "teach_first":
            lesson = await self.explain_system(
                pool, tenant_id, manual_ids[0] if manual_ids else "", system_area, depth="full"
            )
            # Record familiarity
            if mechanic_id:
                await self._record_familiarity(pool, mechanic_id, None, system_area, "full")
            return {"type": "lesson", "system_area": system_area, **lesson}

        elif choice == "quick_overview":
            lesson = await self.explain_system(
                pool, tenant_id, manual_ids[0] if manual_ids else "", system_area, depth="quick"
            )
            if mechanic_id:
                await self._record_familiarity(pool, mechanic_id, None, system_area, "quick")
            return {"type": "overview", "system_area": system_area, **lesson}

        else:  # skip_to_fix
            if mechanic_id:
                await self._record_familiarity(pool, mechanic_id, None, system_area, "skipped")
            return {
                "type": "skip",
                "system_area": system_area,
                "message": f"Proceeding directly to troubleshooting for: {problem}",
            }

    async def assist_continue(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        session_id: UUID,
    ) -> dict:
        """Continue assist session to troubleshooting after teaching."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                "SELECT query_text, response_text, manual_ids FROM queries WHERE id = $1 AND tenant_id = $2",
                session_id,
                tenant_id,
            )

        if not row:
            raise ValueError("Assist session not found")

        problem = row["query_text"]
        manual_ids = [str(m) for m in row["manual_ids"]] if row["manual_ids"] else None

        # Now do troubleshooting retrieval
        chunks = await self.retrieval.retrieve_chunks(
            pool, tenant_id, problem, manual_ids, top_k=settings.MAX_PAGES_PER_QUERY
        )

        # Generate troubleshooting response
        ai_result = await self.ai.generate_response(
            query_text=problem,
            query_mode="troubleshoot",
            context_chunks=chunks,
        )

        return {
            "type": "troubleshoot",
            "response_text": ai_result["response_text"],
            "confidence_score": ai_result["confidence_score"],
            "confidence_level": ai_result["confidence_level"],
            "sources": ai_result["sources"],
            "model_used": ai_result["model_used"],
        }

    # ── Quiz System ──────────────────────────────────────────

    async def generate_quiz(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        learning_path_id: UUID,
        module_index: int,
        count: int = 5,
    ) -> dict:
        """Generate quiz questions for a learning path module."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            path = await conn.fetchrow(
                "SELECT manual_id, modules, system_area FROM learning_paths WHERE id = $1 AND tenant_id = $2",
                learning_path_id,
                tenant_id,
            )

        if not path:
            raise ValueError("Learning path not found")

        modules = path["modules"] or []
        if module_index >= len(modules):
            raise ValueError(f"Module index {module_index} out of range")

        module = modules[module_index]
        system_area = module.get("title", path["system_area"] or "general")

        # Retrieve pages for this module's lessons
        page_ids = []
        for lesson in module.get("lessons", []):
            page_ids.extend(lesson.get("page_ids", []))

        # Get content for these pages
        chunks = []
        if page_ids and path["manual_id"]:
            chunks = await self.retrieval.retrieve_chunks(
                pool, tenant_id, system_area, [str(path["manual_id"])], top_k=10
            )

        questions = await self.ai.generate_quiz_questions(
            system_area, chunks, count=count
        )

        # Store generated questions
        stored_ids = []
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            for q in questions:
                qid = uuid4()
                await conn.execute(
                    """
                    INSERT INTO quiz_questions (id, tenant_id, question_type, question_text,
                                                options, correct_answer, explanation, difficulty)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    qid,
                    tenant_id,
                    q.get("question_type", "concept"),
                    q["question_text"],
                    json.dumps(q.get("options", {})),
                    q.get("correct_answer", ""),
                    q.get("explanation", ""),
                    "green",
                )
                stored_ids.append(str(qid))

        return {
            "learning_path_id": str(learning_path_id),
            "module_index": module_index,
            "module_title": module.get("title", ""),
            "questions": [
                {
                    "id": stored_ids[i] if i < len(stored_ids) else None,
                    **q,
                }
                for i, q in enumerate(questions)
            ],
        }

    async def submit_quiz(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        learning_path_id: UUID,
        module_index: int,
        answers: dict[str, str],
        mechanic_id: UUID | None = None,
    ) -> dict:
        """Score quiz answers and update progress."""
        # Fetch the questions
        question_ids = list(answers.keys())
        if not question_ids:
            return {"score": 0, "total": 0, "results": []}

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT id, question_text, correct_answer, explanation, question_type
                FROM quiz_questions
                WHERE id = ANY($1::uuid[]) AND tenant_id = $2
                """,
                [UUID(qid) for qid in question_ids],
                tenant_id,
            )

        correct = 0
        results = []
        for row in rows:
            qid = str(row["id"])
            user_answer = answers.get(qid, "")
            is_correct = user_answer.upper() == (row["correct_answer"] or "").upper()
            if is_correct:
                correct += 1
            results.append({
                "question_id": qid,
                "question_text": row["question_text"],
                "question_type": row["question_type"],
                "user_answer": user_answer,
                "correct_answer": row["correct_answer"],
                "is_correct": is_correct,
                "explanation": row["explanation"],
            })

        total = len(rows)
        score = round(correct / total * 100, 1) if total > 0 else 0

        # Update learning progress
        if mechanic_id:
            async with pool.acquire() as conn:
                await set_tenant_context(conn, tenant_id)
                await conn.execute(
                    """
                    INSERT INTO learning_progress
                        (id, tenant_id, mechanic_id, learning_path_id, module_index,
                         status, quiz_scores, completed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (mechanic_id, learning_path_id, module_index, lesson_index)
                    DO UPDATE SET quiz_scores = $7, status = $6, completed_at = $8
                    """,
                    uuid4(),
                    tenant_id,
                    mechanic_id,
                    learning_path_id,
                    module_index,
                    "completed" if score >= 70 else "in_progress",
                    json.dumps({"score": score, "correct": correct, "total": total}),
                    datetime.now() if score >= 70 else None,
                )

        return {
            "learning_path_id": str(learning_path_id),
            "module_index": module_index,
            "score": score,
            "correct": correct,
            "total": total,
            "passed": score >= 70,
            "results": results,
        }

    # ── Learning Paths ───────────────────────────────────────

    async def generate_learning_path(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        manual_id: str,
    ) -> dict:
        """Auto-generate a learning path from a manual's content structure."""
        # Fetch manual and its pages
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            manual = await conn.fetchrow(
                "SELECT id, title, make, model FROM manuals WHERE id = $1 AND tenant_id = $2",
                UUID(manual_id),
                tenant_id,
            )
            if not manual:
                raise ValueError("Manual not found")

            pages = await conn.fetch(
                """
                SELECT page_number, classification, LEFT(extracted_text, 300) as preview
                FROM pages
                WHERE manual_id = $1
                ORDER BY page_number
                """,
                UUID(manual_id),
            )

        # Group pages by classification to identify system areas
        class_groups: dict[str, list] = {}
        for p in pages:
            cls = p["classification"] or "text"
            class_groups.setdefault(cls, []).append({
                "page_number": p["page_number"],
                "preview": p["preview"] or "",
            })

        # Build a content summary for Claude
        summary_lines = [f"Manual: {manual['title']}"]
        if manual["make"]:
            summary_lines.append(f"Make: {manual['make']}, Model: {manual['model'] or 'N/A'}")
        summary_lines.append(f"Total pages: {len(pages)}")
        for cls, group_pages in class_groups.items():
            page_nums = [str(p["page_number"]) for p in group_pages[:10]]
            summary_lines.append(f"  {cls}: pages {', '.join(page_nums)} ({len(group_pages)} total)")

        # Ask Claude to generate a learning path structure
        prompt = f"""Based on this service manual structure, generate a learning path for a mechanic.

{chr(10).join(summary_lines)}

Sample page previews:
{chr(10).join(p['preview'][:100] for p in (pages[:5] if pages else []))}

Generate a structured learning path with 3-6 modules, each with 2-4 lessons.
Focus on practical skills: system understanding → component identification → service procedures → troubleshooting.

Return JSON only:
```json
{{
  "title": "Learning path title",
  "system_area": "primary system area",
  "modules": [
    {{
      "index": 0,
      "title": "Module title",
      "lessons": [
        {{
          "index": 0,
          "title": "Lesson title",
          "page_ids": [],
          "description": "What this lesson covers"
        }}
      ],
      "quiz_question_count": 5
    }}
  ]
}}
```"""

        response = await self.ai.client.messages.create(
            model=settings.DEFAULT_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            path_data = json.loads(text)
        except json.JSONDecodeError:
            path_data = {
                "title": f"{manual['title']} Learning Path",
                "system_area": "general",
                "modules": [],
            }

        # Store the learning path
        path_id = uuid4()
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """
                INSERT INTO learning_paths (id, tenant_id, manual_id, title, system_area, modules, auto_generated)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                """,
                path_id,
                tenant_id,
                UUID(manual_id),
                path_data.get("title", f"{manual['title']} Learning Path"),
                path_data.get("system_area", "general"),
                json.dumps(path_data.get("modules", [])),
            )

        return {
            "id": str(path_id),
            "manual_id": manual_id,
            "title": path_data.get("title", ""),
            "system_area": path_data.get("system_area", "general"),
            "modules": path_data.get("modules", []),
            "auto_generated": True,
        }

    async def list_learning_paths(
        self, pool: asyncpg.Pool, tenant_id: UUID
    ) -> list[dict]:
        """List all learning paths for a tenant."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT lp.id, lp.manual_id, lp.title, lp.system_area,
                       lp.modules, lp.auto_generated, lp.created_at,
                       m.title as manual_title
                FROM learning_paths lp
                LEFT JOIN manuals m ON lp.manual_id = m.id
                WHERE lp.tenant_id = $1
                ORDER BY lp.created_at DESC
                """,
                tenant_id,
            )

        return [
            {
                "id": str(r["id"]),
                "manual_id": str(r["manual_id"]) if r["manual_id"] else None,
                "title": r["title"],
                "system_area": r["system_area"],
                "modules": r["modules"] or [],
                "module_count": len(r["modules"] or []),
                "auto_generated": r["auto_generated"],
                "manual_title": r["manual_title"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    async def get_learning_path(
        self, pool: asyncpg.Pool, tenant_id: UUID, path_id: UUID
    ) -> dict | None:
        """Get a learning path with its modules."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT lp.id, lp.manual_id, lp.title, lp.system_area,
                       lp.modules, lp.auto_generated, lp.created_at,
                       m.title as manual_title
                FROM learning_paths lp
                LEFT JOIN manuals m ON lp.manual_id = m.id
                WHERE lp.id = $1 AND lp.tenant_id = $2
                """,
                path_id,
                tenant_id,
            )

        if not row:
            return None

        return {
            "id": str(row["id"]),
            "manual_id": str(row["manual_id"]) if row["manual_id"] else None,
            "title": row["title"],
            "system_area": row["system_area"],
            "modules": row["modules"] or [],
            "auto_generated": row["auto_generated"],
            "manual_title": row["manual_title"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    # ── Mechanic Management ──────────────────────────────────

    async def create_mechanic(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        name: str,
        user_id: UUID | None = None,
        skill_level: str = "green",
    ) -> dict:
        """Register a mechanic profile."""
        mechanic_id = uuid4()
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            await conn.execute(
                """
                INSERT INTO mechanics (id, tenant_id, user_id, name, skill_level, start_date)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                mechanic_id,
                tenant_id,
                user_id,
                name,
                skill_level,
            )

        return {
            "id": str(mechanic_id),
            "tenant_id": str(tenant_id),
            "name": name,
            "skill_level": skill_level,
        }

    async def get_mechanic_dashboard(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        mechanic_id: UUID,
    ) -> dict:
        """Get a mechanic's learning dashboard with progress summary."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)

            # Mechanic info
            mechanic = await conn.fetchrow(
                "SELECT id, name, skill_level, start_date, created_at FROM mechanics WHERE id = $1 AND tenant_id = $2",
                mechanic_id,
                tenant_id,
            )
            if not mechanic:
                raise ValueError("Mechanic not found")

            # Learning progress
            progress_rows = await conn.fetch(
                """
                SELECT lp.module_index, lp.lesson_index, lp.status, lp.quiz_scores,
                       lp.time_spent_seconds, lp.completed_at,
                       path.title as path_title, path.id as path_id
                FROM learning_progress lp
                JOIN learning_paths path ON lp.learning_path_id = path.id
                WHERE lp.mechanic_id = $1 AND lp.tenant_id = $2
                ORDER BY lp.created_at DESC
                """,
                mechanic_id,
                tenant_id,
            )

            # System familiarity
            familiarity_rows = await conn.fetch(
                """
                SELECT system_area, machine_model, teach_depth, quiz_score,
                       troubleshoot_count, last_troubleshoot_at, taught_at
                FROM system_familiarity
                WHERE mechanic_id = $1
                ORDER BY taught_at DESC NULLS LAST
                """,
                mechanic_id,
            )

        # Aggregate stats
        completed_modules = sum(1 for p in progress_rows if p["status"] == "completed")
        total_time = sum(p["time_spent_seconds"] or 0 for p in progress_rows)
        quiz_scores = []
        for p in progress_rows:
            if p["quiz_scores"]:
                scores = p["quiz_scores"] if isinstance(p["quiz_scores"], dict) else json.loads(p["quiz_scores"])
                if "score" in scores:
                    quiz_scores.append(scores["score"])

        avg_quiz = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None

        # Group progress by learning path
        paths_progress: dict[str, dict] = {}
        for p in progress_rows:
            pid = str(p["path_id"])
            if pid not in paths_progress:
                paths_progress[pid] = {
                    "path_id": pid,
                    "path_title": p["path_title"],
                    "completed": 0,
                    "in_progress": 0,
                    "not_started": 0,
                }
            status = p["status"] or "not_started"
            paths_progress[pid][status] = paths_progress[pid].get(status, 0) + 1

        return {
            "mechanic": {
                "id": str(mechanic["id"]),
                "name": mechanic["name"],
                "skill_level": mechanic["skill_level"],
                "start_date": mechanic["start_date"].isoformat() if mechanic["start_date"] else None,
            },
            "stats": {
                "completed_modules": completed_modules,
                "total_time_seconds": total_time,
                "average_quiz_score": avg_quiz,
                "systems_learned": len(familiarity_rows),
            },
            "learning_paths": list(paths_progress.values()),
            "system_familiarity": [
                {
                    "system_area": f["system_area"],
                    "machine_model": f["machine_model"],
                    "teach_depth": f["teach_depth"],
                    "quiz_score": float(f["quiz_score"]) if f["quiz_score"] else None,
                    "troubleshoot_count": f["troubleshoot_count"],
                }
                for f in familiarity_rows
            ],
        }

    async def get_learning_progress(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        path_id: UUID,
        mechanic_id: UUID,
    ) -> dict:
        """Get a mechanic's progress on a specific learning path."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            path = await conn.fetchrow(
                "SELECT id, title, modules FROM learning_paths WHERE id = $1 AND tenant_id = $2",
                path_id,
                tenant_id,
            )
            if not path:
                raise ValueError("Learning path not found")

            rows = await conn.fetch(
                """
                SELECT module_index, lesson_index, status, quiz_scores,
                       time_spent_seconds, completed_at
                FROM learning_progress
                WHERE mechanic_id = $1 AND learning_path_id = $2 AND tenant_id = $3
                ORDER BY module_index, lesson_index
                """,
                mechanic_id,
                path_id,
                tenant_id,
            )

        modules = path["modules"] or []
        total_modules = len(modules)
        completed = sum(1 for r in rows if r["status"] == "completed")

        progress_by_module: dict[int, list] = {}
        for r in rows:
            mi = r["module_index"] or 0
            progress_by_module.setdefault(mi, []).append({
                "lesson_index": r["lesson_index"],
                "status": r["status"],
                "quiz_scores": r["quiz_scores"],
                "time_spent_seconds": r["time_spent_seconds"] or 0,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            })

        return {
            "learning_path_id": str(path_id),
            "mechanic_id": str(mechanic_id),
            "path_title": path["title"],
            "completed_modules": completed,
            "total_modules": total_modules,
            "module_progress": progress_by_module,
        }

    # ── Helpers ───────────────────────────────────────────────

    async def _record_familiarity(
        self,
        pool: asyncpg.Pool,
        mechanic_id: UUID,
        machine_model: str | None,
        system_area: str,
        teach_depth: str,
    ):
        """Record that a mechanic was taught about a system."""
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_familiarity
                    (id, mechanic_id, machine_model, system_area, teach_depth, taught_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (mechanic_id, machine_model, system_area)
                DO UPDATE SET teach_depth = $5, taught_at = NOW()
                """,
                uuid4(),
                mechanic_id,
                machine_model or "",
                system_area,
                teach_depth,
            )
