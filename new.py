import streamlit as st
import os
import uuid
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio
from torchaudio import transforms
from torch.utils.data import Dataset, DataLoader, random_split
import soundfile as sf
import io
from audio_recorder_streamlit import audio_recorder

# ───── CONFIG ─────
DATASET_DIR = "dataset"
TARGET_SR = 16000
TARGET_MEL_LEN = 100

st.set_page_config(page_title="Audio AI", layout="centered")
st.title("🎧 FULL AUDIO AI (ONE STREAMLIT APP)")

# ───── MODEL ─────
class AudioCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((8, 8))
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 128), nn.ReLU(),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        return self.fc(self.net(x.unsqueeze(1)))


# ───── DATA ─────
class AudioDataset(Dataset):
    def __init__(self):
        self.samples = []
        self.classes = sorted(os.listdir(DATASET_DIR)) if os.path.exists(DATASET_DIR) else []
        self.label_map = {c: i for i, c in enumerate(self.classes)}
        self.mel = transforms.MelSpectrogram(sample_rate=TARGET_SR, n_mels=64)

        for cls in self.classes:
            path = os.path.join(DATASET_DIR, cls)
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.endswith(".wav"):
                        self.samples.append((os.path.join(path, f), cls))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, cls = self.samples[idx]
        waveform, sr = torchaudio.load(path)

        waveform = waveform.mean(dim=0, keepdim=True)
        if sr != TARGET_SR:
            waveform = transforms.Resample(sr, TARGET_SR)(waveform)

        spec = self.mel(waveform).squeeze(0)

        if spec.shape[1] > TARGET_MEL_LEN:
            spec = spec[:, :TARGET_MEL_LEN]
        else:
            spec = F.pad(spec, (0, TARGET_MEL_LEN - spec.shape[1]))

        return spec, self.label_map[cls]


# ───── TRAIN STATE ─────
if "model" not in st.session_state:
    st.session_state.model = None
if "classes" not in st.session_state:
    st.session_state.classes = None


# ───── SIDEBAR ─────
menu = st.sidebar.selectbox("Menu", ["📊 Dataset", "🎙️ Record", "🧠 Train", "🔮 Predict"])

os.makedirs(DATASET_DIR, exist_ok=True)

# ─────────────────────────────
# 📊 DATASET
# ─────────────────────────────
if menu == "📊 Dataset":
    st.subheader("Dataset stats")

    stats = {}
    for cls in os.listdir(DATASET_DIR):
        path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(path):
            stats[cls] = len(os.listdir(path))

    st.write(stats)

# ─────────────────────────────
# 🎙️ RECORD
# ─────────────────────────────
elif menu == "🎙️ Record":
    st.subheader("Record audio")

    class_name = st.text_input("Class name")

    audio = audio_recorder()

    if audio:
        st.audio(audio)

        if st.button("Save"):
            if class_name:
                cls_path = os.path.join(DATASET_DIR, class_name)
                os.makedirs(cls_path, exist_ok=True)

                filename = str(uuid.uuid4()) + ".wav"
                path = os.path.join(cls_path, filename)

                with open(path, "wb") as f:
                    f.write(audio)

                st.success("Saved!")
                st.rerun()

# ─────────────────────────────
# 🧠 TRAIN
# ─────────────────────────────
elif menu == "🧠 Train":
    st.subheader("Train model")

    if st.button("Start training"):
        dataset = AudioDataset()

        if len(dataset) == 0:
            st.error("Dataset empty")
        else:
            train_size = int(len(dataset) * 0.8)
            test_size = len(dataset) - train_size

            train_ds, test_ds = random_split(dataset, [train_size, test_size])

            train_dl = DataLoader(train_ds, batch_size=8, shuffle=True)
            test_dl = DataLoader(test_ds, batch_size=8)

            model = AudioCNN(len(dataset.classes))
            opt = torch.optim.Adam(model.parameters(), lr=0.001)
            loss_fn = nn.CrossEntropyLoss()

            for epoch in range(3):
                model.train()
                for x, y in train_dl:
                    loss = loss_fn(model(x.float()), y)
                    opt.zero_grad()
                    loss.backward()
                    opt.step()

                st.write(f"Epoch {epoch+1} done")

            st.session_state.model = model
            st.session_state.classes = dataset.classes

            st.success("Model trained")

# ─────────────────────────────
# 🔮 PREDICT
# ─────────────────────────────
elif menu == "🔮 Predict":
    st.subheader("Predict audio")

    audio = audio_recorder(key="pred")

    if audio:
        st.audio(audio)

        if st.button("Predict"):
            if st.session_state.model is None:
                st.error("Train model first")
            else:
                model = st.session_state.model
                model.eval()

                waveform, sr = torchaudio.load(io.BytesIO(audio))
                waveform = waveform.mean(dim=0, keepdim=True)

                mel = transforms.MelSpectrogram(sample_rate=TARGET_SR, n_mels=64)
                spec = mel(waveform)

                spec = spec[:, :TARGET_MEL_LEN]
                if spec.shape[1] < TARGET_MEL_LEN:
                    spec = F.pad(spec, (0, TARGET_MEL_LEN - spec.shape[1]))

                with torch.no_grad():
                    pred = model(spec.float()).argmax(dim=1).item()

                st.success(st.session_state.classes[pred])