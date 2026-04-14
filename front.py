import streamlit as st
from mysite.front.test import check_collector


page = st.sidebar.selectbox("Выберите страницу", ["Сбор датасета",])

if page == "Сбор датасета":
    check_collector()
