import hmac
import pandas as pd
import streamlit as st

from supabase_db import (
    ACTIVITY_CODE,
    finalize_attempt,
    get_activity,
    get_attempt,
    get_or_create_attempt,
    get_or_create_student,
    get_questions,
    get_responses,
    normalize_ra,
    save_response,
    teacher_dataset,
)

st.set_page_config(
    page_title="Sistemas Numéricos | Estruturas de Dados",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded",
)

LEVELS = ["Conceitual", "Fácil", "Médio", "Difícil", "Desafiador"]

LEVEL_DESCRIPTIONS = {
    "Conceitual": "Compreensão das bases, símbolos e valor posicional.",
    "Fácil": "Conversões diretas com números pequenos.",
    "Médio": "Conversões que exigem mais de uma etapa de raciocínio.",
    "Difícil": "Números maiores e conversões entre diferentes bases.",
    "Desafiador": "Integração entre decimal, binário e hexadecimal.",
}

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1050px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }
        .hero {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 20px;
            padding: 24px 28px;
            margin-bottom: 18px;
            background: linear-gradient(135deg, rgba(73,65,190,.10), rgba(255,255,255,0));
        }
        .hero-kicker {
            font-size: .80rem;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
            opacity: .70;
        }
        .hero-title {
            font-size: clamp(1.8rem, 4vw, 3rem);
            font-weight: 850;
            line-height: 1.06;
            margin-top: 4px;
        }
        .hero-subtitle { margin-top: 8px; opacity: .76; }
        .question-number {
            opacity: .62;
            font-size: .82rem;
            font-weight: 800;
            margin-bottom: 3px;
        }
        .question-text {
            font-size: 1.08rem;
            font-weight: 680;
            margin-bottom: 10px;
        }
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
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
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .hero { padding: 20px; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def hero():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">Estruturas de Dados e Análise de Algoritmos</div>
            <div class="hero-title">Sistemas Numéricos</div>
            <div class="hero-subtitle">Decimal • Binário • Hexadecimal • 25 questões</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def secret_value(name: str, default=""):
    try:
        return str(st.secrets[name])
    except Exception:
        return default


def db_ready():
    required = ["SUPABASE_URL", "SUPABASE_SECRET_KEY"]
    missing = [key for key in required if not secret_value(key)]
    if missing:
        hero()
        st.error(
            "Configuração incompleta. Faltam secrets do Supabase: "
            + ", ".join(missing)
        )
        st.code(
            'SUPABASE_URL = "https://SEU-PROJETO.supabase.co"\n'
            'SUPABASE_SECRET_KEY = "sb_secret_..."\n'
            'TEACHER_PASSWORD = "sua-senha"\n',
            language="toml",
        )
        return False

    try:
        activity = get_activity()
    except Exception as exc:
        hero()
        st.error("Não foi possível conectar ao Supabase.")
        st.exception(exc)
        return False

    if not activity:
        hero()
        st.error(
            f"A atividade {ACTIVITY_CODE} não foi encontrada no Supabase. "
            "Execute o arquivo privado de configuração no SQL Editor."
        )
        return False
    return True


def clear_student_session():
    for key in list(st.session_state.keys()):
        if key.startswith("q_") or key in {
            "student_id",
            "student_name",
            "student_ra",
            "attempt_id",
            "section_index",
            "flash",
        }:
            del st.session_state[key]


def student_login():
    hero()
    st.subheader("Entrar na atividade")
    st.caption(
        "Informe nome e RA. Se você já começou, use o mesmo RA para continuar do ponto salvo."
    )

    with st.form("student_login_form"):
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
        submitted = st.form_submit_button(
            "Iniciar / continuar atividade",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if len(name.strip()) < 3:
            st.error("Informe seu nome completo.")
            return
        if len(normalize_ra(ra)) < 3:
            st.error("Informe um RA válido.")
            return

        try:
            student = get_or_create_student(name, ra)
            attempt = get_or_create_attempt(student["id"])
        except Exception as exc:
            st.error("Não foi possível iniciar a atividade.")
            st.exception(exc)
            return

        clear_student_session()
        st.session_state["student_id"] = student["id"]
        st.session_state["student_name"] = student["name"]
        st.session_state["student_ra"] = student["ra"]
        st.session_state["attempt_id"] = attempt["id"]

        answers = get_responses(attempt["id"])
        questions = get_questions()

        first_incomplete = len(LEVELS)
        for i, level in enumerate(LEVELS):
            qids = [q["id"] for q in questions if q["level"] == level]
            if not qids or not all(qid in answers for qid in qids):
                first_incomplete = i
                break

        st.session_state["section_index"] = first_incomplete
        st.rerun()


def sidebar_student(questions, answers):
    st.sidebar.markdown("### Seu progresso")
    for level in LEVELS:
        qids = [q["id"] for q in questions if q["level"] == level]
        done = sum(qid in answers for qid in qids)
        marker = "✅" if qids and done == len(qids) else "○"
        st.sidebar.write(f"{marker} **{level}** — {done}/{len(qids)}")

    st.sidebar.divider()
    if st.sidebar.button("Sair da atividade", use_container_width=True):
        clear_student_session()
        st.rerun()


def render_question(q, saved_answers):
    saved = saved_answers.get(q["id"], {}).get("answer")
    options = q["options"]
    default_index = options.index(saved) if saved in options else None

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="question-number">QUESTÃO {int(q["position"]):02d} • {q["id"]}</div>
            <div class="question-text">{q["prompt"]}</div>
            """,
            unsafe_allow_html=True,
        )
        return st.radio(
            "Selecione uma alternativa",
            options,
            index=default_index,
            key=f"q_{q['id']}",
            label_visibility="collapsed",
        )


def student_results(attempt, answers):
    questions = get_questions(include_answers=True)
    total = len(questions)
    correct = sum(bool(v["is_correct"]) for v in answers.values())
    pct = 100 * correct / total if total else 0

    hero()
    st.success("Atividade finalizada. Suas respostas foram registradas.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Acertos", f"{correct}/{total}")
    c2.metric("Aproveitamento", f"{pct:.0f}%")
    c3.metric("Respondidas", f"{len(answers)}/{total}")

    rows = []
    for level in LEVELS:
        qs = [q for q in questions if q["level"] == level]
        acertos = sum(
            bool(answers.get(q["id"], {}).get("is_correct", False))
            for q in qs
        )
        rows.append(
            {
                "Nível": level,
                "Acertos": acertos,
                "Questões": len(qs),
                "Aproveitamento": f"{100*acertos/len(qs):.0f}%" if qs else "—",
            }
        )

    st.subheader("Desempenho por nível")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Revisão")
    st.caption("Abra os itens para comparar sua resposta com a resolução.")

    for q in questions:
        response = answers.get(q["id"])
        ok = response and response["is_correct"]
        icon = "✅" if ok else "❌"
        with st.expander(
            f"{icon} Questão {int(q['position']):02d} — {q['level']}"
        ):
            st.write(q["prompt"])
            st.write(
                f"**Sua resposta:** {response['answer'] if response else 'Não respondida'}"
            )
            st.write(f"**Resposta correta:** {q['correct_answer']}")
            st.info(q["explanation"])


def student_app():
    if "attempt_id" not in st.session_state:
        student_login()
        return

    attempt_id = st.session_state["attempt_id"]
    attempt = get_attempt(attempt_id)
    if not attempt:
        clear_student_session()
        st.rerun()

    questions = get_questions()
    answers = get_responses(attempt_id)
    sidebar_student(questions, answers)

    if attempt.get("submitted_at"):
        student_results(attempt, answers)
        return

    total = len(questions)
    section_index = st.session_state.get("section_index", 0)

    if section_index >= len(LEVELS):
        hero()
        st.subheader("Revisão antes de finalizar")
        st.write(f"Você respondeu **{len(answers)} de {total} questões**.")
        st.progress(len(answers) / total if total else 0)

        rows = []
        first_incomplete = None
        for i, level in enumerate(LEVELS):
            qids = [q["id"] for q in questions if q["level"] == level]
            done = sum(qid in answers for qid in qids)
            if qids and done < len(qids) and first_incomplete is None:
                first_incomplete = i
            rows.append(
                {
                    "Etapa": level,
                    "Respondidas": f"{done}/{len(qids)}",
                    "Status": "Concluída" if qids and done == len(qids) else "Pendente",
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if len(answers) < total:
            st.warning("Ainda existem questões sem resposta.")
            if st.button("Ir para a primeira etapa pendente", type="primary"):
                st.session_state["section_index"] = first_incomplete or 0
                st.rerun()
        else:
            st.info(
                "Ao finalizar, as respostas serão bloqueadas e o resultado será exibido."
            )
            if st.button(
                "Finalizar e ver resultado",
                type="primary",
                use_container_width=True,
            ):
                finalize_attempt(attempt_id)
                st.rerun()

        if st.button("← Voltar para a última etapa"):
            st.session_state["section_index"] = len(LEVELS) - 1
            st.rerun()
        return

    level = LEVELS[section_index]
    level_questions = [q for q in questions if q["level"] == level]

    hero()
    st.progress(len(answers) / total if total else 0)

    c1, c2 = st.columns([3, 1])
    c1.markdown(f"### {level}")
    c1.caption(LEVEL_DESCRIPTIONS[level])
    c2.metric("Progresso", f"{len(answers)}/{total}")

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    with st.form(f"form_{level}"):
        selected = {}
        for q in level_questions:
            selected[q["id"]] = render_question(q, answers)

        save = st.form_submit_button(
            "Salvar respostas desta etapa",
            type="primary",
            use_container_width=True,
        )

    if save:
        try:
            for qid, answer in selected.items():
                if answer is not None:
                    save_response(attempt_id, qid, answer)
        except Exception as exc:
            st.error("Não foi possível salvar as respostas.")
            st.exception(exc)
            return

        refreshed = get_responses(attempt_id)
        missing = [q["id"] for q in level_questions if q["id"] not in refreshed]

        if missing:
            st.warning(f"Ainda faltam {len(missing)} questão(ões) nesta etapa.")
        else:
            st.session_state["flash"] = f"Etapa {level} salva com sucesso."
            st.session_state["section_index"] = section_index + 1
            st.rerun()

    left, right = st.columns(2)
    if section_index > 0 and left.button("← Voltar", use_container_width=True):
        st.session_state["section_index"] = section_index - 1
        st.rerun()

    if all(q["id"] in answers for q in level_questions):
        if right.button("Avançar →", use_container_width=True):
            st.session_state["section_index"] = section_index + 1
            st.rerun()

    st.caption(
        "As respostas são registradas no Supabase quando você salva cada etapa."
    )


def teacher_login():
    hero()
    st.subheader("Painel do professor")

    configured = secret_value("TEACHER_PASSWORD")
    if not configured:
        st.error("Defina TEACHER_PASSWORD nos Secrets do Streamlit.")
        return

    with st.form("teacher_login"):
        password = st.text_input("Senha do professor", type="password")
        submit = st.form_submit_button(
            "Acessar painel",
            type="primary",
            use_container_width=True,
        )

    if submit:
        if hmac.compare_digest(str(password), configured):
            st.session_state["teacher_authenticated"] = True
            st.rerun()
        st.error("Senha incorreta.")


def build_teacher_frames():
    students, attempts, responses, questions = teacher_dataset()

    sdf = pd.DataFrame(students)
    adf = pd.DataFrame(attempts)
    rdf = pd.DataFrame(responses)
    qdf = pd.DataFrame(questions)

    if adf.empty:
        return sdf, adf, rdf, qdf, pd.DataFrame()

    student_map = (
        sdf.set_index("id")[["name", "ra"]].to_dict("index")
        if not sdf.empty else {}
    )

    response_counts = {}
    correct_counts = {}
    if not rdf.empty:
        response_counts = rdf.groupby("attempt_id").size().to_dict()
        correct_counts = rdf.groupby("attempt_id")["is_correct"].sum().to_dict()

    total_questions = len(qdf)
    summary_rows = []
    for a in attempts:
        student = student_map.get(a["student_id"], {"name": "—", "ra": "—"})
        answered = int(response_counts.get(a["id"], 0))
        correct = int(correct_counts.get(a["id"], 0))
        summary_rows.append(
            {
                "attempt_id": a["id"],
                "student_id": a["student_id"],
                "Nome": student["name"],
                "RA": student["ra"],
                "Respondidas": answered,
                "Acertos": correct,
                "Aproveitamento (%)": round(100*correct/total_questions, 1) if total_questions else 0,
                "Status": "Finalizado" if a.get("submitted_at") else "Em andamento",
                "Última atualização": a.get("updated_at"),
                "Finalizado em": a.get("submitted_at"),
            }
        )
    return sdf, adf, rdf, qdf, pd.DataFrame(summary_rows)


def teacher_dashboard():
    sdf, adf, rdf, qdf, summary = build_teacher_frames()

    if summary.empty:
        st.info("Nenhum estudante iniciou esta atividade ainda.")
        return

    total_students = len(summary)
    completed = int((summary["Status"] == "Finalizado").sum())
    mean_answered = summary["Respondidas"].mean()
    mean_score = summary["Aproveitamento (%)"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estudantes", total_students)
    c2.metric("Finalizados", completed)
    c3.metric("Média respondida", f"{mean_answered:.1f}/{len(qdf)}")
    c4.metric("Média de acertos", f"{mean_score:.1f}%")

    tab1, tab2, tab3 = st.tabs(["Turma", "Questões", "Estudante"])

    with tab1:
        st.subheader("Acompanhamento da turma")
        st.dataframe(
            summary[
                [
                    "Nome","RA","Respondidas","Acertos",
                    "Aproveitamento (%)","Status","Última atualização"
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        if not rdf.empty and not qdf.empty:
            meta = qdf[["id", "level"]].rename(
                columns={"id": "question_id", "level": "Nível"}
            )
            perf = rdf.merge(meta, on="question_id", how="left")
            level_perf = (
                perf.groupby("Nível", as_index=False)
                .agg(Respostas=("question_id","count"), Acertos=("is_correct","sum"))
            )
            level_perf["Aproveitamento (%)"] = (
                100*level_perf["Acertos"]/level_perf["Respostas"]
            ).round(1)
            level_perf["Nível"] = pd.Categorical(
                level_perf["Nível"], categories=LEVELS, ordered=True
            )
            level_perf = level_perf.sort_values("Nível")
            st.subheader("Aproveitamento por nível")
            st.dataframe(level_perf, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Diagnóstico por questão")
        if qdf.empty:
            st.info("Nenhuma questão cadastrada.")
        else:
            qstats = qdf[["id","position","level","prompt"]].rename(
                columns={
                    "id":"question_id",
                    "position":"#",
                    "level":"Nível",
                    "prompt":"Questão",
                }
            )
            if rdf.empty:
                qstats["Respostas"] = 0
                qstats["Acertos"] = 0
            else:
                agg = (
                    rdf.groupby("question_id", as_index=False)
                    .agg(Respostas=("question_id","count"), Acertos=("is_correct","sum"))
                )
                qstats = qstats.merge(agg, on="question_id", how="left")
                qstats[["Respostas","Acertos"]] = qstats[
                    ["Respostas","Acertos"]
                ].fillna(0).astype(int)

            qstats["Aproveitamento (%)"] = qstats.apply(
                lambda r: round(100*r["Acertos"]/r["Respostas"],1)
                if r["Respostas"] else 0.0,
                axis=1,
            )
            qstats = qstats.sort_values("#")
            st.dataframe(qstats, use_container_width=True, hide_index=True)

            attempted = qstats[qstats["Respostas"] > 0]
            if not attempted.empty:
                st.subheader("Questões com menor aproveitamento")
                hardest = attempted.sort_values(
                    ["Aproveitamento (%)","Respostas"],
                    ascending=[True,False],
                ).head(5)
                st.dataframe(
                    hardest[
                        ["#","Nível","Questão","Respostas","Aproveitamento (%)"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    with tab3:
        st.subheader("Detalhamento individual")
        options = summary["attempt_id"].tolist()
        labels = {
            row["attempt_id"]: f"{row['Nome']} — RA {row['RA']}"
            for _, row in summary.iterrows()
        }
        attempt_id = st.selectbox(
            "Selecione um estudante",
            options,
            format_func=lambda x: labels[x],
        )
        row = summary[summary["attempt_id"] == attempt_id].iloc[0]
        x1, x2, x3 = st.columns(3)
        x1.metric("Respondidas", f"{int(row['Respondidas'])}/{len(qdf)}")
        x2.metric("Acertos", int(row["Acertos"]))
        x3.metric("Aproveitamento", f"{row['Aproveitamento (%)']:.1f}%")

        student_responses = (
            rdf[rdf["attempt_id"] == attempt_id].copy()
            if not rdf.empty else pd.DataFrame()
        )
        response_map = (
            student_responses.set_index("question_id").to_dict("index")
            if not student_responses.empty else {}
        )

        detail = []
        for _, q in qdf.sort_values("position").iterrows():
            r = response_map.get(q["id"])
            detail.append(
                {
                    "#": int(q["position"]),
                    "Nível": q["level"],
                    "Questão": q["prompt"],
                    "Resposta do estudante": r["answer"] if r else "—",
                    "Resposta correta": q["correct_answer"],
                    "Resultado": (
                        "Correta" if r and bool(r["is_correct"])
                        else "Incorreta" if r else "Não respondida"
                    ),
                }
            )
        st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Exportar")
    st.download_button(
        "Baixar resumo da turma (.csv)",
        data=summary.drop(columns=["attempt_id","student_id"]).to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="resumo_turma_sistemas_numericos.csv",
        mime="text/csv",
        use_container_width=True,
    )


@st.fragment(run_every="10s")
def live_dashboard():
    teacher_dashboard()


def teacher_app():
    if not st.session_state.get("teacher_authenticated", False):
        teacher_login()
        return

    hero()
    c1, c2 = st.columns([4,1])
    c1.markdown("### Painel do professor")
    c1.caption("Atualização automática a cada 10 segundos.")
    if c2.button("Sair", use_container_width=True):
        st.session_state["teacher_authenticated"] = False
        st.rerun()

    live_dashboard()


# ============================================================
# INÍCIO
# ============================================================
if not db_ready():
    st.stop()

with st.sidebar:
    st.markdown("## Navegação")
    role = st.radio("Acesso", ["Aluno", "Professor"])
    st.caption("Aula 01 • Sistemas Numéricos")

if role == "Aluno":
    student_app()
else:
    teacher_app()
