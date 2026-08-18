from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client
from supabase.client import ClientOptions

ACTIVITY_CODE = "AULA01-SISTNUM"


@st.cache_resource
def get_supabase() -> Client:
    """Cria um único cliente Supabase por processo, com timeout de rede.

    Sem timeout explícito, uma conexão problemática pode manter uma chamada
    bloqueada por tempo suficiente para o Streamlit parecer travado.
    """
    url = str(st.secrets["SUPABASE_URL"]).strip()
    key = str(st.secrets["SUPABASE_SECRET_KEY"]).strip()

    if not url or not key:
        raise RuntimeError("SUPABASE_URL ou SUPABASE_SECRET_KEY não configurada.")

    return create_client(
        url,
        key,
        options=ClientOptions(
            postgrest_client_timeout=10,
            storage_client_timeout=10,
            schema="public",
        ),
    )


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_ra(ra: str) -> str:
    return "".join(ch for ch in str(ra).strip() if ch.isalnum()).upper()


def get_activity():
    sb = get_supabase()
    res = (
        sb.table("activities")
        .select("code,title,active")
        .eq("code", ACTIVITY_CODE)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_questions(include_answers: bool = False):
    sb = get_supabase()
    fields = "id,position,level,prompt,options"
    if include_answers:
        fields += ",correct_answer,explanation"

    res = (
        sb.table("questions")
        .select(fields)
        .eq("activity_code", ACTIVITY_CODE)
        .eq("active", True)
        .order("position")
        .execute()
    )
    return res.data or []


def get_question_answer(question_id: str):
    sb = get_supabase()
    res = (
        sb.table("questions")
        .select("id,correct_answer,explanation")
        .eq("id", question_id)
        .eq("activity_code", ACTIVITY_CODE)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_or_create_student(name: str, ra: str):
    sb = get_supabase()
    ra = normalize_ra(ra)
    name = name.strip()

    found = (
        sb.table("students")
        .select("id,name,ra")
        .eq("ra", ra)
        .limit(1)
        .execute()
    )

    if found.data:
        student = found.data[0]
        if student["name"] != name:
            updated = (
                sb.table("students")
                .update({"name": name, "updated_at": now_iso()})
                .eq("id", student["id"])
                .select("id,name,ra")
                .execute()
            )
            return updated.data[0] if updated.data else student
        return student

    created = (
        sb.table("students")
        .insert({"name": name, "ra": ra, "updated_at": now_iso()})
        .select("id,name,ra")
        .execute()
    )
    if created.data:
        return created.data[0]

    retry = (
        sb.table("students")
        .select("id,name,ra")
        .eq("ra", ra)
        .limit(1)
        .execute()
    )
    if retry.data:
        return retry.data[0]

    raise RuntimeError("Não foi possível criar ou localizar o estudante.")


def get_or_create_attempt(student_id: str):
    sb = get_supabase()

    found = (
        sb.table("attempts")
        .select("id,student_id,activity_code,started_at,updated_at,submitted_at")
        .eq("student_id", student_id)
        .eq("activity_code", ACTIVITY_CODE)
        .limit(1)
        .execute()
    )
    if found.data:
        return found.data[0]

    created = (
        sb.table("attempts")
        .insert({
            "student_id": student_id,
            "activity_code": ACTIVITY_CODE,
            "updated_at": now_iso(),
        })
        .select("id,student_id,activity_code,started_at,updated_at,submitted_at")
        .execute()
    )
    if created.data:
        return created.data[0]

    retry = (
        sb.table("attempts")
        .select("id,student_id,activity_code,started_at,updated_at,submitted_at")
        .eq("student_id", student_id)
        .eq("activity_code", ACTIVITY_CODE)
        .limit(1)
        .execute()
    )
    if retry.data:
        return retry.data[0]

    raise RuntimeError("Não foi possível criar ou localizar a tentativa.")


def get_attempt(attempt_id: str):
    sb = get_supabase()
    res = (
        sb.table("attempts")
        .select("id,student_id,activity_code,started_at,updated_at,submitted_at")
        .eq("id", attempt_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_responses(attempt_id: str):
    sb = get_supabase()
    res = (
        sb.table("responses")
        .select("question_id,answer,is_correct,answered_at")
        .eq("attempt_id", attempt_id)
        .execute()
    )
    return {row["question_id"]: row for row in (res.data or [])}


def save_first_response(attempt_id: str, question_id: str, answer: str):
    """
    Registra apenas a PRIMEIRA resposta.
    Se a questão já foi respondida, devolve o registro existente sem alterá-lo.
    """
    sb = get_supabase()

    existing = (
        sb.table("responses")
        .select("question_id,answer,is_correct,answered_at")
        .eq("attempt_id", attempt_id)
        .eq("question_id", question_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        return {
            "saved": False,
            "answer": row["answer"],
            "is_correct": bool(row["is_correct"]),
            "answered_at": row["answered_at"],
        }

    question = get_question_answer(question_id)
    if not question:
        raise ValueError(f"Questão {question_id} não encontrada.")

    is_correct = answer == question["correct_answer"]
    ts = now_iso()

    # A PK composta (attempt_id, question_id) também protege contra duplicidade.
    try:
        created = (
            sb.table("responses")
            .insert({
                "attempt_id": attempt_id,
                "question_id": question_id,
                "answer": answer,
                "is_correct": is_correct,
                "answered_at": ts,
            })
            .select("question_id,answer,is_correct,answered_at")
            .execute()
        )
        if created.data:
            row = created.data[0]
        else:
            row = {
                "answer": answer,
                "is_correct": is_correct,
                "answered_at": ts,
            }
    except Exception:
        # Se duas requisições ocorrerem quase simultaneamente, recupera a primeira.
        retry = (
            sb.table("responses")
            .select("question_id,answer,is_correct,answered_at")
            .eq("attempt_id", attempt_id)
            .eq("question_id", question_id)
            .limit(1)
            .execute()
        )
        if not retry.data:
            raise
        row = retry.data[0]

    sb.table("attempts").update(
        {"updated_at": ts}
    ).eq("id", attempt_id).execute()

    return {
        "saved": True,
        "answer": row["answer"],
        "is_correct": bool(row["is_correct"]),
        "answered_at": row["answered_at"],
    }


def finalize_attempt(attempt_id: str):
    sb = get_supabase()
    ts = now_iso()

    # Só finaliza se todas as questões ativas tiverem resposta.
    questions = get_questions(include_answers=False)
    responses = get_responses(attempt_id)
    if len(responses) < len(questions):
        raise ValueError("Ainda existem questões obrigatórias sem resposta.")

    res = (
        sb.table("attempts")
        .update({"submitted_at": ts, "updated_at": ts})
        .eq("id", attempt_id)
        .select("id,submitted_at")
        .execute()
    )
    return res.data[0] if res.data else None


def get_challenge_submission(attempt_id: str):
    sb = get_supabase()
    res = (
        sb.table("challenge_submissions")
        .select(
            "attempt_id,strategy,code_text,test_number,binary_result,"
            "hex_result,submitted_at"
        )
        .eq("attempt_id", attempt_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def submit_optional_challenge(
    attempt_id: str,
    strategy: str,
    code_text: str,
    test_number: str,
    binary_result: str,
    hex_result: str,
):
    """
    Desafio opcional: uma única submissão por tentativa.
    Não é utilizado no cálculo do progresso das 25 questões.
    """
    sb = get_supabase()

    existing = get_challenge_submission(attempt_id)
    if existing:
        return {"saved": False, **existing}

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("submitted_at"):
        raise ValueError(
            "Finalize primeiro as 25 questões obrigatórias antes de enviar o desafio."
        )

    ts = now_iso()
    payload = {
        "attempt_id": attempt_id,
        "strategy": strategy.strip(),
        "code_text": code_text.strip(),
        "test_number": str(test_number).strip(),
        "binary_result": binary_result.strip(),
        "hex_result": hex_result.strip().upper(),
        "submitted_at": ts,
    }

    try:
        created = (
            sb.table("challenge_submissions")
            .insert(payload)
            .select(
                "attempt_id,strategy,code_text,test_number,binary_result,"
                "hex_result,submitted_at"
            )
            .execute()
        )
        if created.data:
            return {"saved": True, **created.data[0]}
    except Exception:
        retry = get_challenge_submission(attempt_id)
        if retry:
            return {"saved": False, **retry}
        raise

    return {"saved": True, **payload}



def get_challenge_ai_feedback(attempt_id: str):
    sb = get_supabase()
    res = (
        sb.table("challenge_ai_feedback")
        .select(
            "attempt_id,model,openai_response_id,"
            "binary_logic_score,hexadecimal_logic_score,algorithm_score,"
            "test_score,clarity_score,total_score,"
            "strengths,areas_to_review,guiding_questions,"
            "next_step,formative_summary,created_at"
        )
        .eq("attempt_id", attempt_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def save_challenge_ai_feedback(
    attempt_id: str,
    feedback,
    model: str,
    openai_response_id: str | None = None,
):
    """
    Salva apenas um feedback por submissão.
    Se já existir, retorna o registro existente e não cria uma nova avaliação.
    """
    sb = get_supabase()

    existing = get_challenge_ai_feedback(attempt_id)
    if existing:
        return {"saved": False, **existing}

    total = round(
        float(feedback.binary_logic_score)
        + float(feedback.hexadecimal_logic_score)
        + float(feedback.algorithm_score)
        + float(feedback.test_score)
        + float(feedback.clarity_score),
        1,
    )

    payload = {
        "attempt_id": attempt_id,
        "model": model,
        "openai_response_id": openai_response_id,
        "binary_logic_score": float(feedback.binary_logic_score),
        "hexadecimal_logic_score": float(feedback.hexadecimal_logic_score),
        "algorithm_score": float(feedback.algorithm_score),
        "test_score": float(feedback.test_score),
        "clarity_score": float(feedback.clarity_score),
        "total_score": total,
        "strengths": feedback.strengths,
        "areas_to_review": feedback.areas_to_review,
        "guiding_questions": feedback.guiding_questions,
        "next_step": feedback.next_step,
        "formative_summary": feedback.formative_summary,
    }

    try:
        created = (
            sb.table("challenge_ai_feedback")
            .insert(payload)
            .select(
                "attempt_id,model,openai_response_id,"
                "binary_logic_score,hexadecimal_logic_score,algorithm_score,"
                "test_score,clarity_score,total_score,"
                "strengths,areas_to_review,guiding_questions,"
                "next_step,formative_summary,created_at"
            )
            .execute()
        )
        if created.data:
            return {"saved": True, **created.data[0]}
    except Exception:
        retry = get_challenge_ai_feedback(attempt_id)
        if retry:
            return {"saved": False, **retry}
        raise

    return {"saved": True, **payload}


def teacher_dataset():
    """Retorna dados brutos para o painel do professor."""
    sb = get_supabase()

    attempts = (
        sb.table("attempts")
        .select("id,student_id,activity_code,started_at,updated_at,submitted_at")
        .eq("activity_code", ACTIVITY_CODE)
        .order("updated_at", desc=True)
        .execute()
    ).data or []

    students = (
        sb.table("students")
        .select("id,name,ra,created_at,updated_at")
        .execute()
    ).data or []

    responses = (
        sb.table("responses")
        .select("attempt_id,question_id,answer,is_correct,answered_at")
        .execute()
    ).data or []

    questions = get_questions(include_answers=True)

    challenges = (
        sb.table("challenge_submissions")
        .select(
            "attempt_id,strategy,code_text,test_number,binary_result,"
            "hex_result,submitted_at"
        )
        .execute()
    ).data or []

    ai_feedbacks = (
        sb.table("challenge_ai_feedback")
        .select(
            "attempt_id,model,openai_response_id,"
            "binary_logic_score,hexadecimal_logic_score,algorithm_score,"
            "test_score,clarity_score,total_score,"
            "strengths,areas_to_review,guiding_questions,"
            "next_step,formative_summary,created_at"
        )
        .execute()
    ).data or []

    attempt_ids = {a["id"] for a in attempts}
    responses = [r for r in responses if r["attempt_id"] in attempt_ids]
    challenges = [c for c in challenges if c["attempt_id"] in attempt_ids]
    ai_feedbacks = [f for f in ai_feedbacks if f["attempt_id"] in attempt_ids]

    student_ids = {a["student_id"] for a in attempts}
    students = [s for s in students if s["id"] in student_ids]

    return students, attempts, responses, questions, challenges, ai_feedbacks
