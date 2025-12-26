import streamlit as st
import pandas as pd
import plotlypip
st.set_page_config(page_title-'CSV File Reader', layout-'wide')
st.header('Single File Upload')
Upload_file = st.file_uploader('Uploade yur csv File')
df - pd.read_csv(Upload_file)
st.dataframe(df, wide=1800, height=1200)


          