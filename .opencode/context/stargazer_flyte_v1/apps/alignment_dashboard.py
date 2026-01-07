import time
import streamlit as st
import streamlit.components.v1 as components
from streamlit import session_state as session
from flytekit.configuration import Config
from flytekit.remote import FlyteRemote
from unionbio.workflows.compare_aligners import alignment_wf
#####################################################
# PYTHONPATH=. streamlit run alignment_dashboard.py #
#####################################################


st.set_page_config(
    page_title="fastq alignment",
    page_icon="https://docs.flyte.org/en/latest/_static/flyte_circle_gradient_1_4x4.png",
)


def gate_node_approval(execution):
    if session.qc_check:
        remote.set_signal("filter-approval", execution.id.name, True)
        while True:
            synced_execution = remote.sync_execution(execution, sync_nodes=True)
            try:
                uri = remote.client.get_download_signed_url(
                    native_url=synced_execution.node_executions["n9"].closure.deck_uri
                )
                break
            except Exception:
                pass
            time.sleep(10)

        st.write("Final MultiQC report:")
        components.iframe(uri.signed_url, scrolling=True, height=1000, width=1000)
    else:
        st.write("Not proceeding with the execution of the workflow.")


def samples():
    execution = remote.execute(alignment_wf, inputs={"seq_dir": session.seq_dir})
    while True:
        synced_execution = remote.sync_execution(execution, sync_nodes=True)
        try:
            uri = remote.client.get_download_signed_url(
                native_url=synced_execution.node_executions["n4"].closure.deck_uri
            )
            break
        except Exception:
            pass
        time.sleep(10)

    components.iframe(uri.signed_url, scrolling=True, height=1000, width=1000)

    user_input_form = st.form(key="user_input_form")
    with user_input_form:
        st.checkbox("Does the MultiQC report look satisfactory to you?", key="qc_check")
        user_input_form.form_submit_button(
            "Submit", on_click=gate_node_approval, args=(execution,)
        )


def data_uploader_form():
    fastq_alignment_form = st.form(key="fastq_alignment_form")
    with fastq_alignment_form:
        st.text_input(
            label="What's the location at which the sequencing data is stored?",
            value="",
            key="seq_dir",
        )
        fastq_alignment_form.form_submit_button(label="Submit", on_click=samples)


if __name__ == "__main__":
    remote = FlyteRemote(
        config=Config.for_sandbox(),
        default_project="flytesnacks",
        default_domain="development",
    )
    data_uploader_form()
