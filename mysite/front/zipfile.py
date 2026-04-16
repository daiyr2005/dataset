import streamlit as st
import requests
import zipfile
import io
import os
from audio_recorder_streamlit import audio_recorder

API = "http://127.0.0.1:8002/predict_1"
TARGET = 100  # цель: 100 записей на класс


def check_zip():
    st.title("🗂️ Сбор аудио датасета")

    # ───── Статистика ─────
    with st.expander("📊 Статистика датасета", expanded=True):
        try:
            stats = requests.get(f"{API}/stats", timeout=5).json()
            if stats["classes"]:
                cols = st.columns(len(stats["classes"]))
                for col, (cls, cnt) in zip(cols, stats["classes"].items()):
                    pct = min(int(cnt) / TARGET, 1.0)
                    col.metric(cls, f"{cnt} / {TARGET}")
                    col.progress(pct)
                st.caption(f"Всего: {stats['total']} файлов | Цель: {TARGET} на класс")
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

    # Показываем сколько осталось для выбранного класса
    if class_name.strip():
        try:
            stats = requests.get(f"{API}/stats", timeout=5).json()
            current = int(stats["classes"].get(class_name.strip(), 0))
            remaining = max(TARGET - current, 0)
            if remaining > 0:
                st.caption(f"📌 Записано: {current} / {TARGET} — осталось {remaining}")
            else:
                st.success(f"✅ Класс «{class_name.strip()}» заполнен ({TARGET}/{TARGET})")
        except:
            pass

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
                    # Проверяем лимит перед сохранением
                    stats = requests.get(f"{API}/stats", timeout=5).json()
                    current = int(stats["classes"].get(class_name.strip(), 0))
                    if current >= TARGET:
                        st.warning(f"⚠️ Класс «{class_name.strip()}» уже достиг {TARGET} записей!")
                    else:
                        resp = requests.post(
                            f"{API}/save",
                            files={"file": ("record.wav", audio_bytes, "audio/wav")},
                            data={"class_name": class_name},
                            timeout=10
                        )
                        if resp.status_code == 200:
                            r = resp.json()
                            new_count = int(r["total"])
                            st.success(f"✅ Сохранено! Класс «{r['class']}» — {new_count} / {TARGET}")
                            if new_count >= TARGET:
                                st.balloons()
                                st.info(f"🎉 Класс «{r['class']}» достиг цели {TARGET} записей!")
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
            try:
                stats = requests.get(f"{API}/stats", timeout=5).json()
                current = int(stats["classes"].get(class_upload.strip(), 0))
                if current >= TARGET:
                    st.warning(f"⚠️ Класс «{class_upload.strip()}» уже достиг {TARGET} записей!")
                else:
                    uploaded.seek(0)
                    resp = requests.post(
                        f"{API}/save",
                        files={"file": (uploaded.name, uploaded.read(), "audio/wav")},
                        data={"class_name": class_upload},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        r = resp.json()
                        new_count = int(r["total"])
                        st.success(f"✅ Сохранено! Класс «{r['class']}» — {new_count} / {TARGET}")
                        if new_count >= TARGET:
                            st.balloons()
                        st.rerun()
                    else:
                        st.error(f"Ошибка: {resp.text}")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    # ───── Скачать ZIP ─────
    st.divider()
    st.subheader("📦 Скачать датасет как ZIP")

    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("🗜️ Подготовить ZIP", type="primary", key="zip_btn"):
            try:
                # Запрашиваем список всех файлов с сервера
                resp = requests.get(f"{API}/list_files", timeout=10)
                if resp.status_code == 200:
                    files_info = resp.json()  # ожидаем: [{"class": "dog", "filename": "001.wav", "url": "..."}]

                    if not files_info:
                        st.warning("Датасет пуст — нечего скачивать.")
                    else:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            progress_bar = st.progress(0)
                            total_files = len(files_info)

                            for i, item in enumerate(files_info):
                                cls = item["class"]
                                fname = item["filename"]
                                file_url = item.get("url")

                                if file_url:
                                    # Скачиваем файл по URL
                                    file_resp = requests.get(file_url, timeout=10)
                                    if file_resp.status_code == 200:
                                        zf.writestr(f"{cls}/{fname}", file_resp.content)
                                else:
                                    # Альтернатива: запрос по отдельному endpoint
                                    file_resp = requests.get(
                                        f"{API}/file",
                                        params={"class_name": cls, "filename": fname},
                                        timeout=10
                                    )
                                    if file_resp.status_code == 200:
                                        zf.writestr(f"{cls}/{fname}", file_resp.content)

                                progress_bar.progress((i + 1) / total_files)

                        zip_buffer.seek(0)
                        st.session_state["zip_data"] = zip_buffer.getvalue()
                        st.success(f"✅ ZIP готов! {total_files} файлов.")
                        st.rerun()
                else:
                    st.error(f"Не удалось получить список файлов: {resp.text}")
            except Exception as e:
                st.error(f"Ошибка при создании ZIP: {e}")

    with col2:
        if "zip_data" in st.session_state and st.session_state["zip_data"]:
            st.download_button(
                label="⬇️ Скачать dataset.zip",
                data=st.session_state["zip_data"],
                file_name="audio_dataset.zip",
                mime="application/zip",
                key="download_zip_btn"
            )