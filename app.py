from pathlib import Path
import textwrap, json

base = Path("/mnt/data/streamlit_sistemas_numericos")
base.mkdir(parents=True, exist_ok=True)
(base / ".streamlit").mkdir(exist_ok=True)

app_code = r'''# -*- coding: utf-8 -*-
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================
st.set_page_config(
    page_title="Sistemas Numéricos | Estruturas de Dados",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Sistemas Numéricos"
APP_SUBTITLE = "Decimal • Binário • Hexadecimal"
COURSE = "Estruturas de Dados e Análise de Algoritmos"
TOTAL_QUESTIONS = 25
TIMEZONE = ZoneInfo("America/Sao_Paulo")

DATA_DIR = os.getenv("QUIZ_DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "respostas_aula01.db")

LEVELS = ["Conceitual", "Fácil", "Médio", "Difícil", "Desafiador"]

LEVEL_DESCRIPTIONS = {
    "Conceitual": "Compreensão das bases, símbolos e valor posicional.",
    "Fácil": "Conversões diretas com números pequenos.",
    "Médio": "Conversões que exigem mais de uma etapa de raciocínio.",
    "Difícil": "Números maiores e conversões entre diferentes bases.",
    "Desafiador": "Integração entre decimal, binário e hexadecimal.",
}


# ============================================================
# BANCO DE QUESTÕES
# 5 questões por nível = 25 questões
# ============================================================
QUESTIONS = [
    {
        "id": "Q01",
        "level": "Conceitual",
        "prompt": "Quais símbolos podem aparecer em um número binário?",
        "options": ["0 e 1", "0 a 7", "0 a 9", "0 a 9 e A a F"],
        "answer": "0 e 1",
        "explanation": "O sistema binário é de base 2 e utiliza apenas os símbolos 0 e 1.",
    },
    {
        "id": "Q02",
        "level": "Conceitual",
        "prompt": "No sistema hexadecimal, qual é o valor decimal do símbolo F?",
        "options": ["10", "14", "15", "16"],
        "answer": "15",
        "explanation": "No hexadecimal, A=10, B=11, C=12, D=13, E=14 e F=15.",
    },
    {
        "id": "Q03",
        "level": "Conceitual",
        "prompt": "No número decimal 410, por que o algarismo 4 representa 400?",
        "options": [
            "Porque 4 sempre vale 400",
            "Porque está na posição correspondente a 10²",
            "Porque 410 é um número binário",
            "Porque a base decimal é 4",
        ],
        "answer": "Porque está na posição correspondente a 10²",
        "explanation": "Na notação posicional decimal: 410 = 4×10² + 1×10¹ + 0×10⁰.",
    },
    {
        "id": "Q04",
        "level": "Conceitual",
        "prompt": "Quantos bits correspondem exatamente a um dígito hexadecimal?",
        "options": ["2", "3", "4", "8"],
        "answer": "4",
        "explanation": "Como 16 = 2⁴, cada dígito hexadecimal representa exatamente 4 bits.",
    },
    {
        "id": "Q05",
        "level": "Conceitual",
        "prompt": "Qual é o valor decimal de 10₂?",
        "options": ["1", "2", "10", "16"],
        "answer": "2",
        "explanation": "10₂ = 1×2¹ + 0×2⁰ = 2₁₀.",
    },
    {
        "id": "Q06",
        "level": "Fácil",
        "prompt": "Converta 101₂ para decimal.",
        "options": ["3", "4", "5", "6"],
        "answer": "5",
        "explanation": "101₂ = 1×2² + 0×2¹ + 1×2⁰ = 4 + 0 + 1 = 5.",
    },
    {
        "id": "Q07",
        "level": "Fácil",
        "prompt": "Converta 1101₂ para decimal.",
        "options": ["11", "12", "13", "14"],
        "answer": "13",
        "explanation": "1101₂ = 8 + 4 + 0 + 1 = 13₁₀.",
    },
    {
        "id": "Q08",
        "level": "Fácil",
        "prompt": "Converta 10₁₀ para binário.",
        "options": ["1000₂", "1010₂", "1100₂", "1110₂"],
        "answer": "1010₂",
        "explanation": "10 = 8 + 2 = 2³ + 2¹, portanto 10₁₀ = 1010₂.",
    },
    {
        "id": "Q09",
        "level": "Fácil",
        "prompt": "Converta 15₁₀ para hexadecimal.",
        "options": ["E₁₆", "F₁₆", "10₁₆", "15₁₆"],
        "answer": "F₁₆",
        "explanation": "O valor decimal 15 é representado pelo símbolo F no hexadecimal.",
    },
    {
        "id": "Q10",
        "level": "Fácil",
        "prompt": "Qual é o valor decimal de A₁₆?",
        "options": ["8", "9", "10", "11"],
        "answer": "10",
        "explanation": "No hexadecimal, A representa o valor decimal 10.",
    },
    {
        "id": "Q11",
        "level": "Médio",
        "prompt": "Converta 25₁₀ para binário.",
        "options": ["11001₂", "10101₂", "11100₂", "10011₂"],
        "answer": "11001₂",
        "explanation": "25 = 16 + 8 + 1, portanto 25₁₀ = 11001₂.",
    },
    {
        "id": "Q12",
        "level": "Médio",
        "prompt": "Converta 42₁₀ para binário.",
        "options": ["101010₂", "101100₂", "110010₂", "100101₂"],
        "answer": "101010₂",
        "explanation": "42 = 32 + 8 + 2, portanto 42₁₀ = 101010₂.",
    },
    {
        "id": "Q13",
        "level": "Médio",
        "prompt": "Converta 11111111₂ para hexadecimal.",
        "options": ["EF₁₆", "F0₁₆", "FF₁₆", "1FF₁₆"],
        "answer": "FF₁₆",
        "explanation": "Agrupando em blocos de 4 bits: 1111 1111 → F F.",
    },
    {
        "id": "Q14",
        "level": "Médio",
        "prompt": "Converta 2D₁₆ para decimal.",
        "options": ["35", "43", "45", "46"],
        "answer": "45",
        "explanation": "2D₁₆ = 2×16¹ + 13×16⁰ = 32 + 13 = 45.",
    },
    {
        "id": "Q15",
        "level": "Médio",
        "prompt": "Qual é a representação binária de 3A₁₆ em grupos de 4 bits?",
        "options": ["0011 1010", "0011 1100", "1010 0011", "1110 0011"],
        "answer": "0011 1010",
        "explanation": "3₁₆ = 0011₂ e A₁₆ = 1010₂. Logo, 3A₁₆ = 0011 1010₂.",
    },
    {
        "id": "Q16",
        "level": "Difícil",
        "prompt": "Converta 100101₂ para decimal.",
        "options": ["35", "36", "37", "41"],
        "answer": "37",
        "explanation": "100101₂ = 32 + 4 + 1 = 37₁₀.",
    },
    {
        "id": "Q17",
        "level": "Difícil",
        "prompt": "Converta 173₁₀ para hexadecimal.",
        "options": ["A9₁₆", "AB₁₆", "AD₁₆", "B1₁₆"],
        "answer": "AD₁₆",
        "explanation": "173 ÷ 16 = 10 com resto 13. Em hexadecimal, 10=A e 13=D: AD₁₆.",
    },
    {
        "id": "Q18",
        "level": "Difícil",
        "prompt": "Converta 7B₁₆ para decimal.",
        "options": ["119", "121", "123", "125"],
        "answer": "123",
        "explanation": "7B₁₆ = 7×16 + 11 = 112 + 11 = 123.",
    },
    {
        "id": "Q19",
        "level": "Difícil",
        "prompt": "Converta 10110110₂ para hexadecimal.",
        "options": ["A6₁₆", "B6₁₆", "B5₁₆", "C6₁₆"],
        "answer": "B6₁₆",
        "explanation": "1011 0110 → B 6. Portanto, 10110110₂ = B6₁₆.",
    },
    {
        "id": "Q20",
        "level": "Difícil",
        "prompt": "Qual é a representação binária de C7₁₆?",
        "options": ["1100 0111", "1101 0111", "1011 0111", "1100 1110"],
        "answer": "1100 0111",
        "explanation": "C₁₆ = 1100₂ e 7₁₆ = 0111₂. Logo, C7₁₆ = 1100 0111₂.",
    },
    {
        "id": "Q21",
        "level": "Desafiador",
        "prompt": "Qual é a representação hexadecimal de 64206₁₀?",
        "options": ["FACE₁₆", "FACA₁₆", "FADE₁₆", "FCAE₁₆"],
        "answer": "FACE₁₆",
        "explanation": "FACE₁₆ = 15×16³ + 10×16² + 12×16 + 14 = 64206.",
    },
    {
        "id": "Q22",
        "level": "Desafiador",
        "prompt": "Converta 111010101011₂ para hexadecimal.",
        "options": ["DAB₁₆", "EAB₁₆", "EAC₁₆", "FAB₁₆"],
        "answer": "EAB₁₆",
        "explanation": "Agrupando: 1110 1010 1011 → E A B.",
    },
    {
        "id": "Q23",
        "level": "Desafiador",
        "prompt": "Converta 2026₁₀ para hexadecimal.",
        "options": ["7DA₁₆", "7EA₁₆", "8EA₁₆", "7FA₁₆"],
        "answer": "7EA₁₆",
        "explanation": "2026 = 7×16² + 14×16 + 10 = 1792 + 224 + 10. Logo, 7EA₁₆.",
    },
    {
        "id": "Q24",
        "level": "Desafiador",
        "prompt": "Qual das equivalências abaixo está INCORRETA?",
        "options": [
            "255₁₀ = 11111111₂ = FF₁₆",
            "64₁₀ = 1000000₂ = 40₁₆",
            "31₁₀ = 11111₂ = 1F₁₆",
            "26₁₀ = 11010₂ = 1B₁₆",
        ],
        "answer": "26₁₀ = 11010₂ = 1B₁₆",
        "explanation": "26₁₀ = 11010₂, mas em hexadecimal é 1A₁₆, e não 1B₁₆.",
    },
    {
        "id": "Q25",
        "level": "Desafiador",
        "prompt": "O valor decimal 2748 deve ser representado em binário e hexadecimal. Qual par está correto?",
        "options": [
            "1010 1011 1100₂ e ABC₁₆",
            "1010 1011 1101₂ e ABD₁₆",
            "1011 1010 1100₂ e BAC₁₆",
            "1010 1100 1011₂ e ACB₁₆",
        ],
        "answer": "1010 1011 1100₂ e ABC₁₆",
        "explanation": "ABC₁₆ = 10×16² + 11×16 + 12 = 2748, e A B C → 1010 1011 1100₂.",
    },
]

QUESTION_BY_ID = {q["id"]: q for q in QUESTIONS}


# ============================================================
# ESTILO / UX
# ============================================================
st.markdown(
    """
    <style>
        .block-container {
            max-width: 1050px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3 {
            letter-spacing: -0.02em;
        }

        .hero {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 20px;
            padding: 24px 28px;
            margin-bottom: 18px;
            background: linear-gradient(135deg, rgba(74,65,190,.10), rgba(255,255,255,0));
        }

        .hero-kicker {
            font-size: .82rem;
            font-weight: 700;
            letter-spacing: .08em;
            text-transform: uppercase;
            opacity: .72;
            margin-bottom: 6px;
        }

        .hero-title {
            font-size: clamp(1.8rem, 4vw, 3rem);
            font-weight: 800;
            line-height: 1.08;
            margin: 0;
        }

        .hero-subtitle {
            margin-top: 8px;
            font-size: 1.05rem;
            opacity: .80;
        }

        .level-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: .78rem;
            font-weight: 700;
            border: 1px solid rgba(128,128,128,.30);
            margin-bottom: 8px;
        }

        .question-number {
            opacity: .65;
            font-size: .85rem;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .question-text {
            font-size: 1.08rem;
            font-weight: 650;
            margin-bottom: 10px;
        }

        .muted {
            opacity: .68;
        }

        div[data-testid="stRadio"] label {
            padding-top: 4px;
            padding-bottom: 4px;
        }

        div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
            min-height: 44px;
            border-radius: 10px;
            font-weight: 700;
        }

        [data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.20);
            border-radius: 14px;
            padding: 12px;
        }

        @media (max-width: 700px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .hero {
                padding: 20px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# UTILITÁRIOS
# ============================================================
def now_str():
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def normalize_ra(ra: str) -> str:
    return "".join(ch for ch in str(ra).strip() if ch.isalnum()).upper()


def student_key_from_ra(ra: str) -> str:
    return hashlib.sha256(normalize_ra(ra).encode("utf-8")).hexdigest()


def get_teacher_password():
    try:
        if "TEACHER_PASSWORD" in st.secrets:
            return str(st.secrets["TEACHER_PASSWORD"])
    except Exception:
        pass
    return os.getenv("TEACHER_PASSWORD", "")


def hero():
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-kicker">{COURSE}</div>
            <div class="hero-title">{APP_TITLE}</div>
            <div class="hero-subtitle">{APP_SUBTITLE} • 25 questões de múltipla escolha</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def clear_student_session():
    keys = list(st.session_state.keys())
    for key in keys:
        if (
            key.startswith("q_")
            or key in {
                "student_key",
                "student_name",
                "student_ra",
                "section_index",
                "flash",
            }
        ):
            del st.session_state[key]


# ============================================================
# BANCO DE DADOS SQLITE
# ============================================================
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def init_db():
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ra TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                submitted_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                student_key TEXT NOT NULL,
                qid TEXT NOT NULL,
                answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL,
                PRIMARY KEY (student_key, qid),
                FOREIGN KEY (student_key) REFERENCES students(student_key)
            )
            """
        )
        conn.commit()


def upsert_student(name: str, ra: str) -> str:
    key = student_key_from_ra(ra)
    ts = now_str()
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO students (student_key, name, ra, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_key) DO UPDATE SET
                name = excluded.name,
                ra = excluded.ra,
                updated_at = excluded.updated_at
            """,
            (key, name.strip(), normalize_ra(ra), ts, ts),
        )
        conn.commit()
    return key


def save_response(student_key: str, qid: str, answer: str):
    q = QUESTION_BY_ID[qid]
    is_correct = int(answer == q["answer"])
    ts = now_str()
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO responses (student_key, qid, answer, is_correct, answered_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_key, qid) DO UPDATE SET
                answer = excluded.answer,
                is_correct = excluded.is_correct,
                answered_at = excluded.answered_at
            """,
            (student_key, qid, answer, is_correct, ts),
        )
        conn.execute(
            "UPDATE students SET updated_at = ? WHERE student_key = ?",
            (ts, student_key),
        )
        conn.commit()


def get_student_record(student_key: str):
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT student_key, name, ra, started_at, updated_at, submitted_at
            FROM students
            WHERE student_key = ?
            """,
            (student_key,),
        ).fetchone()
    return row


def get_student_answers(student_key: str):
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT qid, answer, is_correct, answered_at
            FROM responses
            WHERE student_key = ?
            """,
            (student_key,),
        ).fetchall()
    return {
        qid: {
            "answer": answer,
            "is_correct": bool(is_correct),
            "answered_at": answered_at,
        }
        for qid, answer, is_correct, answered_at in rows
    }


def finalize_student(student_key: str):
    ts = now_str()
    with db_connect() as conn:
        conn.execute(
            """
            UPDATE students
            SET submitted_at = ?, updated_at = ?
            WHERE student_key = ?
            """,
            (ts, ts, student_key),
        )
        conn.commit()


def load_teacher_data():
    with db_connect() as conn:
        students = pd.read_sql_query(
            """
            SELECT
                s.student_key,
                s.name,
                s.ra,
                s.started_at,
                s.updated_at,
                s.submitted_at,
                COUNT(r.qid) AS answered,
                COALESCE(SUM(r.is_correct), 0) AS correct
            FROM students s
            LEFT JOIN responses r ON r.student_key = s.student_key
            GROUP BY
                s.student_key, s.name, s.ra,
                s.started_at, s.updated_at, s.submitted_at
            ORDER BY s.updated_at DESC
            """,
            conn,
        )

        responses = pd.read_sql_query(
            """
            SELECT
                r.student_key,
                s.name,
                s.ra,
                r.qid,
                r.answer,
                r.is_correct,
                r.answered_at,
                s.submitted_at
            FROM responses r
            JOIN students s ON s.student_key = r.student_key
            ORDER BY r.answered_at DESC
            """,
            conn,
        )

    return students, responses


# ============================================================
# ALUNO
# ============================================================
def student_login():
    hero()
    st.subheader("Entrar na atividade")
    st.caption(
        "Informe seus dados para iniciar. Se você já começou, use o mesmo RA para continuar de onde parou."
    )

    with st.form("student_login_form", clear_on_submit=False):
        name = st.text_input(
            "Nome completo",
            placeholder="Ex.: Ana Silva",
            max_chars=120,
        )
        ra = st.text_input(
            "RA",
            placeholder="Digite seu RA",
            max_chars=30,
        )
        entered = st.form_submit_button(
            "Iniciar / continuar atividade",
            type="primary",
            use_container_width=True,
        )

    if entered:
        if len(name.strip()) < 3:
            st.error("Informe seu nome completo.")
            return
        if len(normalize_ra(ra)) < 3:
            st.error("Informe um RA válido.")
            return

        clear_student_session()
        key = upsert_student(name, ra)
        st.session_state["student_key"] = key
        st.session_state["student_name"] = name.strip()
        st.session_state["student_ra"] = normalize_ra(ra)

        answers = get_student_answers(key)
        first_incomplete = 0
        for i, level in enumerate(LEVELS):
            level_qids = [q["id"] for q in QUESTIONS if q["level"] == level]
            if not all(qid in answers for qid in level_qids):
                first_incomplete = i
                break
        else:
            first_incomplete = len(LEVELS)

        st.session_state["section_index"] = first_incomplete
        st.rerun()


def sidebar_student_progress(answers):
    st.sidebar.markdown("### Seu progresso")
    for i, level in enumerate(LEVELS):
        qids = [q["id"] for q in QUESTIONS if q["level"] == level]
        count = sum(qid in answers for qid in qids)
        marker = "✅" if count == len(qids) else "○"
        st.sidebar.write(f"{marker} **{level}** — {count}/{len(qids)}")

    st.sidebar.divider()
    if st.sidebar.button("Sair da atividade", use_container_width=True):
        clear_student_session()
        st.rerun()


def render_question(q, position, saved_answers):
    saved = saved_answers.get(q["id"], {}).get("answer")
    default_index = q["options"].index(saved) if saved in q["options"] else None

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="question-number">QUESTÃO {position:02d} • {q["id"]}</div>
            <div class="question-text">{q["prompt"]}</div>
            """,
            unsafe_allow_html=True,
        )
        selected = st.radio(
            "Selecione uma alternativa",
            q["options"],
            index=default_index,
            key=f"q_{q['id']}",
            label_visibility="collapsed",
        )
    return selected


def results_student(student_key, answers):
    hero()
    student = get_student_record(student_key)
    correct = sum(int(v["is_correct"]) for v in answers.values())
    pct = 100 * correct / TOTAL_QUESTIONS

    st.success("Atividade finalizada e respostas registradas.")
    col1, col2, col3 = st.columns(3)
    col1.metric("Acertos", f"{correct}/{TOTAL_QUESTIONS}")
    col2.metric("Aproveitamento", f"{pct:.0f}%")
    col3.metric("Respondidas", f"{len(answers)}/{TOTAL_QUESTIONS}")

    st.subheader("Desempenho por nível")
    level_rows = []
    for level in LEVELS:
        qs = [q for q in QUESTIONS if q["level"] == level]
        level_correct = sum(
            int(answers.get(q["id"], {}).get("is_correct", False)) for q in qs
        )
        level_rows.append(
            {
                "Nível": level,
                "Acertos": level_correct,
                "Questões": len(qs),
                "Aproveitamento": f"{100 * level_correct / len(qs):.0f}%",
            }
        )
    st.dataframe(
        pd.DataFrame(level_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Revisão das questões")
    st.caption("Abra cada item para comparar sua resposta com a resolução.")

    for idx, q in enumerate(QUESTIONS, start=1):
        response = answers.get(q["id"])
        is_correct = response and response["is_correct"]
        icon = "✅" if is_correct else "❌"
        with st.expander(f"{icon} Questão {idx:02d} — {q['level']}"):
            st.write(q["prompt"])
            st.write(f"**Sua resposta:** {response['answer'] if response else 'Não respondida'}")
            st.write(f"**Resposta correta:** {q['answer']}")
            st.info(q["explanation"])

    st.divider()
    st.caption(
        f"RA: {student[2]} • Finalização: {student[5] or '—'}"
    )


def student_app():
    if "student_key" not in st.session_state:
        student_login()
        return

    student_key = st.session_state["student_key"]
    student = get_student_record(student_key)

    if not student:
        clear_student_session()
        st.rerun()

    answers = get_student_answers(student_key)
    sidebar_student_progress(answers)

    if student[5]:
        results_student(student_key, answers)
        return

    section_index = st.session_state.get("section_index", 0)

    if section_index >= len(LEVELS):
        hero()
        st.subheader("Revisão antes de finalizar")
        st.write(
            f"Você respondeu **{len(answers)} de {TOTAL_QUESTIONS} questões**."
        )
        st.progress(len(answers) / TOTAL_QUESTIONS)

        summary_rows = []
        first_incomplete = None
        for i, level in enumerate(LEVELS):
            qids = [q["id"] for q in QUESTIONS if q["level"] == level]
            count = sum(qid in answers for qid in qids)
            if count < len(qids) and first_incomplete is None:
                first_incomplete = i
            summary_rows.append(
                {
                    "Etapa": level,
                    "Respondidas": f"{count}/{len(qids)}",
                    "Status": "Concluída" if count == len(qids) else "Pendente",
                }
            )

        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
        )

        if len(answers) < TOTAL_QUESTIONS:
            st.warning("Ainda existem questões sem resposta.")
            if st.button("Ir para a primeira etapa pendente", type="primary"):
                st.session_state["section_index"] = first_incomplete or 0
                st.rerun()
        else:
            st.info(
                "Ao finalizar, suas respostas ficam bloqueadas e o resultado será exibido."
            )
            if st.button(
                "Finalizar e ver resultado",
                type="primary",
                use_container_width=True,
            ):
                finalize_student(student_key)
                st.rerun()

        if st.button("Voltar para a última etapa"):
            st.session_state["section_index"] = len(LEVELS) - 1
            st.rerun()
        return

    level = LEVELS[section_index]
    level_questions = [q for q in QUESTIONS if q["level"] == level]

    hero()

    total_answered = len(answers)
    st.progress(total_answered / TOTAL_QUESTIONS)
    col_a, col_b = st.columns([3, 1])
    col_a.markdown(f"### {level}")
    col_a.caption(LEVEL_DESCRIPTIONS[level])
    col_b.metric("Progresso", f"{total_answered}/{TOTAL_QUESTIONS}")

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    with st.form(f"form_{level}", clear_on_submit=False):
        selected_answers = {}
        for q in level_questions:
            position = QUESTIONS.index(q) + 1
            selected_answers[q["id"]] = render_question(
                q, position, answers
            )

        submitted = st.form_submit_button(
            "Salvar respostas desta etapa",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        answered_now = 0
        for qid, selected in selected_answers.items():
            if selected is not None:
                save_response(student_key, qid, selected)
                answered_now += 1

        refreshed = get_student_answers(student_key)
        qids = [q["id"] for q in level_questions]
        missing = [qid for qid in qids if qid not in refreshed]

        if missing:
            st.warning(
                f"Respostas salvas, mas ainda faltam {len(missing)} questão(ões) nesta etapa."
            )
        else:
            st.session_state["flash"] = f"Etapa {level} salva com sucesso."
            st.session_state["section_index"] = section_index + 1
            st.rerun()

    nav_left, nav_right = st.columns(2)
    if section_index > 0:
        if nav_left.button("← Voltar", use_container_width=True):
            st.session_state["section_index"] = section_index - 1
            st.rerun()

    if all(q["id"] in answers for q in level_questions):
        if nav_right.button("Avançar →", use_container_width=True):
            st.session_state["section_index"] = section_index + 1
            st.rerun()

    st.caption(
        "Dica: salve a etapa antes de navegar. Isso evita perder respostas ainda não registradas."
    )


# ============================================================
# PROFESSOR
# ============================================================
def teacher_login():
    hero()
    st.subheader("Painel do professor")

    configured_password = get_teacher_password()
    if not configured_password:
        st.error(
            "A senha do professor ainda não foi configurada. "
            "Defina TEACHER_PASSWORD em .streamlit/secrets.toml ou como variável de ambiente."
        )
        return

    with st.form("teacher_login"):
        pwd = st.text_input("Senha do professor", type="password")
        entered = st.form_submit_button(
            "Acessar painel",
            type="primary",
            use_container_width=True,
        )

    if entered:
        if hmac.compare_digest(str(pwd), configured_password):
            st.session_state["teacher_authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")


def make_teacher_exports(students, responses):
    summary = students.copy()
    if not summary.empty:
        summary["score_pct"] = (
            100 * summary["correct"] / TOTAL_QUESTIONS
        ).round(1)
        summary["status"] = summary["submitted_at"].apply(
            lambda x: "Finalizado" if pd.notna(x) and x else "Em andamento"
        )

    detail = responses.copy()
    if not detail.empty:
        qmeta = pd.DataFrame(
            [
                {
                    "qid": q["id"],
                    "level": q["level"],
                    "question": q["prompt"],
                    "correct_answer": q["answer"],
                }
                for q in QUESTIONS
            ]
        )
        detail = detail.merge(qmeta, on="qid", how="left")
        detail["result"] = detail["is_correct"].map(
            {1: "Correta", 0: "Incorreta"}
        )

    return summary, detail


def teacher_dashboard_content():
    students, responses = load_teacher_data()

    if students.empty:
        st.info("Nenhum estudante iniciou a atividade ainda.")
        return

    students = students.copy()
    students["score_pct"] = (
        100 * students["correct"] / TOTAL_QUESTIONS
    ).round(1)
    students["status"] = students["submitted_at"].apply(
        lambda x: "Finalizado" if pd.notna(x) and x else "Em andamento"
    )

    total_students = len(students)
    completed = int((students["status"] == "Finalizado").sum())
    avg_answered = students["answered"].mean()
    avg_score = students.loc[
        students["answered"] > 0, "score_pct"
    ].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estudantes", total_students)
    c2.metric("Finalizados", completed)
    c3.metric("Média respondida", f"{avg_answered:.1f}/{TOTAL_QUESTIONS}")
    c4.metric(
        "Média de acertos",
        "—" if pd.isna(avg_score) else f"{avg_score:.1f}%",
    )

    tab1, tab2, tab3 = st.tabs(
        ["Visão da turma", "Questões", "Estudante"]
    )

    with tab1:
        st.subheader("Acompanhamento da turma")
        table = students[
            [
                "name",
                "ra",
                "answered",
                "correct",
                "score_pct",
                "status",
                "updated_at",
            ]
        ].rename(
            columns={
                "name": "Nome",
                "ra": "RA",
                "answered": "Respondidas",
                "correct": "Acertos",
                "score_pct": "Aproveitamento (%)",
                "status": "Status",
                "updated_at": "Última atualização",
            }
        )
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        qmeta = pd.DataFrame(
            [
                {"qid": q["id"], "Nível": q["level"]}
                for q in QUESTIONS
            ]
        )
        if not responses.empty:
            perf = responses.merge(qmeta, on="qid", how="left")
            level_perf = (
                perf.groupby("Nível", as_index=False)
                .agg(
                    Respostas=("qid", "count"),
                    Acertos=("is_correct", "sum"),
                )
            )
            level_perf["Aproveitamento (%)"] = (
                100 * level_perf["Acertos"] / level_perf["Respostas"]
            ).round(1)

            ordered = pd.Categorical(
                level_perf["Nível"],
                categories=LEVELS,
                ordered=True,
            )
            level_perf = (
                level_perf.assign(_ord=ordered)
                .sort_values("_ord")
                .drop(columns="_ord")
            )

            st.subheader("Aproveitamento por nível")
            st.dataframe(
                level_perf,
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        st.subheader("Diagnóstico por questão")
        qmeta = pd.DataFrame(
            [
                {
                    "qid": q["id"],
                    "Nível": q["level"],
                    "Questão": q["prompt"],
                }
                for q in QUESTIONS
            ]
        )

        if responses.empty:
            qstats = qmeta.copy()
            qstats["Respostas"] = 0
            qstats["Acertos"] = 0
            qstats["Aproveitamento (%)"] = 0.0
        else:
            agg = (
                responses.groupby("qid", as_index=False)
                .agg(
                    Respostas=("qid", "count"),
                    Acertos=("is_correct", "sum"),
                )
            )
            qstats = qmeta.merge(agg, on="qid", how="left").fillna(
                {"Respostas": 0, "Acertos": 0}
            )
            qstats["Respostas"] = qstats["Respostas"].astype(int)
            qstats["Acertos"] = qstats["Acertos"].astype(int)
            qstats["Aproveitamento (%)"] = qstats.apply(
                lambda row: round(
                    100 * row["Acertos"] / row["Respostas"], 1
                )
                if row["Respostas"] > 0
                else 0.0,
                axis=1,
            )

        st.dataframe(
            qstats,
            use_container_width=True,
            hide_index=True,
        )

        attempted = qstats[qstats["Respostas"] > 0]
        if not attempted.empty:
            hardest = attempted.sort_values(
                ["Aproveitamento (%)", "Respostas"],
                ascending=[True, False],
            ).head(5)
            st.subheader("Questões com menor aproveitamento")
            st.dataframe(
                hardest[
                    [
                        "qid",
                        "Nível",
                        "Questão",
                        "Respostas",
                        "Aproveitamento (%)",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab3:
        st.subheader("Detalhamento individual")
        labels = {
            row.student_key: f"{row.name} — RA {row.ra}"
            for row in students.itertuples()
        }
        selected_key = st.selectbox(
            "Selecione um estudante",
            options=list(labels.keys()),
            format_func=lambda k: labels[k],
        )

        selected_student = students[
            students["student_key"] == selected_key
        ].iloc[0]
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric(
            "Respondidas",
            f"{int(selected_student['answered'])}/{TOTAL_QUESTIONS}",
        )
        sc2.metric("Acertos", int(selected_student["correct"]))
        sc3.metric(
            "Aproveitamento",
            f"{selected_student['score_pct']:.1f}%",
        )

        student_resp = responses[
            responses["student_key"] == selected_key
        ].copy()

        detail_rows = []
        for idx, q in enumerate(QUESTIONS, start=1):
            row = student_resp[student_resp["qid"] == q["id"]]
            if row.empty:
                given = "—"
                result = "Não respondida"
            else:
                given = row.iloc[0]["answer"]
                result = (
                    "Correta"
                    if int(row.iloc[0]["is_correct"]) == 1
                    else "Incorreta"
                )

            detail_rows.append(
                {
                    "#": idx,
                    "ID": q["id"],
                    "Nível": q["level"],
                    "Questão": q["prompt"],
                    "Resposta do estudante": given,
                    "Resposta correta": q["answer"],
                    "Resultado": result,
                }
            )

        st.dataframe(
            pd.DataFrame(detail_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Exportar dados")
    summary_export, detail_export = make_teacher_exports(
        students, responses
    )
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar resumo da turma (.csv)",
        data=summary_export.to_csv(index=False).encode("utf-8-sig"),
        file_name="resumo_turma_sistemas_numericos.csv",
        mime="text/csv",
        use_container_width=True,
    )
    d2.download_button(
        "Baixar respostas detalhadas (.csv)",
        data=detail_export.to_csv(index=False).encode("utf-8-sig"),
        file_name="respostas_sistemas_numericos.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        f"Atualizado automaticamente • {datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')}"
    )


@st.fragment(run_every="10s")
def live_teacher_dashboard():
    teacher_dashboard_content()


def teacher_app():
    if not st.session_state.get("teacher_authenticated", False):
        teacher_login()
        return

    hero()
    top1, top2 = st.columns([4, 1])
    top1.markdown("### Painel do professor")
    top1.caption(
        "Acompanhamento das respostas e do desempenho da turma em tempo quase real."
    )
    if top2.button("Sair do painel", use_container_width=True):
        st.session_state["teacher_authenticated"] = False
        st.rerun()

    live_teacher_dashboard()


# ============================================================
# APP
# ============================================================
init_db()

with st.sidebar:
    st.markdown("## Navegação")
    role = st.radio(
        "Acesso",
        ["Aluno", "Professor"],
        horizontal=False,
    )
    st.caption("Aula 01 • Sistemas numéricos")

if role == "Aluno":
    student_app()
else:
    teacher_app()
'''

requirements = """streamlit>=1.37.0
pandas>=2.0.0
"""

secrets_example = """# Copie este arquivo para:
# .streamlit/secrets.toml
# e altere a senha abaixo.

TEACHER_PASSWORD = "troque-esta-senha"
"""

readme = r"""# App Streamlit — Sistemas Numéricos

Atividade interativa com 25 questões de múltipla escolha sobre:

- sistema decimal;
- sistema binário;
- sistema hexadecimal;
- conversões entre as três bases.

A atividade foi organizada em cinco níveis de dificuldade:

1. Conceitual
2. Fácil
3. Médio
4. Difícil
5. Desafiador

Cada nível possui 5 questões.

## Recursos para o estudante

- identificação por nome e RA;
- retomada da atividade usando o mesmo RA;
- 5 questões por etapa para reduzir carga cognitiva;
- indicador de progresso;
- prevenção de finalização com questões pendentes;
- resultado após a entrega;
- revisão das respostas com explicações.

## Recursos para o professor

- acesso protegido por senha;
- painel com atualização automática;
- número de estudantes;
- número de atividades finalizadas;
- respostas e acertos por estudante;
- desempenho por nível;
- desempenho por questão;
- identificação das questões com menor aproveitamento;
- detalhamento individual;
- exportação dos dados em CSV.

## 1. Instalação

No terminal, entre na pasta do projeto e execute:

```bash
pip install -r requirements.txt
