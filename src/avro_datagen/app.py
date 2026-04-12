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

# Save directory is always in the working directory, never inside the package
SAVE_DIR = Path(os.getenv("SCHEMA_DIR", "schemas"))


def _get_schema_dir() -> Path:
    """Resolve schema directory dynamically on each run.

    Checks: env var → local ./schemas/ → bundled package schemas.
    Re-evaluated on every Streamlit rerun so saving a schema to ./schemas/
    switches the UI away from bundled examples automatically.
    """
    env = os.getenv("SCHEMA_DIR")
    if env:
        return Path(env)
    if Path("schemas").is_dir():
        return Path("schemas")
    return _BUNDLED_SCHEMAS


# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Generator",
    page_icon=":material/database:",
    layout="wide",
    initial_sidebar_state="expanded" if KAFKA_ENABLED else "collapsed",
)

# ── Styling ──────────────────────────────────────────────────────────
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


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
        "_stop_event": threading.Event(),
        "_thread_state": {
            "produced_count": 0,
            "error_count": 0,
            "elapsed_s": 0.0,
            "log_lines": [],
            "producing": False,
        },
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── Header ───────────────────────────────────────────────────────────
st.title("📝 avro-datagen")
st.caption(
    " Avro schema data generation tool. \n\n"
    "[Docs](https://consciousexplorer.github.io/avro-datagen/) | "
    "[Schema guide](https://consciousexplorer.github.io/avro-datagen/schemas/writing-schemas/) | "
    "[Examples](https://consciousexplorer.github.io/avro-datagen/schemas/examples/)"
)


# ── Sidebar: Kafka connection (only when --kafka) ──────────────────
rate = 0.0
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
            "Linger (ms)",
            value=int(os.getenv("KAFKA_LINGER_MS", "5")),
            min_value=0,
        )
        batch_size = st.number_input(
            "Batch size",
            value=int(os.getenv("KAFKA_BATCH_SIZE", "16384")),
            min_value=1,
        )
        compression = st.selectbox(
            "Compression",
            ["none", "gzip", "snappy", "lz4", "zstd"],
            index=2,
        )

        st.subheader("Rate limit")
        rate = st.number_input(
            "Rate (rec/s)",
            value=0.0,
            min_value=0.0,
            step=1.0,
            help="0 = no limit",
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
    _schema_dir = _get_schema_dir()
    avsc_files = sorted(_schema_dir.glob("*.avsc")) if _schema_dir.is_dir() else []
    if not avsc_files:
        st.info(f"No `.avsc` files in `{_schema_dir}/`")
    else:
        selected = st.selectbox(
            "Schema file",
            avsc_files,
            format_func=lambda p: p.name,
        )
        schema_path = selected
        with open(selected) as f:
            schema_dict = json.load(f)

        col_schema, col_sample = st.columns(2, gap="large")
        with col_schema, st.expander("Schema JSON", expanded=False):
            st.json(schema_dict)
        with col_sample:
            _show_sample(schema_dict)

# ── Tab 2: Upload ────────────────────────────────────────────────────
with tab_upload:
    uploaded = st.file_uploader(
        "Drop an `.avsc` or `.json` file",
        type=["avsc", "json"],
        accept_multiple_files=False,
    )
    if uploaded:
        raw = uploaded.read().decode("utf-8")
        upload_dict = json.loads(raw)
        schema_dict = upload_dict
        schema_path = _schema_to_tmp(upload_dict)
        default_fn = uploaded.name if hasattr(uploaded, "name") else "uploaded_schema.avsc"

        # Filename + Upload button at the top (mirrors editor tab layout)
        col_fn, col_upload_btn = st.columns([3, 1])
        with col_fn:
            save_filename_upload = st.text_input(
                "Filename",
                value=default_fn,
                key="save_filename_upload",
                label_visibility="collapsed",
                placeholder="filename.avsc",
            )
        with col_upload_btn:
            if st.button("Upload", use_container_width=True, type="primary", key="save_upload_btn"):
                fn = save_filename_upload.strip() or "uploaded_schema.avsc"
                if not fn.endswith(".avsc"):
                    fn += ".avsc"
                SAVE_DIR.mkdir(parents=True, exist_ok=True)
                save_path = SAVE_DIR / fn
                formatted = json.dumps(upload_dict, indent=2) + "\n"
                with open(save_path, "w") as f:
                    f.write(formatted)
                st.toast(f"Saved to `{save_path}`", icon=":material/save:")

        col_schema, col_sample = st.columns(2, gap="large")
        with col_schema, st.expander("Schema JSON", expanded=False):
            st.json(upload_dict)
        with col_sample:
            _show_sample(upload_dict)

        # Set the editor's filename to the uploaded file's name for next tab
        st.session_state.save_filename = default_fn

# ── Tab 3: Interactive editor ────────────────────────────────────────
with tab_editor:
    # Sync editor contents when a different schema is selected / uploaded
    if schema_dict:
        source_key = str(schema_path)
        if st.session_state.get("_editor_source") != source_key:
            st.session_state._editor_source = source_key
            st.session_state.schema_editor = json.dumps(schema_dict, indent=2)
            # Prefer uploaded filename if set in session, else fallback
            if st.session_state.get("save_filename"):
                pass  # already set by upload tab
            elif schema_path and hasattr(schema_path, "name"):
                st.session_state.save_filename = schema_path.name
            else:
                st.session_state.save_filename = schema_dict.get("name", "custom").lower() + ".avsc"

    default_text = '{\n  "type": "record",\n  "name": "Example",\n  "fields": []\n}'

    # Filename + action buttons at the top (full-width, matches other tabs)
    col_fn, col_save, col_reset = st.columns([3, 1, 1])
    default_fn = st.session_state.get("save_filename", "schema.avsc")
    with col_fn:
        save_filename = st.text_input(
            "Filename",
            value=default_fn,
            label_visibility="collapsed",
            placeholder="filename.avsc",
        )
    with col_save:
        if st.button(
            "Save to file",
            use_container_width=True,
            type="primary",
            disabled=not st.session_state.get("schema_editor", ""),
            key="save_editor_btn",
        ):
            try:
                parsed = json.loads(st.session_state.schema_editor)
                fn = save_filename.strip() or "schema.avsc"
                if not fn.endswith(".avsc"):
                    fn += ".avsc"
                SAVE_DIR.mkdir(parents=True, exist_ok=True)
                save_path = SAVE_DIR / fn
                formatted = json.dumps(parsed, indent=2) + "\n"
                with open(save_path, "w") as f:
                    f.write(formatted)
                st.session_state.save_filename = fn
                st.toast(f"Saved to `{save_path}`", icon=":material/save:")
            except Exception as e:
                st.error(f"Could not save: {e}")
    with col_reset:
        if st.button("Reset", use_container_width=True, key="reset_editor_btn") and schema_dict:
            st.session_state.schema_editor = json.dumps(schema_dict, indent=2)
            st.rerun()

    # Two columns below: editor on left, preview on right
    col_edit, col_preview = st.columns(2, gap="large")

    with col_edit:
        st.caption("Schema JSON")
        schema_text = st.text_area(
            "Schema JSON",
            value=default_text,
            height=500,
            key="schema_editor",
            label_visibility="collapsed",
        )

    # Parse and validate
    editor_valid = False
    parsed = None
    try:
        parsed = json.loads(st.session_state.schema_editor)
        if "fields" not in parsed or "type" not in parsed:
            with col_preview:
                st.warning("Valid JSON but not an Avro record schema.")
        else:
            editor_valid = True
            edited_schema = parsed
    except json.JSONDecodeError as e:
        with col_preview:
            st.error(f"Invalid JSON: {e}")
    except Exception as e:
        with col_preview:
            st.error(f"Schema error: {e}")

    with col_preview:
        if editor_valid and parsed:
            field_count = len(parsed.get("fields", []))
            st.caption(f"`{parsed.get('name', 'unknown')}` -- {field_count} fields")
            _show_sample(parsed)
            fn_preview = save_filename.strip() if save_filename else "schema.avsc"
            if not fn_preview.endswith(".avsc"):
                fn_preview += ".avsc"
            st.download_button(
                "Download",
                data=json.dumps(parsed, indent=2),
                file_name=fn_preview,
                mime="application/json",
                use_container_width=True,
            )

st.divider()

# ═══════════════════════════════════════════════════════════════════════
# 3. GENERATE (streaming)
# ═══════════════════════════════════════════════════════════════════════
st.subheader("Generate")

col_count, col_seed = st.columns(2)

with col_count:
    count = st.number_input(
        "Records",
        value=100,
        min_value=0,
        step=10,
        help="0 = infinite (use Stop button)",
    )
with col_seed:
    seed = st.number_input(
        "Seed",
        value=0,
        min_value=0,
        step=1,
        help="0 = random each run",
    )

effective_rate = rate if rate > 0 else None
effective_seed = seed if seed > 0 else None

gen_schema = edited_schema or schema_dict

if schema_path and gen_schema:
    gen_count = min(count, 500) if count > 0 else 50

    if st.button("Generate", use_container_width=True, type="primary"):
        gen_path = _schema_to_tmp(gen_schema)

        start_t = time.time()
        records = list(generate(str(gen_path), count=gen_count, seed=effective_seed))
        elapsed = time.time() - start_t
        actual_rate = len(records) / elapsed if elapsed > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Records", f"{len(records):,} / {gen_count:,}")
        m2.metric("Rate", f"{actual_rate:,.0f} rec/s")
        m3.metric("Elapsed", f"{elapsed:.2f}s")
        st.dataframe(records, use_container_width=True, hide_index=True)

        os.unlink(gen_path)

# ═══════════════════════════════════════════════════════════════════════
# 4. FIELD RESOLUTION EXPLAINER
# ═══════════════════════════════════════════════════════════════════════
if schema_dict:
    with st.expander("How fields are resolved", icon=":material/schema:"):
        st.caption(
            "Shows the resolution path the generator takes for each field "
            "in the current schema. Fields are resolved top-to-bottom — "
            "later fields can reference earlier ones."
        )

        def _describe_type(avro_type):
            """Return a short human-readable type label."""
            if isinstance(avro_type, str):
                return avro_type
            if isinstance(avro_type, list):
                return "union: " + " | ".join(_describe_type(b) for b in avro_type)
            if isinstance(avro_type, dict):
                logical = avro_type.get("logicalType")
                inner = avro_type.get("type", "")
                if logical:
                    return f"{inner} ({logical})"
                if inner == "array":
                    return f"array<{_describe_type(avro_type.get('items', '?'))}>"
                if inner == "map":
                    return f"map<string, {_describe_type(avro_type.get('values', '?'))}>"
                if inner == "enum":
                    symbols = avro_type.get("symbols", [])
                    preview = ", ".join(symbols[:4])
                    suffix = "..." if len(symbols) > 4 else ""
                    return f"enum({preview}{suffix})"
                if inner == "record":
                    return f"record({avro_type.get('name', '?')})"
                if inner == "fixed":
                    return f"fixed({avro_type.get('size', '?')})"
                return inner
            return str(avro_type)

        def _describe_resolution(field):
            """Return (priority, path_description) for a field."""
            props = field.get("arg.properties", {})
            avro_type = field.get("type", "string")

            if "rules" in props:
                conditions = []
                last_then = None
                op_labels = {
                    "equals": "=",
                    "not_equals": "!=",
                    "gt": ">",
                    "gte": ">=",
                    "lt": "<",
                    "lte": "<=",
                }
                for rule in props["rules"]:
                    cond = rule.get("when", {})
                    ref_field = cond.get("field", "?")
                    matched = False
                    for op, label in op_labels.items():
                        if op in cond:
                            conditions.append(f"{ref_field} {label} {cond[op]!r}")
                            matched = True
                            break
                    if not matched:
                        if "in" in cond:
                            conditions.append(f"{ref_field} in {cond['in']}")
                        elif "not_in" in cond:
                            conditions.append(f"{ref_field} not in {cond['not_in']}")
                        elif "is_null" in cond:
                            null_str = "null" if cond["is_null"] else "not null"
                            conditions.append(f"{ref_field} is {null_str}")
                        elif "matches" in cond:
                            conditions.append(f"{ref_field} matches /{cond['matches']}/")
                    last_then = rule.get("then")
                if last_then is None:
                    hint = "null"
                elif isinstance(last_then, dict):
                    hint = ", ".join(last_then.keys())
                else:
                    hint = repr(last_then)
                return "1. rules", f"conditions: {'; '.join(conditions)} -> {hint}"

            if "ref" in props:
                target_logical = None
                if isinstance(avro_type, dict):
                    target_logical = avro_type.get("logicalType")
                conversion = ""
                if target_logical == "iso-timestamp":
                    conversion = " (epoch ms -> ISO string)"
                return "2. ref", f'copy from "{props["ref"]}"{conversion}'

            if props:
                hints_used = []
                if "template" in props:
                    hints_used.append(f'template: "{props["template"]}"')
                if "faker" in props:
                    spec = props["faker"]
                    if isinstance(spec, str):
                        hints_used.append(f"faker: {spec}")
                    else:
                        hints_used.append(f"faker: {spec.get('method', '?')}")
                if "options" in props:
                    opts = props["options"]
                    preview = ", ".join(str(o) for o in opts[:4])
                    if len(opts) > 4:
                        preview += f", ... ({len(opts)} total)"
                    hints_used.append(f"options: [{preview}]")
                if "pool" in props:
                    hints_used.append(f"pool: {props['pool']} unique values")
                if "range" in props:
                    r = props["range"]
                    hints_used.append(f"range: {r.get('min')} to {r.get('max')}")
                if "pattern" in props:
                    hints_used.append(f'pattern: "{props["pattern"]}"')
                if "null_probability" in props:
                    hints_used.append(f"null_probability: {props['null_probability']}")
                if "length" in props:
                    hints_used.append(f"length: {props['length']}")
                if hints_used:
                    return "3. hints", "; ".join(hints_used)

            if "default" in field:
                return "4. default", f"value: {field['default']!r}"

            return "5. type", f"generate from {_describe_type(avro_type)}"

        rows = []
        for i, field in enumerate(schema_dict.get("fields", []), 1):
            priority, description = _describe_resolution(field)
            rows.append(
                {
                    "#": i,
                    "Field": field["name"],
                    "Type": _describe_type(field.get("type", "?")),
                    "Priority": priority,
                    "Resolution": description,
                }
            )

        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.caption(
            "**Priority order:** 1. rules -> 2. ref -> 3. arg.properties hints "
            "(template > faker > options > pool > range > pattern) -> 4. default -> 5. type"
        )

st.divider()

# ═══════════════════════════════════════════════════════════════════════
# 5. KAFKA PRODUCE (only with --kafka flag)
# ═══════════════════════════════════════════════════════════════════════
if KAFKA_ENABLED:
    from avro_datagen.producer import build_producer_config, produce

    st.subheader("Kafka Produce")

    target_label = f"`{bootstrap_servers}` / `{topic}`"
    if security_protocol:
        target_label += f" -- {security_protocol}"
    st.caption(f"Target: {target_label}")

    # Grab thread-safe shared objects from session state.
    # These persist across Streamlit reruns so the background thread
    # and the main thread always reference the same objects.
    _stop_event: threading.Event = st.session_state._stop_event
    _thread_state: dict = st.session_state._thread_state

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

        effective_count = count if not _stop_event.is_set() else 0

        def _on_progress(i, _record):
            _thread_state["produced_count"] = i + 1
            if _stop_event.is_set():
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
            _thread_state["error_count"] = result["errors"]
            _thread_state["elapsed_s"] = result["elapsed_s"]
            _thread_state["log_lines"].append(
                f"Done -- {result['produced']} produced, "
                f"{result['errors']} errors, {result['elapsed_s']:.1f}s"
            )
        except Exception as e:
            _thread_state["log_lines"].append(f"Error: {e}")
        finally:
            _thread_state["producing"] = False

    # ── Sync thread state back into session state ────────────────────
    # Must run before buttons so they see the up-to-date producing flag.
    st.session_state.produced_count = _thread_state["produced_count"]
    st.session_state.error_count = _thread_state["error_count"]
    st.session_state.elapsed_s = _thread_state["elapsed_s"]
    if _thread_state["log_lines"]:
        st.session_state.log_lines = list(_thread_state["log_lines"])
    if not _thread_state["producing"]:
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
            _stop_event.clear()
            _thread_state.update(
                produced_count=0, error_count=0, elapsed_s=0.0, producing=True, log_lines=[]
            )
            thread = threading.Thread(target=_run_producer, daemon=True)
            thread.start()
            st.rerun()

    with col_stop:
        if st.button(
            "Stop",
            disabled=not st.session_state.producing,
            use_container_width=True,
        ):
            _stop_event.set()
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
            if line.startswith("Error:"):
                st.error(line, icon=":material/error:")
            elif st.session_state.error_count > 0:
                st.warning(line, icon=":material/warning:")
            else:
                st.success(line, icon=":material/check_circle:")
