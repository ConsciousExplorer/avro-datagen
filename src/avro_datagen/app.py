"""Streamlit UI for the data-generator Kafka producer."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from avro_datagen.generator import generate
from avro_datagen.resolver import RecordResolver

# ── Load .env ────────────────────────────────────────────────────────
load_dotenv()

KAFKA_ENABLED = os.getenv("AVRO_DATAGEN_KAFKA", "0") == "1"

_PKG_DIR = Path(__file__).parent
_BUNDLED_SCHEMAS = _PKG_DIR / "schemas"

# Use env var if set, then local ./schemas, then bundled package schemas
_schema_env = os.getenv("SCHEMA_DIR")
if _schema_env:
    SCHEMA_DIR = Path(_schema_env)
elif Path("schemas").is_dir():
    SCHEMA_DIR = Path("schemas")
else:
    SCHEMA_DIR = _BUNDLED_SCHEMAS

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Generator",
    page_icon=":material/database:",
    layout="centered",
    initial_sidebar_state="expanded" if KAFKA_ENABLED else "collapsed",
)

# ── Styling ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    #MainMenu, footer, .stDeployButton { display: none; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #f0f2f6;
    }
    section[data-testid="stSidebar"] [data-testid="stSubheader"] {
        color: #0ea5a0;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #f0f2f6;
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: #64748b; }
    [data-testid="stMetricValue"] { color: #2c3e50; }

    /* Tabs */
    .stTabs [data-baseweb="tab-highlight"] { background-color: #0ea5a0; }
    .stTabs [aria-selected="true"] { color: #0ea5a0; }

    /* Divider */
    hr { border-color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ───────────────────────────────────────────
def _init_state():
    defaults = {
        "producing": False,
        "produced_count": 0,
        "error_count": 0,
        "elapsed_s": 0.0,
        "preview_records": [],
        "log_lines": [],
        "stop_requested": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── Header ───────────────────────────────────────────────────────────
st.title("Data Generator")
st.caption("Schema-driven fake data to Kafka")


# ── Sidebar: Kafka connection (only when --kafka) ──────────────────
if KAFKA_ENABLED:
    with st.sidebar:
        st.subheader("Connection")

        bootstrap_servers = st.text_input(
            "Bootstrap servers",
            value=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        )
        topic = st.text_input(
            "Topic",
            value=os.getenv("KAFKA_TOPIC", "transactions"),
        )

        st.subheader("Authentication")

        security_protocol = st.selectbox(
            "Security protocol",
            ["", "PLAINTEXT", "SASL_PLAINTEXT", "SSL", "SASL_SSL"],
            index=["", "PLAINTEXT", "SASL_PLAINTEXT", "SSL", "SASL_SSL"].index(
                os.getenv("KAFKA_SECURITY_PROTOCOL", "")
            ),
        )
        sasl_mechanism = st.selectbox(
            "SASL mechanism",
            ["", "PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"],
            index=["", "PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"].index(
                os.getenv("KAFKA_SASL_MECHANISM", "")
            ),
        )
        sasl_username = st.text_input(
            "Username",
            value=os.getenv("KAFKA_SASL_USERNAME", ""),
        )
        sasl_password = st.text_input(
            "Password",
            value=os.getenv("KAFKA_SASL_PASSWORD", ""),
            type="password",
        )

        st.subheader("Tuning")

        acks = st.selectbox("Acks", ["all", "0", "1"], index=0)
        linger_ms = st.number_input(
            "Linger (ms)", value=int(os.getenv("KAFKA_LINGER_MS", "5")), min_value=0,
        )
        batch_size = st.number_input(
            "Batch size", value=int(os.getenv("KAFKA_BATCH_SIZE", "16384")), min_value=1,
        )
        compression = st.selectbox(
            "Compression", ["none", "gzip", "snappy", "lz4", "zstd"], index=2,
        )


# ── Helpers ──────────────────────────────────────────────────────────
def _schema_to_tmp(schema_dict):
    """Write schema dict to a temp .avsc file and return its Path."""
    with tempfile.NamedTemporaryFile(suffix=".avsc", delete=False, mode="w") as tmp:
        json.dump(schema_dict, tmp)
        tmp.flush()
        return Path(tmp.name)


# ── Sample helper ────────────────────────────────────────────────────
def _show_sample(schema):
    """Try to generate and display one sample record from a schema dict."""
    try:
        resolver = RecordResolver(schema)
        sample = resolver.generate()
        st.caption("Sample record")
        st.json(sample)
    except Exception as e:
        st.error(f"Could not generate sample: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 1. SCHEMA
# ═══════════════════════════════════════════════════════════════════════
st.subheader("Schema")

schema_path = None
schema_dict = None
edited_schema = None

tab_local, tab_upload, tab_editor = st.tabs(["Local schemas", "Upload", "Editor"])

# ── Tab 1: Local schemas ─────────────────────────────────────────────
with tab_local:
    avsc_files = sorted(SCHEMA_DIR.glob("*.avsc")) if SCHEMA_DIR.is_dir() else []
    if not avsc_files:
        st.info(f"No `.avsc` files in `{SCHEMA_DIR}/`")
    else:
        selected = st.selectbox(
            "Schema file",
            avsc_files,
            format_func=lambda p: p.name,
        )
        schema_path = selected
        with open(selected) as f:
            schema_dict = json.load(f)

        with st.expander("Schema JSON"):
            st.json(schema_dict)

        _show_sample(schema_dict)

# ── Tab 2: Upload ────────────────────────────────────────────────────
with tab_upload:
    uploaded = st.file_uploader(
        "Drop an `.avsc` or `.json` file",
        type=["avsc", "json"],
    )
    if uploaded:
        raw = uploaded.read().decode("utf-8")
        upload_dict = json.loads(raw)
        schema_dict = upload_dict
        schema_path = _schema_to_tmp(upload_dict)

        with st.expander("Schema JSON"):
            st.json(upload_dict)

        _show_sample(upload_dict)

# ── Tab 3: Interactive editor ────────────────────────────────────────
with tab_editor:
    # Sync editor contents when a different schema is selected / uploaded
    if schema_dict:
        source_key = str(schema_path)
        if st.session_state.get("_editor_source") != source_key:
            st.session_state._editor_source = source_key
            # Write directly to the widget key so Streamlit picks it up
            st.session_state.schema_editor = json.dumps(schema_dict, indent=2)

    default_text = '{\n  "type": "record",\n  "name": "Example",\n  "fields": []\n}'

    schema_text = st.text_area(
        "Schema JSON",
        value=default_text,
        height=400,
        key="schema_editor",
    )

    # Parse and validate first so buttons know if schema is valid
    editor_valid = False
    try:
        parsed = json.loads(schema_text)
        if "fields" not in parsed or "type" not in parsed:
            st.warning("Valid JSON but not an Avro record schema (missing `type` or `fields`).")
        else:
            editor_valid = True
            edited_schema = parsed
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
    except Exception as e:
        st.error(f"Schema error: {e}")

    # Action buttons
    col_save, col_download, col_reset, _ = st.columns([1, 1, 1, 1])
    with col_save:
        can_save = editor_valid and schema_path and SCHEMA_DIR.is_dir()
        if st.button(
            "Save to file", use_container_width=True, type="primary", disabled=not can_save
        ):
            # Pretty-print before saving
            formatted = json.dumps(parsed, indent=2) + "\n"
            # Save to the original path if it's a local schema, otherwise into schemas/
            save_path = schema_path
            if not str(save_path).startswith(str(SCHEMA_DIR)):
                name = parsed.get("name", "custom").lower() + ".avsc"
                save_path = SCHEMA_DIR / name
            with open(save_path, "w") as f:
                f.write(formatted)
            st.toast(f"Saved to `{save_path.name}`", icon=":material/save:")
    with col_download:
        if editor_valid:
            name = parsed.get("name", "schema").lower() + ".avsc"
            st.download_button(
                "Download",
                data=json.dumps(parsed, indent=2),
                file_name=name,
                mime="application/json",
                use_container_width=True,
            )
    with col_reset:
        if schema_dict and st.button("Reset", use_container_width=True):
            st.session_state.schema_editor = json.dumps(schema_dict, indent=2)
            st.rerun()

    # Render sample
    if editor_valid:
        field_count = len(parsed.get("fields", []))
        st.caption(f"`{parsed.get('name', 'unknown')}` -- {field_count} fields")
        _show_sample(parsed)

st.divider()

# ═══════════════════════════════════════════════════════════════════════
# 3. GENERATE (streaming)
# ═══════════════════════════════════════════════════════════════════════
st.subheader("Generate")

col_count, col_rate, col_seed = st.columns(3)

with col_count:
    count = st.number_input(
        "Records", value=100, min_value=0, step=10,
        help="0 = infinite (use Stop button)",
    )
with col_rate:
    rate = st.number_input(
        "Rate (rec/s)", value=0.0, min_value=0.0, step=1.0,
        help="0 = no limit",
    )
with col_seed:
    seed = st.number_input(
        "Seed", value=0, min_value=0, step=1,
        help="0 = random each run",
    )

effective_rate = rate if rate > 0 else None
effective_seed = seed if seed > 0 else None

gen_schema = edited_schema or schema_dict

if schema_path and gen_schema:
    gen_count = min(count, 500) if count > 0 else 50

    if st.button("Generate", use_container_width=True, type="primary"):
        gen_path = _schema_to_tmp(gen_schema)
        metrics_ph = st.empty()
        table_ph = st.empty()

        records = []
        start_t = time.time()
        delay = (1.0 / effective_rate) if effective_rate else 0
        # Batch UI updates: refresh every N records or 150ms
        last_render = start_t

        for i, record in enumerate(generate(str(gen_path), count=gen_count, seed=effective_seed)):
            records.append(record)
            now = time.time()
            elapsed = now - start_t
            is_last = (i + 1) == gen_count

            if is_last or (now - last_render) >= 0.15:
                actual_rate = (i + 1) / elapsed if elapsed > 0 else 0
                with metrics_ph.container():
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Records", f"{i + 1:,} / {gen_count:,}")
                    m2.metric("Rate", f"{actual_rate:,.0f} rec/s")
                    m3.metric("Elapsed", f"{elapsed:.2f}s")
                table_ph.dataframe(records, use_container_width=True, hide_index=True)
                last_render = now

            if delay:
                time.sleep(delay)

        os.unlink(gen_path)

st.divider()

# ═══════════════════════════════════════════════════════════════════════
# 4. KAFKA PRODUCE (only with --kafka flag)
# ═══════════════════════════════════════════════════════════════════════
if KAFKA_ENABLED:
    from avro_datagen.producer import build_producer_config, produce

    st.subheader("Kafka Produce")

    target_label = f"`{bootstrap_servers}` / `{topic}`"
    if security_protocol:
        target_label += f" -- {security_protocol}"
    st.caption(f"Target: {target_label}")

    def _run_producer():
        """Background thread that produces to Kafka."""
        produce_schema = edited_schema or schema_dict
        produce_path = _schema_to_tmp(produce_schema) if produce_schema else schema_path

        config = build_producer_config(
            bootstrap_servers=bootstrap_servers,
            security_protocol=security_protocol,
            sasl_mechanism=sasl_mechanism,
            sasl_username=sasl_username,
            sasl_password=sasl_password,
            acks=acks,
            linger_ms=int(linger_ms),
            batch_size=int(batch_size),
            compression_type=compression,
        )

        effective_count = count if not st.session_state.stop_requested else 0

        def _on_progress(i, record):
            st.session_state.produced_count = i + 1
            if st.session_state.stop_requested:
                raise KeyboardInterrupt

        try:
            result = produce(
                schema_path=str(produce_path),
                topic=topic,
                producer_config=config,
                count=effective_count,
                rate=effective_rate,
                seed=effective_seed,
                on_progress=_on_progress,
            )
            st.session_state.error_count = result["errors"]
            st.session_state.elapsed_s = result["elapsed_s"]
            st.session_state.log_lines.append(
                f"Done -- {result['produced']} produced, "
                f"{result['errors']} errors, {result['elapsed_s']:.1f}s"
            )
        except Exception as e:
            st.session_state.log_lines.append(f"Error: {e}")
        finally:
            st.session_state.producing = False

    col_produce, col_stop = st.columns(2)

    with col_produce:
        start_disabled = schema_path is None or st.session_state.producing
        if st.button(
            "Produce to Kafka",
            disabled=start_disabled,
            type="primary",
            use_container_width=True,
        ):
            st.session_state.producing = True
            st.session_state.produced_count = 0
            st.session_state.error_count = 0
            st.session_state.elapsed_s = 0.0
            st.session_state.stop_requested = False
            st.session_state.log_lines = []
            thread = threading.Thread(target=_run_producer, daemon=True)
            thread.start()
            st.rerun()

    with col_stop:
        if st.button(
            "Stop",
            disabled=not st.session_state.producing,
            use_container_width=True,
        ):
            st.session_state.stop_requested = True
            st.rerun()

    # ── Live metrics ─────────────────────────────────────────────────
    if st.session_state.producing or st.session_state.produced_count > 0:
        if st.session_state.producing:
            st.info("Producing...", icon=":material/sync:")

        m1, m2, m3 = st.columns(3)
        m1.metric("Sent", f"{st.session_state.produced_count:,}")
        m2.metric("Errors", f"{st.session_state.error_count:,}")
        m3.metric("Elapsed", f"{st.session_state.elapsed_s:.1f}s")

        if st.session_state.producing:
            time.sleep(0.5)
            st.rerun()

    if st.session_state.log_lines:
        for line in st.session_state.log_lines:
            st.success(line, icon=":material/check_circle:")
