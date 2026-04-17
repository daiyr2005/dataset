import streamlit as st
from audio_recorder_streamlit import audio_recorder
import zipfile
import io
import os
import uuid
import shutil

TARGET = 100

# ───── DATASET DIR ─────
if "dataset_dir" not in st.session_state:
    st.session_state["dataset_dir"] = "dataset"

DATASET_DIR = st.session_state["dataset_dir"]
os.makedirs(DATASET_DIR, exist_ok=True)

st.title("🗂️ Сбор аудио датасета")

# ───── ПЕРЕКЛЮЧЕНИЕ ДАТАСЕТА ─────
all_datasets = [d for d in os.listdir(".") if os.path.isdir(d) and not d.startswith(".")]

col1, col2 = st.columns([2, 1])
with col1:
    selected = st.selectbox(
        "📁 Текущий датасет",
        all_datasets,
        index=all_datasets.index(DATASET_DIR) if DATASET_DIR in all_datasets else 0
    )
    if selected != DATASET_DIR:
        st.session_state["dataset_dir"] = selected
        st.rerun()

with col2:
    st.metric("Активный", DATASET_DIR)

st.divider()

# ───── СОЗДАТЬ ДАТАСЕТ ─────
st.subheader("🆕 Создать новый датасет")

new_name = st.text_input("Название нового датасета")

if st.button("🆕 Создать"):
    if new_name.strip():
        new_dir = new_name.strip().lower().replace(" ", "_")
        os.makedirs(new_dir, exist_ok=True)
        st.session_state["dataset_dir"] = new_dir
        st.success(f"Создан: {new_dir}")
        st.rerun()
    else:
        st.error("Введи название")

st.divider()

# ───── FUNCTIONS ─────
def get_stats():
    stats = {}
    for cls in os.listdir(DATASET_DIR):
        path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(path):
            stats[cls] = len(os.listdir(path))
    return stats


def save_audio(file_bytes, class_name):
    class_name = class_name.strip().lower().replace(" ", "_")
    class_dir = os.path.join(DATASET_DIR, class_name)
    os.makedirs(class_dir, exist_ok=True)

    filename = f"{uuid.uuid4()}.wav"
    path = os.path.join(class_dir, filename)

    with open(path, "wb") as f:
        f.write(file_bytes)

    return class_name, filename


# ───── STATS ─────
with st.expander("📊 Статистика", expanded=True):
    stats = get_stats()
    if stats:
        cols = st.columns(len(stats))
        for col, (cls, cnt) in zip(cols, stats.items()):
            pct = min(cnt / TARGET, 1.0)
            col.metric(cls, f"{cnt}/{TARGET}")
            col.progress(pct)
    else:
        st.info("Пусто")

st.divider()

# ───── RECORD ─────
st.subheader("🎙️ Запись")

class_name = st.text_input("Класс", key="class_input")

if class_name.strip():
    current = get_stats().get(class_name.strip().lower().replace(" ", "_"), 0)
    st.caption(f"{current}/{TARGET}")

audio_bytes = audio_recorder(
    text="Нажми для записи",
    recording_color="#e74c3c",
    neutral_color="#3498db",
)

# ✅ ВОТ ТУТ ДОБАВЛЕНО СКАЧИВАНИЕ
if audio_bytes and len(audio_bytes) > 0:
    st.audio(audio_bytes, format="audio/wav")

    st.download_button(
        label="⬇️ Скачать аудио",
        data=audio_bytes,
        file_name=f"{uuid.uuid4()}.wav",
        mime="audio/wav"
    )

    if st.button("💾 Сохранить"):
        if not class_name.strip():
            st.error("Введи класс")
        else:
            cls, fname = save_audio(audio_bytes, class_name)
            st.success(f"Сохранено: {cls}/{fname}")
            st.rerun()

# ───── UPLOAD ─────
st.divider()
st.subheader("📂 Загрузка файла")

uploaded = st.file_uploader("WAV", type=["wav"])
upload_class = st.text_input("Класс файла")

if uploaded and st.button("Сохранить файл"):
    if upload_class.strip():
        data = uploaded.read()
        cls, fname = save_audio(data, upload_class)
        st.success(f"{cls}/{fname}")
        st.rerun()
    else:
        st.error("Введи класс")

# ───── ZIP IMPORT ─────
st.divider()
st.subheader("📥 Импорт ZIP")

uploaded_zip = st.file_uploader("ZIP", type=["zip"])

if uploaded_zip and st.button("Импорт"):
    imported = 0
    with zipfile.ZipFile(io.BytesIO(uploaded_zip.read())) as zf:
        for name in zf.namelist():
            parts = name.strip("/").split("/")
            if len(parts) == 2:
                cls, file = parts
                if file.endswith(".wav"):
                    cls_dir = os.path.join(DATASET_DIR, cls)
                    os.makedirs(cls_dir, exist_ok=True)
                    path = os.path.join(cls_dir, f"{uuid.uuid4()}.wav")
                    with zf.open(name) as src, open(path, "wb") as dst:
                        dst.write(src.read())
                    imported += 1

    st.success(f"Импортировано: {imported}")
    st.rerun()

# ───── ZIP DOWNLOAD ─────
st.divider()
st.subheader("📦 Скачать всё")

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w") as zf:
    for cls in os.listdir(DATASET_DIR):
        cls_path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(cls_path):
            for file in os.listdir(cls_path):
                zf.write(os.path.join(cls_path, file), f"{cls}/{file}")

zip_buffer.seek(0)

st.download_button(
    "⬇️ Скачать dataset.zip",
    data=zip_buffer.getvalue(),
    file_name="dataset.zip"
)