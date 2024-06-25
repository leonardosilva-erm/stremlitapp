import ee
import geemap
import geemap.foliumap as geemap
import streamlit as st
import streamlit_folium
from streamlit_folium import folium_static
import plotly.express as px 
import pandas as pd 
import geopandas as gpd
import matplotlib.pyplot as plt 
from datetime import datetime
import json

#Página
st.set_page_config(layout="wide")

st.title("Precipitação")
st.divider()

st.sidebar.markdown("""Análise de dados de precipitação no Brasil""")

m = geemap.Map()

roi = ee.FeatureCollection('projects/ee-leonardorcgeo/assets/Br_Mun')

#Botão de filtro de Estado
list_states = sorted(list(roi.aggregate_array('SIGLA_UF').distinct().getInfo()))
state = st.selectbox("Selecione o estado de interesse:", list_states)
roi_state = roi.filter(ee.Filter.eq('SIGLA_UF', ee.String(state)))

#Botão de filtro de Município
list_city = sorted(list(roi_state.aggregate_array('NM_MUN').distinct().getInfo()))
city = st.selectbox("Selecione o município de interesse:", list_city)
roi_city = roi_state.filter(ee.Filter.eq('NM_MUN', ee.String(city)))

#Analisys Date
today_date = ee.Date(datetime.now())
day_pass = today_date.advance(-4, 'months')

#Date Format
formatted_day_today = today_date.format('YYYY-MM-dd').getInfo()
formatted_day_pass = day_pass.format('YYYY-MM-dd').getInfo()

#App Date
start_date = st.sidebar.text_input('Data de Início', value=formatted_day_pass)
end_date = st.sidebar.text_input('Data de Fim', value=formatted_day_today)

def data(image):
    return image.clip(roi_city).set({'data':image.date().format('yyy-MM-dd')})

chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")\
                     .select('precipitation')\
                     .filterDate(start_date, end_date)\
                     .filterBounds(roi_city)\
                     .map(data)
                     
#Statistics
def  stats(image):
    reduce = image.reduceRegions(**{
                        'collection': roi_city,
                        'reducer': ee.Reducer.mean().combine(**{
                        'reducer2': ee.Reducer.min(),
                        'sharedInputs': True}).combine(**{
                        'reducer2': ee.Reducer.max(),
                        'sharedInputs': True}),
                        'scale': 5000
                        })
    
    serie_reduce = reduce.map(lambda f: f.set({'data': image.get('data')}))
    
    return serie_reduce.copyProperties(image, image.propertyNames())

#Applying reduce
data_reduce = chirps.map(stats)\
                .flatten()\
                .sort('data',True)\
                .select(['SIGLA_UF', 'NM_MUN', 'data', 'precipitation', 'Ano'])
                
st.divider()
df_stats = geemap.ee_to_df(data_reduce)


#Display
m.add_basemap('HYBRID')
m.addLayer(roi_city, {}, 'Município')
m.addLayer(chirps.mean(), {'palette':['white','red','orange','red','cyan','blue'],min:0, max:0.7},'Precipitação')
m.centerObject(roi_city,10)
m.to_streamlit()

#Fim
st.divider()
st.sidebar.markdown("Desenvolvido por Leonardo Silva !")