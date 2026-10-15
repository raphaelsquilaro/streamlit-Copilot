import json
import os
from datetime import date

import firebase_admin
import streamlit as st
from firebase_admin.exceptions import FirebaseError
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from streamlit.errors import StreamlitSecretNotFoundError


st.set_page_config(page_title="Finanças pessoais", layout="wide")

COLLECTION_NAME = "transactions"


def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    try:
        firebase_config = st.secrets.get("firebase", {})
    except StreamlitSecretNotFoundError:
        firebase_config = {}
    service_account = firebase_config.get("service_account")
    if service_account:
        credential = credentials.Certificate(dict(service_account))
        project_id = firebase_config.get("project_id")
    else:
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        project_id = os.getenv("FIREBASE_PROJECT_ID")

        if service_account_json:
            credential = credentials.Certificate(json.loads(service_account_json))
        elif service_account_path:
            credential = credentials.Certificate(service_account_path)
        else:
            raise RuntimeError(
                "Configure as credenciais do Firebase em "
                ".streamlit/secrets.toml ou nas variáveis de ambiente. "
                "Veja o README.md."
            )

    options = {"projectId": project_id} if project_id else None
    return firebase_admin.initialize_app(credential, options)


def get_transactions(database):
    transactions = []
    for document in database.collection(COLLECTION_NAME).stream():
        transaction = document.to_dict()
        transaction["id"] = document.id
        transactions.append(transaction)
    return sorted(
        transactions,
        key=lambda transaction: transaction.get("date", ""),
        reverse=True,
    )


def save_transaction(database, values, document_id=None):
    values["amount"] = round(float(values["amount"]), 2)
    values["date"] = values["date"].isoformat()
    if document_id:
        database.collection(COLLECTION_NAME).document(document_id).update(values)
    else:
        database.collection(COLLECTION_NAME).add(values)


def format_brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


try:
    firebase_app = get_firebase_app()
    db = firestore.client(app=firebase_app, database_id="(default)")
    transactions = get_transactions(db)
except (
    FirebaseError,
    GoogleAPICallError,
    GoogleAuthError,
    OSError,
    RuntimeError,
    StreamlitSecretNotFoundError,
    ValueError,
) as error:
    st.error(f"Não foi possível conectar ao Firebase: {error}")
    st.stop()

st.title("Finanças pessoais")
st.caption("Acompanhe suas receitas e despesas.")

income = sum(
    transaction.get("amount", 0)
    for transaction in transactions
    if transaction.get("type") == "Receita"
)
expenses = sum(
    transaction.get("amount", 0)
    for transaction in transactions
    if transaction.get("type") == "Despesa"
)

metric_income, metric_expenses, metric_balance = st.columns(3)
metric_income.metric("Receitas", format_brl(income))
metric_expenses.metric("Despesas", format_brl(expenses))
metric_balance.metric("Saldo", format_brl(income - expenses))

tab_list, tab_add, tab_manage = st.tabs(
    ["Lançamentos", "Novo lançamento", "Editar ou excluir"]
)

with tab_list:
    if transactions:
        rows = [
            {
                "Data": transaction.get("date", ""),
                "Tipo": transaction.get("type", ""),
                "Descrição": transaction.get("description", ""),
                "Categoria": transaction.get("category", ""),
                "Valor": format_brl(transaction.get("amount", 0)),
            }
            for transaction in transactions
        ]
        st.dataframe(
            rows,
            hide_index=True,
            alt="Lista de receitas e despesas cadastradas",
        )
    else:
        st.info("Nenhum lançamento cadastrado. Adicione sua primeira receita ou despesa.")

with tab_add:
    with st.form("add_transaction", clear_on_submit=True):
        new_type = st.selectbox("Tipo", ["Despesa", "Receita"])
        new_description = st.text_input("Descrição")
        new_category = st.text_input("Categoria")
        new_amount = st.number_input("Valor (R$)", min_value=0.01, step=1.0, format="%.2f")
        new_date = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        submitted = st.form_submit_button("Salvar lançamento", type="primary")

    if submitted:
        if not new_description.strip() or not new_category.strip():
            st.error("Preencha a descrição e a categoria.")
        else:
            try:
                save_transaction(
                    db,
                    {
                        "type": new_type,
                        "description": new_description.strip(),
                        "category": new_category.strip(),
                        "amount": new_amount,
                        "date": new_date,
                    },
                )
                st.success("Lançamento cadastrado.")
                st.rerun()
            except (FirebaseError, GoogleAPICallError, GoogleAuthError, ValueError) as error:
                st.error(f"Não foi possível salvar o lançamento: {error}")

with tab_manage:
    if not transactions:
        st.info("Cadastre um lançamento para poder editá-lo ou excluí-lo.")
    else:
        transaction_ids = [transaction["id"] for transaction in transactions]

        def transaction_label(transaction_id):
            transaction = next(
                item for item in transactions if item["id"] == transaction_id
            )
            return (
                f'{transaction.get("date", "")} — {transaction.get("description", "")} '
                f'({format_brl(transaction.get("amount", 0))})'
            )

        selected_id = st.selectbox(
            "Selecione um lançamento",
            transaction_ids,
            format_func=transaction_label,
        )
        selected = next(
            transaction for transaction in transactions if transaction["id"] == selected_id
        )
        current_date = date.fromisoformat(selected["date"])

        with st.form("edit_transaction"):
            edit_type = st.selectbox(
                "Tipo", ["Despesa", "Receita"],
                index=["Despesa", "Receita"].index(selected.get("type", "Despesa")),
            )
            edit_description = st.text_input(
                "Descrição", value=selected.get("description", "")
            )
            edit_category = st.text_input("Categoria", value=selected.get("category", ""))
            edit_amount = st.number_input(
                "Valor (R$)",
                min_value=0.01,
                step=1.0,
                format="%.2f",
                value=float(selected.get("amount", 0.01)),
            )
            edit_date = st.date_input(
                "Data", value=current_date, format="DD/MM/YYYY"
            )
            updated = st.form_submit_button("Salvar alterações", type="primary")

        if updated:
            if not edit_description.strip() or not edit_category.strip():
                st.error("Preencha a descrição e a categoria.")
            else:
                try:
                    save_transaction(
                        db,
                        {
                            "type": edit_type,
                            "description": edit_description.strip(),
                            "category": edit_category.strip(),
                            "amount": edit_amount,
                            "date": edit_date,
                        },
                        document_id=selected_id,
                    )
                    st.success("Lançamento atualizado.")
                    st.rerun()
                except (FirebaseError, GoogleAPICallError, GoogleAuthError, ValueError) as error:
                    st.error(f"Não foi possível atualizar o lançamento: {error}")

        st.divider()
        confirm_delete = st.checkbox(
            f"Confirmo a exclusão de “{selected.get('description', '')}”"
        )
        if st.button("Excluir lançamento", type="secondary", disabled=not confirm_delete):
            try:
                db.collection(COLLECTION_NAME).document(selected_id).delete()
                st.success("Lançamento excluído.")
                st.rerun()
            except (FirebaseError, GoogleAPICallError, GoogleAuthError, ValueError) as error:
                st.error(f"Não foi possível excluir o lançamento: {error}")
