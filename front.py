import streamlit as st
from mysite.front.test import check_collector
from mysite.front.zipfile import check_zip


page = st.sidebar.selectbox("Выберите страницу", ["Сбор датасета", "zipfile"])

if page == "Сбор датасета":
    check_collector()

elif page =='zipfile':
    check_zip()
