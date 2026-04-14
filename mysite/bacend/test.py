from fastapi import FastAPI, UploadFile, File, Form, APIRouter, BackgroundTasks
import os, uuid, torch, torch.nn as nn, torch.nn.functional as F
import torchaudio
from torchaudio import transforms
from torch.utils.data import Dataset, DataLoader, random_split
import soundfile as sf
import io

collector_router = APIRouter(prefix='/predict_1', tags=['Collector'])

DATASET_DIR = 'dataset'  # dataset/класс/uuid.wav


# ───── Сохранение аудио ─────
@collector_router.post('/save')
async def save_audio(
    file: UploadFile = File(...),
    class_name: str = Form(...)
):
    class_name = class_name.strip().lower().replace(' ', '_')
    class_dir = os.path.join(DATASET_DIR, class_name)
    os.makedirs(class_dir, exist_ok=True)

    count = len([f for f in os.listdir(class_dir) if f.endswith('.wav')])
    filename = f"{1000 + count + 1}.wav"
    filepath = os.path.join(class_dir, filename)

    data = await file.read()
    with open(filepath, 'wb') as f:
        f.write(data)

    count = len(os.listdir(class_dir))
    return {"status": "ok", "class": class_name, "file": filename, "total": count}


# ───── Статистика датасета ─────
@collector_router.get('/stats')
async def dataset_stats():
    if not os.path.exists(DATASET_DIR):
        return {"classes": {}, "total": 0}

    stats = {}
    for cls in sorted(os.listdir(DATASET_DIR)):
        cls_path = os.path.join(DATASET_DIR, cls)
        if os.path.isdir(cls_path):
            stats[cls] = len([f for f in os.listdir(cls_path) if f.endswith('.wav')])

    return {"classes": stats, "total": sum(stats.values())}


# ───── Модель ─────
class AudioCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.cnn = nn.Sequential(
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
        return self.fc(self.cnn(x.unsqueeze(1)))


# ───── Датасет из папок ─────
class FolderAudioDataset(Dataset):
    def __init__(self, dataset_dir, max_len=100, sample_rate=16000, n_mels=64):
        self.samples = []
        self.classes = sorted(os.listdir(dataset_dir))
        self.label_map = {c: i for i, c in enumerate(self.classes)}
        self.max_len = max_len
        self.mel = transforms.MelSpectrogram(sample_rate=sample_rate, n_mels=n_mels)
        self.resample_cache = {}
        self.target_sr = sample_rate

        for cls in self.classes:
            cls_path = os.path.join(dataset_dir, cls)
            if not os.path.isdir(cls_path):
                continue
            for fname in os.listdir(cls_path):
                if fname.endswith('.wav'):
                    self.samples.append((os.path.join(cls_path, fname), cls))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, cls = self.samples[idx]
        waveform, sr = torchaudio.load(path)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sr != self.target_sr:
            if sr not in self.resample_cache:
                self.resample_cache[sr] = transforms.Resample(sr, self.target_sr)
            waveform = self.resample_cache[sr](waveform)

        spec = self.mel(waveform).squeeze(0)
        if spec.shape[1] > self.max_len:
            spec = spec[:, :self.max_len]
        elif spec.shape[1] < self.max_len:
            spec = F.pad(spec, (0, self.max_len - spec.shape[1]))

        return spec, self.label_map[cls]


training_status = {"running": False, "log": [], "accuracy": None}


def run_training():
    training_status["running"] = True
    training_status["log"] = []
    training_status["accuracy"] = None

    try:
        dataset = FolderAudioDataset(DATASET_DIR)
        classes = dataset.classes
        torch.save(classes, 'collected_labels.pth')

        train_size = int(len(dataset) * 0.8)
        test_size = len(dataset) - train_size
        train_ds, test_ds = random_split(dataset, [train_size, test_size],
                                         generator=torch.Generator().manual_seed(42))

        train_dl = DataLoader(train_ds, batch_size=16, shuffle=True)
        test_dl  = DataLoader(test_ds,  batch_size=16)

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = AudioCNN(len(classes)).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        for epoch in range(10):
            model.train()
            total_loss = 0
            for x, y in train_dl:
                x, y = x.to(device).float(), y.to(device)
                loss = criterion(model(x), y)
                optimizer.zero_grad(); loss.backward(); optimizer.step()
                total_loss += loss.item()
            msg = f"Epoch {epoch+1}/10 — loss: {total_loss:.2f}"
            training_status["log"].append(msg)

        # Оценка
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in test_dl:
                x, y = x.to(device).float(), y.to(device)
                preds = model(x).argmax(dim=1)
                correct += (preds == y).sum().item()
                total += y.size(0)

        acc = 100 * correct / total if total > 0 else 0
        training_status["accuracy"] = round(acc, 2)
        training_status["log"].append(f"Точность: {acc:.2f}%")
        torch.save(model.state_dict(), 'collected_model.pth')
        training_status["log"].append("Модель сохранена: collected_model.pth")

    except Exception as e:
        training_status["log"].append(f"Ошибка: {e}")
    finally:
        training_status["running"] = False


@collector_router.post('/train')
async def start_training(background_tasks: BackgroundTasks):
    if training_status["running"]:
        return {"status": "already_running"}
    if not os.path.exists(DATASET_DIR) or not os.listdir(DATASET_DIR):
        return {"status": "error", "detail": "Датасет пуст"}
    background_tasks.add_task(run_training)
    return {"status": "started"}


@collector_router.get('/train/status')
async def get_training_status():
    return training_status

@collector_router.post('/')
async def predict_audio(file: UploadFile = File(...)):
    # читаем аудио
    data = await file.read()
    waveform, sr = torchaudio.load(io.BytesIO(data))

    # загружаем классы и модель
    classes = torch.load('labels.pth')
    model = AudioCNN(len(classes))
    model.load_state_dict(torch.load('model.pth'))
    model.eval()

    # преобразуем в спектрограмму
    mel = transforms.MelSpectrogram(sample_rate=16000, n_mels=64)
    spec = mel(waveform.mean(dim=0, keepdim=True))
    spec = spec[:, :100] if spec.shape[1] > 100 else F.pad(spec, (0, 100 - spec.shape[1]))

    with torch.no_grad():
        pred = model(spec).argmax(dim=1).item()

    return {"Класс": classes[pred], "Индекс": pred}