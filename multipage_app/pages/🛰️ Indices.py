import ee
import geemap
import geemap.foliumap as geemap
import streamlit as st
import streamlit_folium
from streamlit_folium import folium_static
import plotly.express as px 
import pandas as pd 
import matplotlib.pyplot as plt 
from datetime import datetime

#Página
st.set_page_config(layout="wide")

st.title("Índices")
st.divider()

st.sidebar.markdown("""Aplicativo para classificação de índices geoespaciais""")

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

#Funções

#Máscara de Nuvem Sentinel 2 Sentinel-2 SR image
def maskCloudAndShadowsSR(image):
  cloudProb = image.select('MSK_CLDPRB');
  snowProb = image.select('MSK_SNWPRB');
  cloud = cloudProb.lt(5);
  snow = snowProb.lt(5);
  scl = image.select('SCL'); 
  shadow = scl.eq(3); # 3 = cloud shadow
  cirrus = scl.eq(10); # 10 = cirrus
  
  # Probabilidade de nuvem menor que 5% ou classificação de sombra de nuvem
  mask = (cloud.And(snow)).And(cirrus.neq(1)).And(shadow.neq(1));
  
  return image.updateMask(mask).select('B.*').multiply(0.0001).set('data',image.date().format('YYYY-MM-dd')).copyProperties(image, image.propertyNames());

#Índices
def indice(image):
  ndvi = image.normalizedDifference(['B8','B4']).rename('ndvi')
  
  evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2')
            }
        ).rename('evi')
  
  savi = image.expression(
      '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
      {
          'NIR': image.select('B8'),
          'RED': image.select('B4'),
          'L': 0.5
      }
    ).rename('savi')
  
  return image.addBands([ndvi,evi,savi]).clip(roi_city).copyProperties(image, image.propertyNames())

#Analisys Date
today_date = ee.Date(datetime.now())
day_pass = today_date.advance(-4, 'months')

#Date Format
formatted_day_today = today_date.format('YYYY-MM-dd').getInfo()
formatted_day_pass = day_pass.format('YYYY-MM-dd').getInfo()

#App Date
start_date = st.sidebar.text_input('Data de Início', value=formatted_day_pass)
end_date = st.sidebar.text_input('Data de Fim', value=formatted_day_today)

#Nuvens
max_cloud_percent = st.sidebar.slider('Selecione o percentual máximo de nuvens', min_value=0, max_value=100, value=5)

#Image Collections
S2 = ee.ImageCollection("COPERNICUS/S2_SR")\
                          .filterBounds(roi_city)\
                          .filterDate(start_date, end_date)\
                          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',max_cloud_percent))\
                          .map(maskCloudAndShadowsSR)\
                          .map(indice)\
                          .select(['ndvi','savi','evi'])
                          
#Image Selection
date_image = list((S2.aggregate_array('data').distinct().getInfo()))
data_select = st.selectbox('Selecione a data da imagem', date_image)

image_select = S2.filter(ee.Filter.eq('data', data_select)).median()

#Display
m.add_basemap('HYBRID')
m.addLayer(roi_city, {}, 'Município')
m.addLayer(image_select.select('ndvi'), {'palette':['red','yellow','green'], 'min':0, 'max':0.7}, 'NDVI {}'.format(str(data_select)))
m.addLayer(image_select.select('evi'), {'palette':['red','yellow','green'], 'min':0, 'max':0.7}, 'EVI {}'.format(str(data_select)))
m.addLayer(image_select.select('savi'), {'palette':['red','yellow','green'], 'min':0, 'max':0.7}, 'SAVI {}'.format(str(data_select)))
m.centerObject(roi_city,10)
m.to_streamlit()

#Statistics
def reduce (image):
    serie_reduce = image.reduceRegions(**{
                        'collection': roi_city,
                        'reducer': ee.Reducer.mean(),
                        'scale': 30
                        })
    
    serie_reduce = serie_reduce.map(lambda f: f.set({'data': image.get('data')}))
    
    return serie_reduce.copyProperties(image, image.propertyNames())

#Applying reduce
data_reduce = S2.map(reduce)\
                .flatten()\
                .sort('data',True)\
                .select(['NM_MUN','data','evi','ndvi','savi'])
                
st.divider()
df_stats = geemap.ee_to_df(data_reduce)

#mean
df_stats_grouped = df_stats.groupby('data')[['ndvi', 'evi', 'savi']].mean().reset_index()

#Graph
fig = px.line(df_stats_grouped, x='data', y=['ndvi', 'evi', 'savi'],
              labels={'value': 'Índice', 'variable': 'Tipo do índice'},
              title='Variação entre os índices NDVI, EVI e SAVI ao longo do tempo',
              color_discrete_map={
                  'ndvi': 'green',
                  'evi': 'red',
                  'savi': 'blue'
              })

#Exibition
col1, col2 = st.columns([0.6,0.4])

with col1:
    st.plotly_chart(fig)


with col2:
    st.dataframe(df_stats, width=600, height=400)

#Fim
st.divider()
st.sidebar.markdown("Desenvolvido por Leonardo Silva")
