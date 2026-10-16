import os
import pandas as pd
import requests
import streamlit as st

from src.reconciliation.report import build_operations_report
from src.reconciliation.uploads import validate_business_csv


st.set_page_config(
    page_title="Slimes.Hustlers | Business Operations",
    page_icon="📊",
    layout="wide",
)

st.title("Slimes.Hustlers")
st.subheader("AI Business Operations Agent Dashboard")
st.caption("Verified reconciliation reports and operational exceptions")

st.markdown("### Business data")

st.caption(
    "Upload your own business CSV files to generate a report, "
    "or leave all three empty to use the built-in demonstration data."
)

orders_file = st.file_uploader(
    "Orders CSV",
    type=["csv"],
    key="orders_csv_upload",
)
invoices_file = st.file_uploader(
    "Invoices CSV",
    type=["csv"],
    key="invoices_csv_upload",
)
inventory_file = st.file_uploader(
    "Inventory CSV",
    type=["csv"],
    key="inventory_csv_upload",
)

uploaded_files = [orders_file, invoices_file, inventory_file]
uploaded_count = sum(file is not None for file in uploaded_files)

if st.button("Refresh report", type="primary"):
    st.rerun()

if uploaded_count not in (0, 3):
    st.error(
        "Upload all three CSV files, or remove the uploaded files "
        "to return to demo mode. No report was generated."
    )
    st.stop()

try:
    if uploaded_count == 3:
        orders = validate_business_csv(
            pd.read_csv(orders_file), "orders"
        )
        invoices = validate_business_csv(
            pd.read_csv(invoices_file), "invoices"
        )
        inventory = validate_business_csv(
            pd.read_csv(inventory_file), "inventory"
        )

        report = build_operations_report(
            orders=orders,
            invoices=invoices,
            inventory=inventory,
        )
        st.success(
            "UPLOADED DATA — The report below uses the three CSV files "
            "currently held in this dashboard session. Files are not "
            "saved to disk by this upload workflow."
        )
    else:
        report = build_operations_report()
        st.info(
            "DEMO DATA — This dashboard reads the project's sample CSV "
            "files. It does not display live data from a customer business."
        )

    summary = report["summary"]

except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(f"Could not process the uploaded CSV data: {exc}")
    st.stop()
except Exception as exc:
    st.error(
        "The operations report could not be loaded. "
        "Check the application logs and data files."
    )
    with st.expander("Technical details"):
        st.code(f"{type(exc).__name__}: {exc}")
    st.stop()

# AI AGENT WORKSPACE ? CHAT UI
st.divider()
st.markdown("### AI Agent workspace")
st.caption(
    "Ask the Business Operations Agent to investigate an issue or explain "
    "the verified report. Responses come from the existing authenticated API."
)

api_url = os.getenv(
    "BUSINESS_OPERATIONS_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
api_token = os.getenv("BUSINESS_OPERATIONS_API_TOKEN", "")

if not api_token:
    st.warning(
        "Chat is not connected yet. Configure BUSINESS_OPERATIONS_API_TOKEN "
        "in the dashboard process environment. Do not put API tokens in this file."
    )

if "agent_chat_history" not in st.session_state:
    st.session_state["agent_chat_history"] = []

with st.container(border=True):
    for chat_message in st.session_state["agent_chat_history"]:
        with st.chat_message(chat_message["role"]):
            st.markdown(chat_message["content"])

    with st.form("business_operations_agent_chat", clear_on_submit=True):
        prompt = st.text_area(
            "Message the AI Business Operations Agent",
            placeholder=(
                "For example: Explain the financial exceptions in the "
                "current report, or investigate order ORD-1004."
            ),
            height=100,
            max_chars=10000,
        )
        submitted = st.form_submit_button(
            "Send message",
            type="primary",
            disabled=not bool(api_token),
        )

    if submitted:
        message = prompt.strip()

        if not message:
            st.warning("Enter a message before submitting.")
        else:
            st.session_state["agent_chat_history"].append(
                {"role": "user", "content": message}
            )

            try:
                with st.spinner("The agent is working..."):
                    if all(
                        uploaded_file is not None
                        for uploaded_file in (orders_file, invoices_file, inventory_file)
                    ):
                        files = {
                            "orders_file": (
                                orders_file.name,
                                orders_file.getvalue(),
                                "text/csv",
                            ),
                            "invoices_file": (
                                invoices_file.name,
                                invoices_file.getvalue(),
                                "text/csv",
                         ),
                            "inventory_file": (
                                inventory_file.name,
                                inventory_file.getvalue(),
                                "text/csv",
                            ),
                        }

                        response = requests.post(
                            f"{api_url}/agent/chat",
                            headers={"Authorization": f"Bearer {api_token}"},
                            data={"message": message},
                            files=files,
                            timeout=120,
                        )
                    else:
                        response = requests.post(
                            f"{api_url}/agent/chat",
                            headers={"Authorization": f"Bearer {api_token}"},
                            json={"message": message},
                            timeout=120,
                        )

                if response.ok:
                    payload = response.json()
                    answer = payload.get("response", "").strip()

                    if answer:
                        st.session_state["agent_chat_history"].append(
                            {"role": "assistant", "content": answer}
                        )
                    else:
                        st.session_state["agent_chat_history"].append(
                            {
                                "role": "assistant",
                                "content": (
                                    "The API returned no response text. "
                                    "Please try again."
                                ),
                            }
                        )
                else:
                    try:
                        detail = response.json().get(
                            "detail", "The API rejected the request."
                        )
                    except ValueError:
                        detail = "The API returned an unreadable error response."

                    st.session_state["agent_chat_history"].append(
                        {
                            "role": "assistant",
                            "content": f"Request failed (HTTP {response.status_code}): {detail}",
                        }
                    )

            except requests.RequestException:
                st.session_state["agent_chat_history"].append(
                    {
                        "role": "assistant",
                        "content": (
                            "Could not reach the agent API. Confirm that the "
                            "API server is running and the configured URL is correct."
                        ),
                    }
                )

            st.rerun()

    if st.session_state["agent_chat_history"]:
        if st.button("Clear conversation"):
            st.session_state["agent_chat_history"] = []
            st.rerun()


def display_table(data, columns, column_config=None):
    """Render readable tables without mixing text and numeric Arrow types."""
    frame = pd.DataFrame(data)

    if frame.empty:
        st.success("No exceptions found.")
        return

    missing_columns = [name for name in columns if name not in frame.columns]
    if missing_columns:
        st.error(
            "This report is missing expected fields: "
            + ", ".join(missing_columns)
        )
        return

    frame = frame.loc[:, columns].copy()

    currency_columns = {
        "expected_amount",
        "invoice_amount",
        "amount_difference",
        "unit_cost",
    }

    # Convert the display copy to consistent text values.
    # The original report data remains unchanged.
    for column in frame.columns:
        if column in currency_columns:
            frame[column] = frame[column].map(
                lambda value: (
                    "Not available"
                    if pd.isna(value)
                    else f"${value:,.2f}"
                )
            )
        else:
            frame[column] = frame[column].map(
                lambda value: (
                    "Not available"
                    if pd.isna(value)
                    else str(value)
                )
            )

    # TextColumn is intentional: currency formatting is now handled above.
    text_config = {
        column: st.column_config.TextColumn(
            column.replace("_", " ").title(),
            width="large" if column == "recommended_action" else "medium",
        )
        for column in frame.columns
    }

    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config=text_config,
    )



st.subheader("Operations overview")

orders_processed = summary.get("orders_processed", 0)
matched_orders = summary.get("matched_orders", 0)
financial_exceptions = summary.get("financial_exceptions", 0)
inventory_exceptions = summary.get("inventory_exceptions", 0)
invoices_processed = summary.get("invoices_processed", 0)
orphan_invoices = summary.get("orphan_invoices", 0)
inventory_records = summary.get("inventory_records", 0)

overview_rows = [
    [
        ("Orders processed", orders_processed),
        ("Matched orders", matched_orders),
        ("Financial exceptions", financial_exceptions),
        ("Inventory exceptions", inventory_exceptions),
    ],
    [
        ("Invoices processed", invoices_processed),
        ("Orphan invoices", orphan_invoices),
        ("Inventory records", inventory_records),
    ],
]

for metrics in overview_rows:
    columns = st.columns(len(metrics), gap="medium")

    for column, (label, value) in zip(columns, metrics):
        with column:
            with st.container(border=True):
                st.metric(label=label, value=value)

has_exceptions = any(
    summary[key] > 0
    for key in (
        "financial_exceptions",
        "orphan_invoices",
        "inventory_exceptions",
    )
)

if has_exceptions:
    st.warning("Action required: one or more exceptions need review.")
else:
    st.success("No exceptions were identified in this report.")

financial_tab, inventory_tab, orphan_tab = st.tabs(
    ["Financial exceptions", "Inventory alerts", "Orphan invoices"]
)

with financial_tab:
    st.markdown("#### Orders requiring financial review")
    st.caption(
        "A discrepancy identifies a difference in available records; "
        "it does not, by itself, establish the cause."
    )

    display_table(
        report["financial_exceptions"],
        [
            "order_id",
            "invoice_id",
            "customer",
            "sku",
            "reconciliation_status",
            "expected_amount",
            "invoice_amount",
            "amount_difference",
            "priority",
            "recommended_action",
        ],
        {
            "order_id": st.column_config.TextColumn("Order ID"),
            "invoice_id": st.column_config.TextColumn("Invoice ID"),
            "customer": st.column_config.TextColumn("Customer"),
            "sku": st.column_config.TextColumn("SKU"),
            "reconciliation_status": st.column_config.TextColumn("Exception"),
            "expected_amount": st.column_config.NumberColumn(
                "Expected amount", format="$%.2f"
            ),
            "invoice_amount": st.column_config.NumberColumn(
                "Invoice amount", format="$%.2f"
            ),
            "amount_difference": st.column_config.NumberColumn(
                "Difference", format="$%.2f"
            ),
            "priority": st.column_config.TextColumn("Priority"),
            "recommended_action": st.column_config.TextColumn(
                "Recommended action", width="large"
            ),
        },
    )

with inventory_tab:
    st.markdown("#### Inventory requiring review")
    st.caption(
        "Stock alerts are based on recorded quantities and configured "
        "reorder levels."
    )

    display_table(
        report["inventory_exceptions"],
        [
            "sku",
            "product_name",
            "stock_quantity",
            "reorder_level",
            "unit_cost",
            "issue_type",
            "priority",
            "recommended_action",
        ],
        {
            "sku": st.column_config.TextColumn("SKU"),
            "product_name": st.column_config.TextColumn("Product"),
            "stock_quantity": st.column_config.NumberColumn(
                "Current stock", format="%d"
            ),
            "reorder_level": st.column_config.NumberColumn(
                "Reorder level", format="%d"
            ),
            "unit_cost": st.column_config.NumberColumn(
                "Recorded unit cost", format="$%.2f"
            ),
            "issue_type": st.column_config.TextColumn("Alert"),
            "priority": st.column_config.TextColumn("Priority"),
            "recommended_action": st.column_config.TextColumn(
                "Recommended action", width="large"
            ),
        },
    )

with orphan_tab:
    st.markdown("#### Invoices without a matching order")
    st.caption(
        "These invoices reference orders that were not found in the "
        "available order records. Review before taking action."
    )

    display_table(
        report["orphan_invoices"],
        [
            "invoice_id",
            "order_id",
            "invoice_amount",
            "status",
            "issue_type",
        ],
        {
            "invoice_id": st.column_config.TextColumn("Invoice ID"),
            "order_id": st.column_config.TextColumn("Referenced order"),
            "invoice_amount": st.column_config.NumberColumn(
                "Invoice amount", format="$%.2f"
            ),
            "status": st.column_config.TextColumn("Recorded status"),
            "issue_type": st.column_config.TextColumn("Exception"),
        },
    )

st.divider()
st.caption(
    "Slimes.Hustlers AI Solutions | Smart AI. Smarter Business. "
    "| Read-only reporting preview"
)
