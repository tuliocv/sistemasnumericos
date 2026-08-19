import hmac
import pandas as pd
import streamlit as st

from supabase_db import (
    ACTIVITY_CODE,
    finalize_attempt,
    get_activity,
    get_attempt,
    get_challenge_submission,
    get_challenge_ai_feedback,
    get_or_create_attempt,
    get_or_create_student,
    get_questions,
    get_responses,
    normalize_ra,
    save_first_response,
    save_challenge_ai_feedback,
    submit_optional_challenge,
    teacher_dataset,
)

st.set_page_config(
    page_title="Sistemas Numéricos | Estruturas de Dados",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded",
)

LEVELS = ["Conceitual", "Fácil", "Médio", "Difícil", "Desafiador"]


def openai_is_configured():
    """Carrega o módulo de IA apenas quando o desafio realmente precisar dele."""
    from ai_feedback import openai_is_configured as _openai_is_configured
    return _openai_is_configured()


def evaluate_challenge(submission):
    """Evita importar OpenAI/Pydantic durante a abertura da página inicial."""
    from ai_feedback import evaluate_challenge as _evaluate_challenge
    return _evaluate_challenge(submission)


st.markdown(
    """
    <style>
        .block-container {
            max-width: 960px;
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        .hero {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 22px;
            padding: 25px 28px;
            margin-bottom: 20px;
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
            font-size: clamp(1.9rem, 4vw, 3.0rem);
            font-weight: 850;
            line-height: 1.06;
            margin-top: 4px;
        }

        .hero-subtitle {
            margin-top: 8px;
            opacity: .76;
        }

        .question-card {
            border: 1px solid rgba(128,128,128,.20);
            border-radius: 18px;
            padding: 22px;
            margin-top: 12px;
            margin-bottom: 16px;
        }

        .question-number {
            opacity: .62;
            font-size: .80rem;
            font-weight: 800;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .question-text {
            font-size: 1.18rem;
            font-weight: 700;
            margin-top: 8px;
            margin-bottom: 12px;
            line-height: 1.45;
        }

        .locked {
            border-left: 4px solid rgba(128,128,128,.55);
            padding-left: 14px;
            margin: 12px 0;
        }

        .optional-box {
            border: 1px dashed rgba(128,128,128,.38);
            border-radius: 18px;
            padding: 22px;
            margin-top: 22px;
        }

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 46px;
            border-radius: 11px;
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
    """Valida somente a configuração local.

    Não faz chamada de rede durante o bootstrap do Streamlit. Isso evita que
    uma conexão lenta/indisponível com o Supabase bloqueie a primeira
    renderização da página.
    """
    required = ["SUPABASE_URL", "SUPABASE_SECRET_KEY"]
    missing = [key for key in required if not secret_value(key)]

    if missing:
        hero()
        st.error(
            "Configuração incompleta. Faltam Secrets: "
            + ", ".join(missing)
        )
        return False

    return True


def clear_student_session():
    for key in list(st.session_state.keys()):
        if key.startswith("answer_") or key in {
            "student_id",
            "student_name",
            "student_ra",
            "attempt_id",
            "current_position",
            "feedback_qid",
        }:
            del st.session_state[key]


def get_first_unanswered_index(questions, answers):
    for idx, q in enumerate(questions):
        if q["id"] not in answers:
            return idx
    return len(questions)


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
            activity = get_activity()
            if not activity:
                st.error(
                    f"A atividade {ACTIVITY_CODE} não foi encontrada no Supabase."
                )
                return
            if not activity.get("active", False):
                st.warning("Esta atividade está temporariamente desativada.")
                return

            student = get_or_create_student(name, ra)
            attempt = get_or_create_attempt(student["id"])
            questions = get_questions()
            answers = get_responses(attempt["id"])
        except Exception as exc:
            st.error(
                "Não foi possível acessar o Supabase agora. "
                "A página continua disponível; tente novamente em instantes."
            )
            st.caption(f"Detalhe técnico: {exc}")
            return

        clear_student_session()
        st.session_state["student_id"] = student["id"]
        st.session_state["student_name"] = student["name"]
        st.session_state["student_ra"] = student["ra"]
        st.session_state["attempt_id"] = attempt["id"]

        st.session_state["current_position"] = get_first_unanswered_index(
            questions, answers
        )
        st.rerun()


def sidebar_student(questions, answers):
    st.sidebar.markdown("### Seu progresso")

    for level in LEVELS:
        level_q = [q for q in questions if q["level"] == level]
        done = sum(q["id"] in answers for q in level_q)
        marker = "✅" if level_q and done == len(level_q) else "○"
        st.sidebar.write(f"{marker} **{level}** — {done}/{len(level_q)}")

    st.sidebar.divider()
    st.sidebar.caption(
        "Cada questão pode ser respondida apenas uma vez."
    )

    if st.sidebar.button("Sair da atividade", use_container_width=True):
        clear_student_session()
        st.rerun()


def feedback_box(question, response):
    answer_meta = next(
        (
            q for q in get_questions(include_answers=True)
            if q["id"] == question["id"]
        ),
        None,
    )

    if not answer_meta:
        st.warning("Não foi possível carregar o feedback desta questão.")
        return

    if response["is_correct"]:
        st.success("✅ Resposta correta!")
    else:
        st.error("❌ Resposta incorreta.")

    st.markdown(
        f"""
        <div class="locked">
        <strong>Sua resposta:</strong> {response["answer"]}<br>
        <strong>Resposta correta:</strong> {answer_meta["correct_answer"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(f"💡 {answer_meta['explanation']}")
    st.caption(
        "Esta resposta foi registrada e não pode mais ser alterada."
    )


def question_screen(attempt_id, questions, answers):
    total = len(questions)
    idx = st.session_state.get(
        "current_position",
        get_first_unanswered_index(questions, answers),
    )

    if idx >= total:
        finalization_screen(attempt_id, questions, answers)
        return

    question = questions[idx]
    response = answers.get(question["id"])

    hero()

    answered_count = len(answers)
    st.progress(answered_count / total if total else 0)

    left, right = st.columns([3, 1])
    left.caption(f"Nível atual: **{question['level']}**")
    right.metric("Progresso", f"{answered_count}/{total}")

    st.markdown(
        f"""
        <div class="question-card">
            <div class="question-number">
                Questão {int(question["position"]):02d} de {total} • {question["level"]}
            </div>
            <div class="question-text">{question["prompt"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if response:
        feedback_box(question, response)

        button_label = (
            "Ir para conclusão da lista →"
            if idx == total - 1
            else "Próxima questão →"
        )

        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
        ):
            st.session_state["current_position"] = idx + 1
            st.rerun()
        return

    with st.form(f"question_form_{question['id']}"):
        selected = st.radio(
            "Selecione uma alternativa",
            question["options"],
            index=None,
            key=f"answer_{question['id']}",
        )

        verify = st.form_submit_button(
            "Verificar resposta",
            type="primary",
            use_container_width=True,
        )

    if verify:
        if selected is None:
            st.warning("Selecione uma alternativa antes de verificar.")
            return

        try:
            result = save_first_response(
                attempt_id,
                question["id"],
                selected,
            )
        except Exception as exc:
            st.error("Não foi possível registrar sua resposta.")
            st.exception(exc)
            return

        # Mantém a tela na mesma questão para exibir o feedback.
        st.session_state["feedback_qid"] = question["id"]
        st.rerun()


def finalization_screen(attempt_id, questions, answers):
    hero()

    total = len(questions)
    answered = len(answers)
    correct = sum(bool(r["is_correct"]) for r in answers.values())

    st.subheader("Você chegou ao final da lista 🎯")
    st.write(
        "Todas as respostas já registradas estão bloqueadas. "
        "Revise apenas o resumo abaixo e, quando estiver pronto, encerre a lista."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Respondidas", f"{answered}/{total}")
    c2.metric("Acertos até aqui", correct)
    c3.metric(
        "Aproveitamento",
        f"{100*correct/total:.0f}%" if total else "—",
    )

    if answered < total:
        st.warning("Ainda existem questões obrigatórias sem resposta.")
        if st.button(
            "Voltar para a primeira questão pendente",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["current_position"] = get_first_unanswered_index(
                questions, answers
            )
            st.rerun()
        return

    st.info(
        "Ao clicar em **Finalizar lista**, sua tentativa será encerrada. "
        "Depois disso você poderá ver o resultado completo e, se quiser, "
        "fazer o Desafio de Criação opcional."
    )

    if st.button(
        "Finalizar lista",
        type="primary",
        use_container_width=True,
    ):
        try:
            finalize_attempt(attempt_id)
        except Exception as exc:
            st.error("Não foi possível finalizar a lista.")
            st.exception(exc)
            return
        st.rerun()


def render_ai_feedback(feedback):
    total = float(feedback["total_score"])

    st.markdown("### 🤖 Feedback formativo da IA")
    st.caption(
        "Este retorno é formativo e não altera sua nota ou o resultado das 25 questões."
    )

    c1, c2 = st.columns([1, 2])
    c1.metric("Indicador formativo", f"{total:.1f}/10")
    c2.info(
        "A IA foi orientada a não entregar a solução pronta. "
        "Use o feedback para revisar e explicar melhor a sua própria estratégia."
    )

    st.markdown("#### 📊 Rubrica")
    rubric = pd.DataFrame(
        [
            ["Lógica Decimal → Binário", float(feedback["binary_logic_score"]), 2],
            ["Lógica Decimal → Hexadecimal", float(feedback["hexadecimal_logic_score"]), 2],
            ["Construção do algoritmo", float(feedback["algorithm_score"]), 2],
            ["Teste e coerência", float(feedback["test_score"]), 2],
            ["Clareza da explicação", float(feedback["clarity_score"]), 2],
        ],
        columns=["Critério", "Pontuação", "Máximo"],
    )
    st.dataframe(rubric, use_container_width=True, hide_index=True)

    if feedback.get("strengths"):
        st.markdown("#### ✅ O que você já construiu bem")
        for item in feedback["strengths"]:
            st.write(f"• {item}")

    if feedback.get("areas_to_review"):
        st.markdown("#### 🔎 O que vale revisar")
        for item in feedback["areas_to_review"]:
            st.write(f"• {item}")

    if feedback.get("guiding_questions"):
        st.markdown("#### 🧠 Perguntas para orientar sua revisão")
        for i, item in enumerate(feedback["guiding_questions"], start=1):
            st.write(f"{i}. {item}")

    st.markdown("#### 💡 Próximo passo")
    st.write(feedback["next_step"])

    st.markdown("#### Síntese")
    st.write(feedback["formative_summary"])

    st.caption(
        "Feedback gerado por IA. Ele pode conter imprecisões; o professor pode revisar "
        "a atividade e o retorno apresentado."
    )


def generate_ai_feedback_for_attempt(attempt_id, submission):
    existing = get_challenge_ai_feedback(attempt_id)
    if existing:
        return existing

    feedback, model, response_id = evaluate_challenge(submission)
    saved = save_challenge_ai_feedback(
        attempt_id=attempt_id,
        feedback=feedback,
        model=model,
        openai_response_id=response_id,
    )
    return saved


def optional_challenge(attempt_id):
    submission = get_challenge_submission(attempt_id)
    ai_feedback = get_challenge_ai_feedback(attempt_id) if submission else None

    st.markdown(
        """
        <div class="optional-box">
            <h3>🚀 Quer ir além? — Desafio de Criação</h3>
            <p>
                <strong>Opcional.</strong> Este desafio não altera sua nota,
                seu aproveitamento ou a conclusão das 25 questões.
            </p>
            <p>
                Crie uma solução que receba um número decimal e produza suas
                representações em binário e hexadecimal <strong>sem utilizar
                funções prontas de conversão</strong>.
            </p>
            <p>
                Se você enviar, receberá um <strong>feedback formativo por IA</strong>.
                A IA não deve fornecer a solução pronta: o objetivo é ajudar você a
                refletir e melhorar sua própria construção.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if submission:
        st.success("🌟 Desafio de Criação enviado.")
        st.caption(
            "Sua submissão foi registrada e não pode ser alterada."
        )

        with st.expander("Visualizar minha submissão"):
            st.write("**Estratégia utilizada**")
            st.write(submission["strategy"])

            st.write("**Pseudocódigo ou código**")
            st.code(submission["code_text"], language="java")

            st.write(f"**Número testado:** {submission['test_number']}")
            st.write(f"**Resultado binário informado:** {submission['binary_result']}")
            st.write(f"**Resultado hexadecimal informado:** {submission['hex_result']}")

        if ai_feedback:
            render_ai_feedback(ai_feedback)
            return

        if not openai_is_configured():
            st.warning(
                "O desafio foi salvo, mas o feedback por IA ainda não está disponível "
                "porque a OPENAI_API_KEY não foi configurada no Streamlit."
            )
            return

        st.info(
            "Seu desafio está salvo. O feedback ainda não foi gerado."
        )
        if st.button(
            "Gerar meu feedback formativo",
            type="primary",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "Analisando sua estratégia e preparando perguntas orientadoras..."
                ):
                    generate_ai_feedback_for_attempt(attempt_id, submission)
                st.rerun()
            except Exception as exc:
                st.error(
                    "Não foi possível gerar o feedback agora. "
                    "Sua atividade continua salva e você poderá tentar novamente."
                )
                st.caption(str(exc))
        return

    with st.expander("Fazer o Desafio de Criação", expanded=False):
        st.write(
            "Explique como sua solução realiza as duas conversões e apresente "
            "um pseudocódigo ou código Java."
        )

        with st.form("challenge_form"):
            strategy = st.text_area(
                "1. Explique a estratégia do seu algoritmo",
                height=130,
                placeholder=(
                    "Descreva como você faria a conversão Decimal → Binário "
                    "e Decimal → Hexadecimal."
                ),
            )

            code_text = st.text_area(
                "2. Escreva seu pseudocódigo ou código Java",
                height=220,
                placeholder="// Sua solução aqui",
            )

            c1, c2, c3 = st.columns(3)
            test_number = c1.text_input(
                "3. Número decimal testado",
                placeholder="Ex.: 45",
            )
            binary_result = c2.text_input(
                "Resultado binário",
                placeholder="Ex.: 101101",
            )
            hex_result = c3.text_input(
                "Resultado hexadecimal",
                placeholder="Ex.: 2D",
            )

            send = st.form_submit_button(
                "Enviar Desafio de Criação",
                type="primary",
                use_container_width=True,
            )

        if send:
            if not all(
                [
                    strategy.strip(),
                    code_text.strip(),
                    test_number.strip(),
                    binary_result.strip(),
                    hex_result.strip(),
                ]
            ):
                st.warning("Preencha todos os campos do desafio antes de enviar.")
                return

            try:
                submission = submit_optional_challenge(
                    attempt_id,
                    strategy,
                    code_text,
                    test_number,
                    binary_result,
                    hex_result,
                )
            except Exception as exc:
                st.error("Não foi possível enviar o desafio.")
                st.exception(exc)
                return

            if openai_is_configured():
                try:
                    with st.spinner(
                        "Desafio salvo. Preparando seu feedback formativo..."
                    ):
                        generate_ai_feedback_for_attempt(attempt_id, submission)
                except Exception:
                    # A submissão não é perdida se a API estiver temporariamente indisponível.
                    pass

            st.rerun()

def student_results(attempt_id, answers):
    questions = get_questions(include_answers=True)
    total = len(questions)
    correct = sum(bool(v["is_correct"]) for v in answers.values())
    pct = 100 * correct / total if total else 0

    hero()
    st.success("✅ Lista concluída com sucesso!")

    c1, c2, c3 = st.columns(3)
    c1.metric("Acertos", f"{correct}/{total}")
    c2.metric("Aproveitamento", f"{pct:.0f}%")
    c3.metric("Questões", f"{len(answers)}/{total}")

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
                "Aproveitamento": (
                    f"{100*acertos/len(qs):.0f}%" if qs else "—"
                ),
            }
        )

    st.subheader("Desempenho por nível")
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Rever as 25 questões"):
        for q in questions:
            response = answers.get(q["id"])
            ok = response and response["is_correct"]
            icon = "✅" if ok else "❌"

            st.markdown(
                f"**{icon} Questão {int(q['position']):02d} — {q['level']}**"
            )
            st.write(q["prompt"])
            st.write(
                f"**Sua resposta:** "
                f"{response['answer'] if response else 'Não respondida'}"
            )
            st.write(f"**Resposta correta:** {q['correct_answer']}")
            st.caption(q["explanation"])
            st.divider()

    optional_challenge(attempt_id)


def student_app():
    if "attempt_id" not in st.session_state:
        student_login()
        return

    attempt_id = st.session_state["attempt_id"]

    # Mostra uma mensagem imediatamente enquanto uma sessão anterior é retomada.
    # Assim, uma eventual lentidão do Supabase não deixa a tela aparentemente vazia.
    status = st.empty()
    status.info("Reconectando à sua atividade salva...")

    try:
        attempt = get_attempt(attempt_id)
        if not attempt:
            status.empty()
            clear_student_session()
            st.rerun()

        questions = get_questions()
        answers = get_responses(attempt_id)
    except Exception as exc:
        status.empty()
        hero()
        st.warning(
            "Não foi possível retomar sua sessão automaticamente. "
            "Isso pode ocorrer quando o banco ainda está reconectando."
        )
        st.caption(f"Detalhe técnico: {exc}")

        c1, c2 = st.columns(2)
        if c1.button("Tentar novamente", type="primary", use_container_width=True):
            st.rerun()
        if c2.button("Voltar para o login", use_container_width=True):
            clear_student_session()
            st.rerun()
        return

    status.empty()
    sidebar_student(questions, answers)

    if attempt.get("submitted_at"):
        student_results(attempt_id, answers)
        return

    question_screen(attempt_id, questions, answers)


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
        else:
            st.error("Senha incorreta.")


def build_teacher_frames():
    students, attempts, responses, questions, challenges, ai_feedbacks = teacher_dataset()

    sdf = pd.DataFrame(students)
    adf = pd.DataFrame(attempts)
    rdf = pd.DataFrame(responses)
    qdf = pd.DataFrame(questions)
    cdf = pd.DataFrame(challenges)
    fdf = pd.DataFrame(ai_feedbacks)

    if adf.empty:
        return sdf, adf, rdf, qdf, cdf, fdf, pd.DataFrame()

    student_map = (
        sdf.set_index("id")[["name", "ra"]].to_dict("index")
        if not sdf.empty else {}
    )

    response_counts = {}
    correct_counts = {}
    if not rdf.empty:
        response_counts = rdf.groupby("attempt_id").size().to_dict()
        correct_counts = (
            rdf.groupby("attempt_id")["is_correct"].sum().to_dict()
        )

    challenge_ids = (
        set(cdf["attempt_id"].tolist())
        if not cdf.empty else set()
    )

    feedback_ids = (
        set(fdf["attempt_id"].tolist())
        if not fdf.empty else set()
    )

    total_questions = len(qdf)
    summary_rows = []

    for a in attempts:
        student = student_map.get(
            a["student_id"],
            {"name": "—", "ra": "—"},
        )
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
                "Aproveitamento (%)": (
                    round(100 * correct / total_questions, 1)
                    if total_questions else 0
                ),
                "Status": (
                    "Finalizado"
                    if a.get("submitted_at")
                    else "Em andamento"
                ),
                "Desafio": (
                    "Enviado"
                    if a["id"] in challenge_ids
                    else (
                        "Não realizado"
                        if a.get("submitted_at")
                        else "—"
                    )
                ),
                "Feedback IA": (
                    "Disponível"
                    if a["id"] in feedback_ids
                    else (
                        "Pendente"
                        if a["id"] in challenge_ids
                        else "—"
                    )
                ),
                "Última atualização": a.get("updated_at"),
                "Finalizado em": a.get("submitted_at"),
            }
        )

    return sdf, adf, rdf, qdf, cdf, fdf, pd.DataFrame(summary_rows)


def teacher_dashboard():
    sdf, adf, rdf, qdf, cdf, fdf, summary = build_teacher_frames()

    if summary.empty:
        st.info("Nenhum estudante iniciou esta atividade ainda.")
        return

    total_students = len(summary)
    completed = int((summary["Status"] == "Finalizado").sum())
    challenges = int((summary["Desafio"] == "Enviado").sum())
    mean_answered = summary["Respondidas"].mean()
    mean_score = summary["Aproveitamento (%)"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Estudantes", total_students)
    c2.metric("Finalizados", completed)
    c3.metric("Desafios", challenges)
    c4.metric("Média respondida", f"{mean_answered:.1f}/{len(qdf)}")
    c5.metric("Média de acertos", f"{mean_score:.1f}%")

    tab1, tab2, tab3 = st.tabs(
        ["Turma", "Questões", "Estudante"]
    )

    with tab1:
        st.subheader("Acompanhamento da turma")
        st.dataframe(
            summary[
                [
                    "Nome",
                    "RA",
                    "Respondidas",
                    "Acertos",
                    "Aproveitamento (%)",
                    "Status",
                    "Desafio",
                    "Feedback IA",
                    "Última atualização",
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
                .agg(
                    Respostas=("question_id", "count"),
                    Acertos=("is_correct", "sum"),
                )
            )
            level_perf["Aproveitamento (%)"] = (
                100
                * level_perf["Acertos"]
                / level_perf["Respostas"]
            ).round(1)

            level_perf["Nível"] = pd.Categorical(
                level_perf["Nível"],
                categories=LEVELS,
                ordered=True,
            )
            level_perf = level_perf.sort_values("Nível")

            st.subheader("Aproveitamento por nível")
            st.dataframe(
                level_perf,
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        st.subheader("Diagnóstico por questão")

        if qdf.empty:
            st.info("Nenhuma questão cadastrada.")
        else:
            qstats = qdf[
                ["id", "position", "level", "prompt"]
            ].rename(
                columns={
                    "id": "question_id",
                    "position": "#",
                    "level": "Nível",
                    "prompt": "Questão",
                }
            )

            if rdf.empty:
                qstats["Respostas"] = 0
                qstats["Acertos"] = 0
            else:
                agg = (
                    rdf.groupby("question_id", as_index=False)
                    .agg(
                        Respostas=("question_id", "count"),
                        Acertos=("is_correct", "sum"),
                    )
                )
                qstats = qstats.merge(
                    agg,
                    on="question_id",
                    how="left",
                )
                qstats[["Respostas", "Acertos"]] = qstats[
                    ["Respostas", "Acertos"]
                ].fillna(0).astype(int)

            qstats["Aproveitamento (%)"] = qstats.apply(
                lambda r: (
                    round(
                        100 * r["Acertos"] / r["Respostas"],
                        1,
                    )
                    if r["Respostas"] else 0.0
                ),
                axis=1,
            )

            qstats = qstats.sort_values("#")

            st.dataframe(
                qstats,
                use_container_width=True,
                hide_index=True,
            )

            attempted = qstats[qstats["Respostas"] > 0]
            if not attempted.empty:
                st.subheader("Questões com menor aproveitamento")
                hardest = attempted.sort_values(
                    ["Aproveitamento (%)", "Respostas"],
                    ascending=[True, False],
                ).head(5)

                st.dataframe(
                    hardest[
                        [
                            "#",
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

        options = summary["attempt_id"].tolist()
        labels = {
            row["attempt_id"]: (
                f"{row['Nome']} — RA {row['RA']}"
            )
            for _, row in summary.iterrows()
        }

        attempt_id = st.selectbox(
            "Selecione um estudante",
            options,
            format_func=lambda x: labels[x],
        )

        row = summary[
            summary["attempt_id"] == attempt_id
        ].iloc[0]

        x1, x2, x3, x4 = st.columns(4)
        x1.metric(
            "Respondidas",
            f"{int(row['Respondidas'])}/{len(qdf)}",
        )
        x2.metric("Acertos", int(row["Acertos"]))
        x3.metric(
            "Aproveitamento",
            f"{row['Aproveitamento (%)']:.1f}%",
        )
        x4.metric("Desafio", row["Desafio"])

        student_responses = (
            rdf[rdf["attempt_id"] == attempt_id].copy()
            if not rdf.empty
            else pd.DataFrame()
        )

        response_map = (
            student_responses
            .set_index("question_id")
            .to_dict("index")
            if not student_responses.empty
            else {}
        )

        detail = []
        for _, q in qdf.sort_values("position").iterrows():
            r = response_map.get(q["id"])
            detail.append(
                {
                    "#": int(q["position"]),
                    "Nível": q["level"],
                    "Questão": q["prompt"],
                    "Resposta do estudante": (
                        r["answer"] if r else "—"
                    ),
                    "Resposta correta": q["correct_answer"],
                    "Resultado": (
                        "Correta"
                        if r and bool(r["is_correct"])
                        else (
                            "Incorreta"
                            if r
                            else "Não respondida"
                        )
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(detail),
            use_container_width=True,
            hide_index=True,
        )

        if not cdf.empty:
            challenge = cdf[
                cdf["attempt_id"] == attempt_id
            ]

            if not challenge.empty:
                challenge = challenge.iloc[0]

                st.subheader("🚀 Desafio de Criação")
                st.write("**Estratégia**")
                st.write(challenge["strategy"])

                st.write("**Pseudocódigo / código**")
                st.code(
                    challenge["code_text"],
                    language="java",
                )

                cc1, cc2, cc3 = st.columns(3)
                cc1.write(
                    f"**Número:** {challenge['test_number']}"
                )
                cc2.write(
                    f"**Binário:** {challenge['binary_result']}"
                )
                cc3.write(
                    f"**Hexadecimal:** {challenge['hex_result']}"
                )

                if not fdf.empty:
                    ai_row = fdf[
                        fdf["attempt_id"] == attempt_id
                    ]
                    if not ai_row.empty:
                        st.markdown("---")
                        st.markdown("### 🤖 Feedback formativo da IA")
                        render_ai_feedback(ai_row.iloc[0].to_dict())

    st.divider()
    st.subheader("Exportar")

    st.download_button(
        "Baixar resumo da turma (.csv)",
        data=summary.drop(
            columns=["attempt_id", "student_id"]
        ).to_csv(index=False).encode("utf-8-sig"),
        file_name="resumo_turma_sistemas_numericos.csv",
        mime="text/csv",
        use_container_width=True,
    )


@st.fragment(run_every="10s")
def live_dashboard():
    teacher_dashboard()


def teacher_app():
    if not st.session_state.get(
        "teacher_authenticated",
        False,
    ):
        teacher_login()
        return

    hero()

    c1, c2 = st.columns([4, 1])
    c1.markdown("### Painel do professor")
    c1.caption("Atualização automática a cada 10 segundos.")

    if c2.button("Sair", use_container_width=True):
        st.session_state["teacher_authenticated"] = False
        st.rerun()

    live_dashboard()


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
