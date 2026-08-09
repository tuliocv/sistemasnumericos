from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client

ACTIVITY_CODE = "AULA01-SISTNUM"


@st.cache_resource
def get_supabase() -> Client:
    """Cria um único cliente Supabase por processo do Streamlit."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SECRET_KEY"]
    return create_client(url, key)


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
    if not created.data:
        # Proteção simples para eventual corrida de duas inserções simultâneas.
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
    return created.data[0]


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
    return {
        row["question_id"]: row
        for row in (res.data or [])
    }


def save_response(attempt_id: str, question_id: str, answer: str):
    sb = get_supabase()
    question = get_question_answer(question_id)
    if not question:
        raise ValueError(f"Questão {question_id} não encontrada.")

    is_correct = answer == question["correct_answer"]
    ts = now_iso()

    sb.table("responses").upsert(
        {
            "attempt_id": attempt_id,
            "question_id": question_id,
            "answer": answer,
            "is_correct": is_correct,
            "answered_at": ts,
        },
        on_conflict="attempt_id,question_id",
    ).execute()

    sb.table("attempts").update(
        {"updated_at": ts}
    ).eq("id", attempt_id).execute()

    return is_correct


def finalize_attempt(attempt_id: str):
    sb = get_supabase()
    ts = now_iso()
    res = (
        sb.table("attempts")
        .update({"submitted_at": ts, "updated_at": ts})
        .eq("id", attempt_id)
        .select("id,submitted_at")
        .execute()
    )
    return res.data[0] if res.data else None


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

    attempt_ids = {a["id"] for a in attempts}
    responses = [r for r in responses if r["attempt_id"] in attempt_ids]

    student_ids = {a["student_id"] for a in attempts}
    students = [s for s in students if s["id"] in student_ids]

    return students, attempts, responses, questions
