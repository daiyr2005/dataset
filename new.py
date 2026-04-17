import streamlit as st
import zipfile
import io
import os
import uuid
import shutil
from audio_recorder_streamlit import audio_recorder

TARGET = 100

# ───── DATASET DIR из session_state ─────
if "dataset_dir" not in st.session_state:
    st.session_state["dataset_dir"] = "dataset"

DATASET_DIR = st.session_state["dataset_dir"]
os.makedirs(DATASET_DIR, exist_ok=True)

st.title("🗂️ Сбор аудио датасета")

# ───── ПЕРЕКЛЮЧЕНИЕ ДАТАСЕТА ─────
all_datasets = [d for d in os.listdir(".") if os.path.isdir(d) and not d.startswith(".")]

col1, col2 = st.columns([2, 1])
with col1:
    selected = st.selectbox("📁 Текущий датасет", all_datasets, index=all_datasets.index(DATASET_DIR) if DATASET_DIR in all_datasets else 0)
    if selected != DATASET_DIR:
        st.session_state["dataset_dir"] = selected
        st.rerun()

with col2:
    st.metric("Активный", DATASET_DIR)

st.divider()

# ───── СОЗДАТЬ НОВЫЙ ДАТАСЕТ ─────
st.subheader("🆕 Создать новый датасет")

new_name = st.text_input("Название нового датасета", placeholder="например: dataset_2")

if st.button("🆕 Создать"):
    if new_name.strip():
        new_dir = new_name.strip().lower().replace(" ", "_")
        os.makedirs(new_dir, exist_ok=True)
        st.session_state["dataset_dir"] = new_dir
        st.success(f"✅ Создан и выбран: `{new_dir}`")
        st.rerun()
    else:
        st.error("Введи название")

st.divider()

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

# ПРОВЕРКА
st.write("audio_bytes:", audio_bytes)
st.write("тип:", type(audio_bytes))
st.write("длина:", len(audio_bytes) if audio_bytes else 0)

if audio_bytes and len(audio_bytes) > 1000:  # меньше 1000 байт = пустая запись
    st.audio(audio_bytes, format="audio/wav")
    if st.button("💾 Сохранить"):
        if class_name.strip():
            cls, fname = save_audio(audio_bytes, class_name)
            st.success(f"Сохранено: {cls}/{fname}")
            st.rerun()
        else:
            st.error("Введи название класса")
else:
    if audio_bytes:
        st.warning("⚠️ Запись слишком короткая или пустая!")
    else:
        st.info("Нажми кнопку и запиши звук")
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

# ───── IMPORT ZIP ─────
st.divider()
st.subheader("📥 Загрузить / обновить датасет из ZIP")

uploaded_zip = st.file_uploader("Загрузи ZIP датасет", type=["zip"], key="zip_upload")

mode = st.radio(
    "Режим загрузки",
    ["➕ Добавить к существующему", "🔄 Заменить существующий"],
    horizontal=True
)

if uploaded_zip and st.button("📥 Импортировать ZIP"):
    if mode == "🔄 Заменить существующий":
        shutil.rmtree(DATASET_DIR)
        os.makedirs(DATASET_DIR, exist_ok=True)

    imported = 0
    with zipfile.ZipFile(io.BytesIO(uploaded_zip.read())) as zf:
        for name in zf.namelist():
            parts = name.strip("/").split("/")
            if len(parts) == 2:
                cls_name, file_name = parts
                if file_name.endswith(".wav"):
                    cls_dir = os.path.join(DATASET_DIR, cls_name)
                    os.makedirs(cls_dir, exist_ok=True)
                    save_path = os.path.join(cls_dir, f"{uuid.uuid4()}.wav")
                    with zf.open(name) as src, open(save_path, "wb") as dst:
                        dst.write(src.read())
                    imported += 1

    st.success(f"✅ Импортировано {imported} файлов!")
    st.rerun()

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
    file_name=f"{DATASET_DIR}.zip",
    mime="application/zip"
)