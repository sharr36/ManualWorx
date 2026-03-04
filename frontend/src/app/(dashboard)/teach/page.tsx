"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  Brain,
  CheckCircle,
  ChevronRight,
  GraduationCap,
  Loader2,
  Plus,
  Send,
  Trophy,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api-client";

interface LearningPath {
  id: string;
  manual_id: string | null;
  title: string;
  system_area: string;
  modules: Module[];
  module_count?: number;
  auto_generated: boolean;
  manual_title?: string;
}

interface Module {
  index: number;
  title: string;
  lessons: { index: number; title: string; description?: string }[];
  quiz_question_count: number;
}

interface QuizQuestion {
  id: string;
  question_type: string;
  question_text: string;
  options: Record<string, string>;
  correct_answer: string;
  explanation?: string;
}

interface QuizResult {
  question_id: string;
  question_text: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation?: string;
}

interface AssistSession {
  session_id: string;
  system_area: string;
  system_confidence: number;
  related_systems: string[];
  choices: { id: string; label: string; description: string; duration: string }[];
}

type View = "home" | "assist" | "lesson" | "quiz" | "results" | "path";

export default function TeachPage() {
  const [view, setView] = useState<View>("home");
  const [paths, setPaths] = useState<LearningPath[]>([]);
  const [selectedPath, setSelectedPath] = useState<LearningPath | null>(null);
  const [loadingPaths, setLoadingPaths] = useState(true);

  // Assist mode state
  const [problem, setProblem] = useState("");
  const [assistLoading, setAssistLoading] = useState(false);
  const [assistSession, setAssistSession] = useState<AssistSession | null>(null);

  // Lesson state
  const [lessonText, setLessonText] = useState("");
  const [lessonMeta, setLessonMeta] = useState<{
    key_concepts: string[];
    system_area: string;
  } | null>(null);
  const [lessonLoading, setLessonLoading] = useState(false);

  // Quiz state
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [quizResults, setQuizResults] = useState<{
    score: number;
    passed: boolean;
    results: QuizResult[];
  } | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [activeModule, setActiveModule] = useState(0);

  // Load learning paths
  const loadPaths = useCallback(async () => {
    try {
      const data = await api.get<LearningPath[]>("/api/paths");
      setPaths(data);
    } catch {
      // No paths yet
    } finally {
      setLoadingPaths(false);
    }
  }, []);

  useEffect(() => {
    loadPaths();
  }, [loadPaths]);

  // --- Assist flow ---
  const startAssist = async () => {
    if (!problem.trim()) return;
    setAssistLoading(true);
    try {
      const data = await api.post<AssistSession>("/api/assist", {
        problem_description: problem.trim(),
      });
      setAssistSession(data);
      setView("assist");
    } catch (e) {
      console.error(e);
    } finally {
      setAssistLoading(false);
    }
  };

  const chooseAssistPath = async (choice: string) => {
    if (!assistSession) return;
    setLessonLoading(true);
    try {
      const data = await api.post<Record<string, unknown>>(
        `/api/assist/${assistSession.session_id}/choice`,
        { choice }
      );
      if (data.type === "skip") {
        // Continue to troubleshooting
        const result = await api.post<Record<string, unknown>>(
          `/api/assist/${assistSession.session_id}/continue`,
          {}
        );
        setLessonText(result.response_text as string);
        setLessonMeta({
          key_concepts: [],
          system_area: assistSession.system_area,
        });
      } else {
        setLessonText(data.lesson_text as string);
        setLessonMeta({
          key_concepts: (data.key_concepts as string[]) || [],
          system_area: data.system_area as string,
        });
      }
      setView("lesson");
    } catch (e) {
      console.error(e);
    } finally {
      setLessonLoading(false);
    }
  };

  const continueToTroubleshoot = async () => {
    if (!assistSession) return;
    setLessonLoading(true);
    try {
      const result = await api.post<Record<string, unknown>>(
        `/api/assist/${assistSession.session_id}/continue`,
        {}
      );
      setLessonText(result.response_text as string);
      setLessonMeta({
        key_concepts: [],
        system_area: assistSession.system_area,
      });
      setView("lesson");
    } catch (e) {
      console.error(e);
    } finally {
      setLessonLoading(false);
    }
  };

  // --- Quiz flow ---
  const startQuiz = async (pathId: string, moduleIndex: number) => {
    setQuizLoading(true);
    setActiveModule(moduleIndex);
    try {
      const data = await api.post<{
        questions: QuizQuestion[];
        module_title: string;
      }>("/api/teach/quiz/generate", {
        learning_path_id: pathId,
        module_index: moduleIndex,
      });
      setQuestions(data.questions);
      setAnswers({});
      setQuizResults(null);
      setView("quiz");
    } catch (e) {
      console.error(e);
    } finally {
      setQuizLoading(false);
    }
  };

  const submitQuiz = async () => {
    if (!selectedPath) return;
    setQuizLoading(true);
    try {
      const data = await api.post<{
        score: number;
        passed: boolean;
        results: QuizResult[];
      }>("/api/teach/quiz/submit", {
        learning_path_id: selectedPath.id,
        module_index: activeModule,
        answers,
      });
      setQuizResults(data);
      setView("results");
    } catch (e) {
      console.error(e);
    } finally {
      setQuizLoading(false);
    }
  };

  // --- Learning path generation ---
  const [manuals, setManuals] = useState<{ id: string; title: string }[]>([]);
  const [genLoading, setGenLoading] = useState(false);

  useEffect(() => {
    api
      .get<{ id: string; title: string }[]>("/api/manuals")
      .then(setManuals)
      .catch(() => {});
  }, []);

  const generatePath = async (manualId: string) => {
    setGenLoading(true);
    try {
      const path = await api.post<LearningPath>("/api/paths/generate", {
        manual_id: manualId,
      });
      setPaths((prev) => [path, ...prev]);
      setSelectedPath(path);
      setView("path");
    } catch (e) {
      console.error(e);
    } finally {
      setGenLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      {/* Left panel — Learning paths */}
      <div className="w-72 shrink-0 space-y-4 overflow-y-auto border-r pr-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Learning Paths</h2>
        </div>

        {loadingPaths ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading...
          </div>
        ) : paths.length === 0 ? (
          <div className="rounded-lg border border-dashed p-4 text-center">
            <GraduationCap className="mx-auto mb-2 h-8 w-8 text-slate-300" />
            <p className="text-xs text-muted-foreground">
              No learning paths yet
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {paths.map((p) => (
              <button
                key={p.id}
                className={`w-full rounded-lg border p-3 text-left text-sm transition hover:bg-slate-50 ${
                  selectedPath?.id === p.id
                    ? "border-emerald-500 bg-emerald-50"
                    : ""
                }`}
                onClick={() => {
                  setSelectedPath(p);
                  setView("path");
                }}
              >
                <p className="font-medium line-clamp-1">{p.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {p.module_count || p.modules?.length || 0} modules
                  {p.manual_title && ` · ${p.manual_title}`}
                </p>
              </button>
            ))}
          </div>
        )}

        {/* Generate from manual */}
        <div className="border-t pt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Generate from Manual
          </p>
          {manuals.map((m) => (
            <button
              key={m.id}
              disabled={genLoading}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-slate-100 disabled:opacity-50"
              onClick={() => generatePath(m.id)}
            >
              <Plus className="h-3.5 w-3.5 text-emerald-600" />
              <span className="line-clamp-1">{m.title}</span>
            </button>
          ))}
          {genLoading && (
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Generating...
            </div>
          )}
        </div>
      </div>

      {/* Right panel — Content */}
      <div className="flex-1 space-y-4 overflow-y-auto">
        {view === "home" && <HomeView onStartAssist={startAssist} problem={problem} setProblem={setProblem} assistLoading={assistLoading} />}

        {view === "assist" && assistSession && (
          <AssistView
            session={assistSession}
            onChoose={chooseAssistPath}
            loading={lessonLoading}
          />
        )}

        {view === "lesson" && (
          <LessonView
            text={lessonText}
            meta={lessonMeta}
            loading={lessonLoading}
            onContinue={
              assistSession ? continueToTroubleshoot : () => setView("home")
            }
            onBack={() => setView("home")}
            showContinue={!!assistSession}
          />
        )}

        {view === "quiz" && (
          <QuizView
            questions={questions}
            answers={answers}
            setAnswers={setAnswers}
            onSubmit={submitQuiz}
            loading={quizLoading}
          />
        )}

        {view === "results" && quizResults && (
          <ResultsView
            results={quizResults}
            onBack={() => setView("path")}
          />
        )}

        {view === "path" && selectedPath && (
          <PathView
            path={selectedPath}
            onStartQuiz={(mi) => startQuiz(selectedPath.id, mi)}
            quizLoading={quizLoading}
          />
        )}
      </div>
    </div>
  );
}

// --- Sub-components ---

function HomeView({
  onStartAssist,
  problem,
  setProblem,
  assistLoading,
}: {
  onStartAssist: () => void;
  problem: string;
  setProblem: (v: string) => void;
  assistLoading: boolean;
}) {
  return (
    <div className="space-y-6">
      {/* Teach-then-troubleshoot input */}
      <div className="rounded-lg border bg-white p-6">
        <div className="mb-4 flex items-center gap-2">
          <Brain className="h-5 w-5 text-emerald-600" />
          <h3 className="font-semibold">Teach-Then-Troubleshoot</h3>
        </div>
        <p className="mb-4 text-sm text-slate-600">
          Describe your problem and ManualWorx will identify the system, offer
          to teach you how it works, then walk you through diagnostics.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            className="flex-1 rounded-md border px-3 py-2 text-sm"
            placeholder="e.g., The auxiliary hydraulics on my CAT 236B are running slow..."
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onStartAssist()}
          />
          <Button onClick={onStartAssist} disabled={assistLoading || !problem.trim()}>
            {assistLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-4 font-semibold">How it works</h3>
        <div className="space-y-4 text-sm text-slate-600">
          <div className="rounded-lg border-l-4 border-emerald-600 bg-emerald-50 p-4">
            <p className="font-medium text-emerald-800">1. Describe your problem</p>
            <p className="mt-1 text-emerald-700">
              &ldquo;The auxiliary hydraulics on my CAT 236B are running slow&rdquo;
            </p>
          </div>
          <div className="rounded-lg border-l-4 border-blue-600 bg-blue-50 p-4">
            <p className="font-medium text-blue-800">2. ManualWorx identifies the system</p>
            <p className="mt-1 text-blue-700">
              Finds the auxiliary hydraulic system in your manual library and offers to teach you how it works first.
            </p>
          </div>
          <div className="rounded-lg border-l-4 border-amber-500 bg-amber-50 p-4">
            <p className="font-medium text-amber-800">3. Choose your path</p>
            <ul className="mt-1 space-y-1 text-amber-700">
              <li><strong>Teach Me First</strong> — 5-min interactive lesson</li>
              <li><strong>Quick Overview</strong> — 60-second system brief</li>
              <li><strong>Skip to Fix</strong> — Jump straight to diagnostics</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function AssistView({
  session,
  onChoose,
  loading,
}: {
  session: AssistSession;
  onChoose: (choice: string) => void;
  loading: boolean;
}) {
  const icons: Record<string, typeof BookOpen> = {
    teach_first: BookOpen,
    quick_overview: Zap,
    skip_to_fix: ChevronRight,
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 font-semibold">
          System Identified: {session.system_area}
        </h3>
        <div className="mb-4 flex items-center gap-2">
          <Badge variant="secondary">
            {Math.round(session.system_confidence * 100)}% confidence
          </Badge>
          {session.related_systems.length > 0 && (
            <span className="text-xs text-muted-foreground">
              Related: {session.related_systems.join(", ")}
            </span>
          )}
        </div>

        <p className="mb-6 text-sm text-slate-600">
          Choose how you&apos;d like to approach this:
        </p>

        <div className="grid gap-3">
          {session.choices.map((c) => {
            const Icon = icons[c.id] || ChevronRight;
            return (
              <button
                key={c.id}
                disabled={loading}
                className="flex items-start gap-4 rounded-lg border p-4 text-left transition hover:bg-emerald-50 hover:border-emerald-300 disabled:opacity-50"
                onClick={() => onChoose(c.id)}
              >
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                <div>
                  <p className="font-medium">{c.label}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {c.description}
                  </p>
                  <Badge variant="outline" className="mt-1 text-[10px]">
                    {c.duration}
                  </Badge>
                </div>
              </button>
            );
          })}
        </div>

        {loading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Preparing lesson...
          </div>
        )}
      </div>
    </div>
  );
}

function LessonView({
  text,
  meta,
  loading,
  onContinue,
  onBack,
  showContinue,
}: {
  text: string;
  meta: { key_concepts: string[]; system_area: string } | null;
  loading: boolean;
  onContinue: () => void;
  onBack: () => void;
  showContinue: boolean;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {meta && (
        <div className="flex items-center gap-2">
          <GraduationCap className="h-5 w-5 text-emerald-600" />
          <h3 className="font-semibold">
            {meta.system_area} System
          </h3>
        </div>
      )}

      <div className="rounded-lg border bg-white p-6">
        <div className="prose prose-sm max-w-none whitespace-pre-wrap">
          {text}
        </div>
      </div>

      {meta && meta.key_concepts.length > 0 && (
        <div className="rounded-lg border bg-emerald-50 p-4">
          <p className="mb-2 text-xs font-medium text-emerald-800">
            Key Concepts
          </p>
          <div className="flex flex-wrap gap-1.5">
            {meta.key_concepts.map((c, i) => (
              <Badge key={i} variant="secondary" className="text-xs">
                {c}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        {showContinue && (
          <Button onClick={onContinue}>
            Continue to Troubleshooting
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

function QuizView({
  questions,
  answers,
  setAnswers,
  onSubmit,
  loading,
}: {
  questions: QuizQuestion[];
  answers: Record<string, string>;
  setAnswers: (a: Record<string, string>) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  const allAnswered = questions.every((q) => answers[q.id]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="h-5 w-5 text-blue-600" />
        <h3 className="font-semibold">Quiz</h3>
        <Badge variant="outline" className="ml-auto">
          {Object.keys(answers).length}/{questions.length} answered
        </Badge>
      </div>

      {questions.map((q, qi) => (
        <div key={q.id} className="rounded-lg border bg-white p-4">
          <div className="mb-1 flex items-start gap-2">
            <Badge variant="secondary" className="mt-0.5 text-[10px]">
              {q.question_type}
            </Badge>
            <p className="text-sm font-medium">
              {qi + 1}. {q.question_text}
            </p>
          </div>
          <div className="mt-3 space-y-2 pl-6">
            {Object.entries(q.options).map(([key, text]) => (
              <label
                key={key}
                className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${
                  answers[q.id] === key
                    ? "border-emerald-500 bg-emerald-50"
                    : "hover:bg-slate-50"
                }`}
              >
                <input
                  type="radio"
                  name={q.id}
                  value={key}
                  checked={answers[q.id] === key}
                  onChange={() =>
                    setAnswers({ ...answers, [q.id]: key })
                  }
                  className="accent-emerald-600"
                />
                <span className="font-mono text-xs text-muted-foreground">
                  {key}.
                </span>
                {text}
              </label>
            ))}
          </div>
        </div>
      ))}

      <Button
        onClick={onSubmit}
        disabled={!allAnswered || loading}
        className="w-full"
      >
        {loading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Trophy className="mr-2 h-4 w-4" />
        )}
        Submit Quiz
      </Button>
    </div>
  );
}

function ResultsView({
  results,
  onBack,
}: {
  results: { score: number; passed: boolean; results: QuizResult[] };
  onBack: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-white p-6 text-center">
        {results.passed ? (
          <Trophy className="mx-auto mb-2 h-12 w-12 text-amber-500" />
        ) : (
          <Brain className="mx-auto mb-2 h-12 w-12 text-blue-500" />
        )}
        <h3 className="text-2xl font-bold">
          {results.score}%
        </h3>
        <p className="text-sm text-muted-foreground">
          {results.passed
            ? "Great job! You passed the quiz."
            : "Keep studying. You need 70% to pass."}
        </p>
      </div>

      {results.results.map((r, i) => (
        <div
          key={i}
          className={`rounded-lg border p-4 ${
            r.is_correct ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
          }`}
        >
          <div className="flex items-start gap-2">
            {r.is_correct ? (
              <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
            )}
            <div>
              <p className="text-sm font-medium">{r.question_text}</p>
              {!r.is_correct && (
                <p className="mt-1 text-xs">
                  Your answer: <strong>{r.user_answer}</strong> · Correct:{" "}
                  <strong>{r.correct_answer}</strong>
                </p>
              )}
              {r.explanation && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {r.explanation}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}

      <Button variant="outline" onClick={onBack}>
        Back to Learning Path
      </Button>
    </div>
  );
}

function PathView({
  path,
  onStartQuiz,
  quizLoading,
}: {
  path: LearningPath;
  onStartQuiz: (moduleIndex: number) => void;
  quizLoading: boolean;
}) {
  const modules = path.modules || [];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold">{path.title}</h3>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant="secondary">{path.system_area}</Badge>
          {path.auto_generated && (
            <Badge variant="outline" className="text-[10px]">
              Auto-generated
            </Badge>
          )}
        </div>
      </div>

      {modules.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          No modules in this learning path.
        </div>
      ) : (
        modules.map((mod, mi) => (
          <div key={mi} className="rounded-lg border bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">
                  Module {mi + 1}: {mod.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {mod.lessons?.length || 0} lessons ·{" "}
                  {mod.quiz_question_count || 5} quiz questions
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={quizLoading}
                onClick={() => onStartQuiz(mi)}
              >
                {quizLoading ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Brain className="mr-1 h-3.5 w-3.5" />
                )}
                Take Quiz
              </Button>
            </div>

            {mod.lessons && mod.lessons.length > 0 && (
              <div className="mt-3 space-y-1 border-t pt-3">
                {mod.lessons.map((lesson, li) => (
                  <div
                    key={li}
                    className="flex items-center gap-2 text-xs text-slate-600"
                  >
                    <BookOpen className="h-3 w-3 text-slate-400" />
                    <span>{lesson.title}</span>
                    {lesson.description && (
                      <span className="text-muted-foreground">
                        — {lesson.description}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
