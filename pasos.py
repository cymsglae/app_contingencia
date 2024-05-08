import streamlit as st
import pandas as pd
from arcgis.gis import GIS
from arcgis.features import FeatureLayer


# Autenticación con ArcGIS
gis = GIS("https://mahuilque.maps.arcgis.com/", "Mahuilque", "Mahuilque2022")

# ID del item de tu encuesta Survey123
item_id = "71182aa01a414350a12f891fbc4c6514"

# Obtener el item y su capa de datos
item = gis.content.get(item_id)
flayer = item.layers[0]

# Descargar los datos como DataFrame
df = flayer.query(where="1=1", as_df=True)

st.title('Datos de la Encuesta Survey123')

# Mostrar los datos en una tabla
st.dataframe(df)

st.bar_chart(df['tipo_sensor'])

