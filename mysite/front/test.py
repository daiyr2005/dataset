import streamlit as st
import requests
import time
from audio_recorder_streamlit import audio_recorder

API = "http://127.0.0.1:8002/predict_1"

def check_collector():
    st.title("🗂️ Сбор аудио датасета")

    # ───── Статистика ─────
    with st.expander("📊 Статистика датасета", expanded=True):
        try:
            stats = requests.get(f"{API}/stats", timeout=5).json()
            if stats["classes"]:
                cols = st.columns(len(stats["classes"]))
                for col, (cls, cnt) in zip(cols, stats["classes"].items()):
                    col.metric(cls, cnt, "записей")
                st.caption(f"Всего: {stats['total']} файлов")
            else:
                st.info("Датасет пуст — начни запись!")
        except:
            st.warning("Сервер недоступен")

    st.divider()

    # ───── Запись голоса ─────
    st.subheader("🎙️ Запись нового примера")

    class_name = st.text_input(
        "Название класса (папки)",
        placeholder="например: dog, cat, car_horn",
        key="class_input"
    )

    audio_bytes = audio_recorder(
        text="Нажми для записи",
        recording_color="#e74c3c",
        neutral_color="#3498db",
        key="collector_recorder"
    )

    if audio_bytes and len(audio_bytes) > 0:
        st.audio(audio_bytes, format="audio/wav")

        if st.button("💾 Сохранить в датасет", key="save_btn", type="primary"):
            if not class_name.strip():
                st.error("Введи название класса!")
            else:
                try:
                    resp = requests.post(
                        f"{API}/save",
                        files={"file": ("record.wav", audio_bytes, "audio/wav")},
                        data={"class_name": class_name},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        r = resp.json()
                        st.success(f"✅ Сохранено! Класс «{r['class']}» — всего {r['total']} файлов")
                        st.rerun()
                    else:
                        st.error(f"Ошибка: {resp.text}")
                except Exception as e:
                    st.error(f"Ошибка соединения: {e}")

    # ───── Загрузка файла ─────
    st.divider()
    st.subheader("📂 Или загрузи готовый .wav")

    uploaded = st.file_uploader("Загрузи аудио файл", type=["wav"], key="file_upload")
    class_upload = st.text_input("Класс для файла", key="class_upload",
                                  placeholder="например: siren")

    if uploaded and st.button("💾 Сохранить файл", key="save_file_btn"):
        if not class_upload.strip():
            st.error("Введи название класса!")
        else:
            uploaded.seek(0)
            try:
                resp = requests.post(
                    f"{API}/save",
                    files={"file": (uploaded.name, uploaded.read(), "audio/wav")},
                    data={"class_name": class_upload},
                    timeout=10
                )
                if resp.status_code == 200:
                    r = resp.json()
                    st.success(f"✅ Сохранено! Класс «{r['class']}» — всего {r['total']} файлов")
                    st.rerun()
                else:
                    st.error(f"Ошибка: {resp.text}")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    # ───── Обучение ─────
    st.divider()
    st.subheader("🚀 Обучить модель")

    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("▶ Начать обучение", type="primary", key="train_btn"):
            try:
                resp = requests.post(f"{API}/train", timeout=10).json()
                if resp["status"] == "started":
                    st.success("Обучение запущено!")
                elif resp["status"] == "already_running":
                    st.warning("Обучение уже идёт...")
                else:
                    st.error(resp.get("detail", "Ошибка"))
            except Exception as e:
                st.error(f"Ошибка: {e}")

    with col2:
        if st.button("🔄 Обновить статус", key="refresh_btn"):
            pass  # просто перерисовывает страницу

    # Лог обучения
    try:
        status = requests.get(f"{API}/train/status", timeout=5).json()

        if status["running"]:
            st.info("⏳ Обучение идёт...")
            progress = len([l for l in status["log"] if "Epoch" in l])
            st.progress(progress / 10)

        if status["log"]:
            with st.expander("📋 Лог обучения", expanded=status["running"]):
                for line in status["log"]:
                    st.text(line)

        if status["accuracy"] is not None:
            st.metric("Точность на тесте", f"{status['accuracy']}%")

    except:
        pass