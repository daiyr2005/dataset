import streamlit as st
import zipfile
import io
import os
import uuid
from audio_recorder_streamlit import audio_recorder

DATASET_DIR = "dataset"
TARGET = 100

os.makedirs(DATASET_DIR, exist_ok=True)

st.title("🗂️ Сбор аудио датасета (FULL STREAMLIT)")

# ───── STATS ─────
def get_stats():
    stats = {}
    for cls in os.listdir(DATASET_DIR):
        path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(path):
            stats[cls] = len(os.listdir(path))
    return stats


# ───── SAVE AUDIO ─────
def save_audio(file_bytes, class_name):
    class_name = class_name.strip().lower().replace(" ", "_")
    class_dir = os.path.join(DATASET_DIR, class_name)
    os.makedirs(class_dir, exist_ok=True)

    filename = f"{uuid.uuid4()}.wav"
    path = os.path.join(class_dir, filename)

    with open(path, "wb") as f:
        f.write(file_bytes)

    return class_name, filename


# ───── UI STATS ─────
with st.expander("📊 Статистика датасета", expanded=True):
    stats = get_stats()
    if stats:
        cols = st.columns(len(stats))
        for col, (cls, cnt) in zip(cols, stats.items()):
            pct = min(cnt / TARGET, 1.0)
            col.metric(cls, f"{cnt} / {TARGET}")
            col.progress(pct)
    else:
        st.info("Датасет пуст — начни запись!")


st.divider()

# ───── RECORD ─────
st.subheader("🎙️ Запись нового примера")

class_name = st.text_input("Название класса", key="class_input")

audio_bytes = audio_recorder(
    text="Нажми для записи",
    recording_color="#e74c3c",
    neutral_color="#3498db",
    key="rec"
)

if audio_bytes:
    st.audio(audio_bytes, format="audio/wav")

    if st.button("💾 Сохранить"):
        if class_name.strip():
            cls, fname = save_audio(audio_bytes, class_name)
            st.success(f"Сохранено: {cls}/{fname}")
            st.rerun()
        else:
            st.error("Введи название класса")


# ───── UPLOAD ─────
st.divider()
st.subheader("📂 Загрузка файла")

uploaded = st.file_uploader("Загрузи WAV", type=["wav"])
upload_class = st.text_input("Класс файла")

if uploaded and st.button("Сохранить файл"):
    if upload_class.strip():
        data = uploaded.read()
        cls, fname = save_audio(data, upload_class)
        st.success(f"Сохранено: {cls}/{fname}")
        st.rerun()
    else:
        st.error("Введи класс")

# ───── ZIP DOWNLOAD ─────
st.divider()
st.subheader("📦 Скачать dataset.zip")

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for cls in os.listdir(DATASET_DIR):
        cls_path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(cls_path):
            for file in os.listdir(cls_path):
                file_path = os.path.join(cls_path, file)
                zf.write(file_path, f"{cls}/{file}")

zip_buffer.seek(0)

st.download_button(
    "⬇️ Скачать dataset.zip",
    data=zip_buffer.getvalue(),
    file_name="dataset.zip",
    mime="application/zip"
)