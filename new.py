import streamlit as st
from audio_recorder_streamlit import audio_recorder
import os
import uuid
import zipfile
import io
import random
import librosa
import numpy as np
import soundfile as sf

# ───── SETTINGS ─────
TARGET = 100


import streamlit as st
from audio_recorder_streamlit import audio_recorder

st.title("Test mic")

audio_bytes = audio_recorder()

if audio_bytes:
    st.audio(audio_bytes)
    st.write("OK")
else:
    st.write("No audio")


if "dataset_dir" not in st.session_state:
    st.session_state["dataset_dir"] = "dataset"

DATASET_DIR = st.session_state["dataset_dir"]
os.makedirs(DATASET_DIR, exist_ok=True)

st.title("🗂️ Audio Dataset + 500 Voice Augmentation")


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


# ───── COUNT ─────
def get_local_count(class_name):
    class_dir = os.path.join(DATASET_DIR, class_name)
    if not os.path.exists(class_dir):
        return 0
    return len([f for f in os.listdir(class_dir) if f.endswith(".wav")])


# ───── 500 VOICE AUGMENTATION ─────
def generate_500_variants(audio_bytes):
    # вместо librosa.load напрямую из BytesIO
    buffer = io.BytesIO(audio_bytes)
    y, sr = sf.read(buffer)  # soundfile умеет читать из BytesIO

    outputs = []
    for _ in range(500):
        y_mod = y.copy()

        # pitch shift
        n_steps = random.uniform(-8, 8)
        y_mod = librosa.effects.pitch_shift(y_mod, sr=sr, n_steps=n_steps)

        # speed change
        rate = random.uniform(0.85, 1.15)
        y_mod = librosa.effects.time_stretch(y_mod, rate=rate)

        # noise
        noise = np.random.normal(0, 0.002, len(y_mod))
        y_mod = y_mod + noise

        buffer_out = io.BytesIO()
        sf.write(buffer_out, y_mod, sr, format="WAV")
        outputs.append(buffer_out.getvalue())

    return outputs


# ───── UI ─────
st.subheader("🎙️ Record audio")

class_name = st.text_input("Class name")

audio_bytes = audio_recorder(
    text="Press to record",
    recording_color="#e74c3c",
    neutral_color="#3498db"
)


# ───── PREVIEW ─────
if audio_bytes:
    st.audio(audio_bytes, format="audio/wav")

    st.subheader("🔥 Generate dataset")

    if st.button("Generate 500 voices"):
        if not class_name.strip():
            st.error("Enter class name")
        else:
            cls = class_name.strip().lower().replace(" ", "_")
            class_dir = os.path.join(DATASET_DIR, cls)
            os.makedirs(class_dir, exist_ok=True)

            variants = generate_500_variants(audio_bytes)

            for i, audio in enumerate(variants):
                filename = f"{uuid.uuid4()}_{i}.wav"
                path = os.path.join(class_dir, filename)

                with open(path, "wb") as f:
                    f.write(audio)

            st.success("🔥 500 files created!")
            st.balloons()
            st.rerun()

    if st.button("💾 Save single file"):
        if class_name.strip():
            cls, fname = save_audio(audio_bytes, class_name)
            count = get_local_count(cls)
            st.success(f"Saved: {cls}/{fname} — {count}")
            st.rerun()
        else:
            st.error("Enter class name")


# ───── UPLOAD ─────
st.divider()
st.subheader("📂 Upload WAV")

uploaded = st.file_uploader("Upload wav", type=["wav"])
upload_class = st.text_input("Upload class")

if uploaded and st.button("Save upload"):
    if upload_class.strip():
        save_audio(uploaded.read(), upload_class)
        st.success("Uploaded")
        st.rerun()
    else:
        st.error("Enter class")


# ───── ZIP EXPORT ─────
st.divider()
st.subheader("📦 Download dataset")

zip_buffer = io.BytesIO()

with zipfile.ZipFile(zip_buffer, "w") as zf:
    for cls in os.listdir(DATASET_DIR):
        cls_path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(cls_path):
            for file in os.listdir(cls_path):
                zf.write(os.path.join(cls_path, file), f"{cls}/{file}")

zip_buffer.seek(0)

st.download_button(
    "⬇️ Download ZIP",
    data=zip_buffer.getvalue(),
    file_name="dataset.zip"
)