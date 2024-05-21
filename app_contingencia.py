##Carga de librerias
import datetime as dt
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
import pyproj ##libreria para transformacion espacial UTM
import plotly.express as px
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import warnings
import openpyxl
import altair as alt
from streamlit_folium import folium_static
from shapely.geometry import Point
from branca.element import Figure, Template, MacroElement

warnings.filterwarnings('ignore')
##Funciones de creacion del mapa
shapefile_AAOO = gpd.read_file('Shp/AAOO_6k.shp')
shapefile_tuberia = gpd.read_file('Shp/TUBERIA.shp')
shapefile_BOAT = gpd.read_file('Shp/ao_test.shp')
area_especifica = shapefile_BOAT.iloc[0].geometry


def estilo(feature):

    if feature['properties']['AREA'] == 1000:
        color = 'blue'
    elif feature['properties']['AREA'] == 2000:
        color = 'green'
    elif feature['properties']['AREA'] == 3000:
        color = 'red'
    elif feature['properties']['AREA'] == 4000:
        color = 'yellow'
    elif feature['properties']['AREA'] == 5000:
        color = 'white'
    else:
        color = 'gray'  # Color por defecto

    # Devuelve un diccionario con el estilo
    return {
        'fillColor': color,
        'color': 'black',  # Color del borde
        'weight': 1,       # Grosor del borde
        'fillOpacity': 0.5 # Opacidad del relleno
    }
    
    # Definir un esquema de colores para las metodologías
colores_mot_interv = {
    "Avistamiento de individuos": "red",
    "Ahuyentamiento de individuos": "blue",
    "Atencion a atropello y colision con fauna": "green",
    "Disposicion de fauna muerta": "yellow",
    "Rescate de mamiferos, reptiles, anfibios y/o aves": "purple",
    "Rescate de especies hidrobiologicas": "purple",
}


def create_map():
    # Crear un mapa centrado en una ubicación específica (por ejemplo, latitud y longitud de Nueva York)
    m = folium.Map(location=[-17.1196497, -70.861221], zoom_start=9)
    # Puedes agregar más características al mapa aquí (marcadores, capas, etc.)
    #folium.GeoJson(shapefile_BOAT).add_to(m)
    folium.GeoJson(
        shapefile_AAOO,
        style_function=estilo,
        tooltip=folium.GeoJsonTooltip(fields=['Nombre'], aliases=['Nombre:'])
    ).add_to(m)
    folium.GeoJson(shapefile_tuberia).add_to(m)
    folium.GeoJson(shapefile_BOAT).add_to(m)

    folium.GeoJson(
    shapefile_AAOO,
    style_function=estilo,
    tooltip=folium.GeoJsonTooltip(fields=['Nombre'], aliases=['Nombre:'])  # Añadir etiqueta
).add_to(m)
    for index, row in df_espacial_sin_vacios.iterrows():
                folium.Marker(
                    [row['lat_registro'], row['lon_registro']],
                    popup=row['motivo_intervencion'],
                    icon=folium.Icon(color=colores_mot_interv.get(row['motivo_intervencion'], 'gray'))
                ).add_to(m)
    
    # Agregar leyenda (usando HTML y CSS)
    template = """
    {% macro html(this, kwargs) %}
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 150px; height: 90px; 
                border:2px solid grey; z-index:9999; font-size:14px;
                ">&nbsp; Leyenda <br>
                &nbsp; Metodología 1 &nbsp; <i class="fa fa-map-marker fa-2x" style="color:red"></i><br>
                &nbsp; Metodología 2 &nbsp; <i class="fa fa-map-marker fa-2x" style="color:blue"></i><br>
                &nbsp; Metodología 3 &nbsp; <i class="fa fa-map-marker fa-2x" style="color:green"></i>
    </div>
    {% endmacro %}
    """

    macro = MacroElement()
    macro._template = Template(template)

    m.get_root().add_child(macro)
    return m

##Funciones de control
def componente_biologico_unico(dataframe, columna):
    
    valores_unicos = dataframe[columna].unique()
    return valores_unicos


# Función para verificar si una fila coincide con alguna fila del DataFrame de control
def coincide_con_control(fila, df_control):
    for _, fila_control in df_control.iterrows():
        if fila.equals(fila_control):
            return True
    return False


def leer_excel_y_crear_dataframe(archivo_excel):
    # Leer las hojas del archivo de Excel
    xls = pd.ExcelFile(archivo_excel, engine='openpyxl')

    # Crear una lista para almacenar la información de las hojas
    info_hojas = []

    # Iterar sobre las hojas y recopilar la información
    for hoja in xls.sheet_names:
        df_temp = pd.read_excel(xls, sheet_name=hoja)
        num_filas = len(df_temp)
        info_hojas.append({'Hoja': hoja, 'NumFilas': num_filas})

    # Crear un DataFrame con la información de las hojas
    df_hojas = pd.DataFrame(info_hojas)

    return df_hojas

##Funcion para realizar suma de abundancia Sexo e identificar que filas no coinciden
def encontrar_diferencias_sexo(df):
    # Calcular la suma de las columnas segunda a quinta para cada fila
    df['suma_calculada'] = df.iloc[:, 1:5].sum(axis=1)
    df_modificado = df.drop(df.columns[[1,2,3,4]], axis=1)
    df_modificado = df_modificado.dropna()
    #df_modificado_2 = df_modificado['suma_calculada'] != df_modificado['abundancia']
    #Crear una máscara booleana donde la suma no es igual al sexto campo
    df_filtrado = df_modificado[df_modificado.iloc[:, 1] != df_modificado.iloc[:, 2]]
    # Devolver el nuevo DataFrame con solo las filas que tienen diferencias
    return df_filtrado

##Funcion para realizar suma de abundancia Edad e identificar que filas no coinciden
def encontrar_diferencias_edad(df):
    # Calcular la suma de las columnas segunda a quinta para cada fila
    df['suma_calculada'] = df.iloc[:, 1:6].sum(axis=1)
    df_modificado = df.drop(df.columns[[1,2,3,4,5,6]], axis=1)
    df_modificado = df_modificado.dropna()
    #df_modificado_2 = df_modificado['suma_calculada'] != df_modificado['abundancia']
    #Crear una máscara booleana donde la suma no es igual al sexto campo
    df_filtrado = df_modificado[df_modificado.iloc[:, 1] != df_modificado.iloc[:, 2]]
    # Devolver el nuevo DataFrame con solo las filas que tienen diferencias
    return df_filtrado

# def encontrar_especies_no_registradas(df_control, df_campo):
#     # Fusionar los dos dataframes basándose en el identificador y el nombre
#     # 'indicator=True' añade una columna '_merge' que indica cómo se ha fusionado cada fila
#     df_merged = pd.merge(df_campo, df_control, on=['id_esp', 'especie'], how='left', indicator=True)

#     # Filtrar las filas que no coincidan en ambos dataframes
#     df_no_coincidentes = df_merged[df_merged['_merge'] != 'both']

#     # Eliminar la columna '_merge' ya que ya no se necesita
#     df_resultante = df_no_coincidentes.drop(columns=['_merge'])
#     return df_resultante

def encontrar_especies_no_registradas2(df_control2, df_campo2):
    # Fusionar los dos dataframes basándose en el identificador y el nombre
    # 'indicator=True' añade una columna '_merge' que indica cómo se ha fusionado cada fila
    df_merged = pd.merge(df_campo2, df_control2, on='nombre_comun', how='left', indicator=True)

    # Filtrar las filas que no coincidan en ambos dataframes
    df_no_coincidentes = df_merged[df_merged['_merge'] != 'both']

    # Eliminar la columna '_merge' ya que ya no se necesita
    df_resultante_2 = df_no_coincidentes.drop(columns=['_merge'])
    return df_resultante_2



st.set_page_config(page_title='QAQC Encuesta Contingencia V1.0', layout='wide', initial_sidebar_state='expanded')

with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

logo = Image.open('logo.png')
st.sidebar.image(logo, width=150,)

st.title('QAQC Encuesta Contingencia - MSB V2.0 - Nuevo Formato ')
st.sidebar.header('`Version 1.0`')

st.text('Aplicacion web para la autogestión del QAQC para la encuesta de Contingencia (Todas las especialidades necesarias.)')
st.caption('Todos los indicadores deben tener la confirmacion de correcto ✅ para poder ser enviados al area de Data Manager.')

##Carga de catalogos para controles de calidad mapeados en el archivo excel controles
df_comportamiento = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='comportamiento', index_col=False)
df_mot_interv = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='mot_interv', index_col=False)
df_causa_prob = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='causa_probable', index_col=False)
df_tipo_registro = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='tipo_registro', index_col=False)
df_comportamiento = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='comportamiento', index_col=False)
df_area_operativa = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='area_operativa', index_col=False)
df_localidad = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='localidad', index_col=False)
df_herpetofauna = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='herpetofauna', index_col=False)
df_herpetofauna.columns = ['nombre_comun']
df_ornitofauna = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='ornitofauna', index_col=False)
df_ornitofauna.columns = ['nombre_comun']
df_mastofauna = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='mastofauna', index_col=False)
df_mastofauna.columns = ['nombre_comun']
df_ictiofauna = pd.read_excel('controles_app.xlsx', engine='openpyxl', sheet_name='ictiofauna', index_col=False)
df_ictiofauna.columns = ['nombre_comun']

##Carga de catalogo de especies oficial
catalogo_especies = pd.read_csv('catalogos/catalogo_especie_full_2024.1.csv', sep=';', encoding='UTF-8')
catalogo_especies_minimo = catalogo_especies[['id_esp', 'especie']]
catalogo_especies_minimo2 = catalogo_especies[['id_esp', 'nombre_comun']]

## SIDEBAR
uploaded_file = st.sidebar.file_uploader(' ***Elija la plantilla excel***', type='xlsx')
nombre_hoja = 'Plantilla_Contingencia'
numero_campos_masto = 41

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheets = xls.sheet_names  # see all the sheets in your file
    #sheets_pd = pd.DataFrame(sheets)    
    #st.sidebar.dataframe(sheets_pd.values[1:])    
    df = pd.read_excel(uploaded_file, engine='openpyxl', sheet_name=nombre_hoja, parse_dates=['fecha_evaluacion'])
    df_especie = (pd.read_excel(uploaded_file, engine='openpyxl', sheet_name='AAQ_MSB_Contingencia_Fauna__0')).shape[0]
    ##Crear Dataframe Sin Registro en el campo observacion
    df_sin_registro = df[df['observacion'] != 'Sin registro']
    ##Funcion para obtener valor unico de componente biologico
    df_inicial = df.copy()
    especialidad_unica = componente_biologico_unico(df,'componente_biologico')
    conteo_df = df.groupby('componente_biologico').size().reset_index(name='conteo')

    ##Conteo de catalogos que se estan leyendo para mostrar en sidebar
    df_hojas = leer_excel_y_crear_dataframe(xls)
    st.sidebar.write("Información de las hojas del archivo Excel:")
    st.sidebar.dataframe(df_hojas)
    st.sidebar.write("N° Especies en catalogo: ", catalogo_especies.shape[0])
    st.sidebar.write("N° Motivos Inter: ", df_mot_interv.shape[0])
    
    ##Transformacion espacial
    myProj = pyproj.Proj('+proj=utm +zone=19 +south +ellps=WGS84', preserve_units=False)
    df_sin_registro['lon_inicio'], df_sin_registro['lat_inicio'] = myProj(df_sin_registro['este_registro'].values, df_sin_registro['norte_registro'].values, inverse=True)
    df_sin_registro['lon_registro'], df_sin_registro['lat_registro'] = myProj(df_sin_registro['este_registro'].values, df_sin_registro['norte_registro'].values, inverse=True)
    ##Creacion de DF Espacial
    df_espacial = df_sin_registro[['objectid','motivo_intervencion','componente_localidad','lat_registro','lon_registro']]
    df_espacial_sin_vacios = df_espacial.dropna()
    filas_con_valores_vacios = df_espacial[df_espacial['lat_registro'].isnull()]
    gdf = gpd.GeoDataFrame(df_espacial_sin_vacios, geometry=gpd.points_from_xy(df_espacial_sin_vacios.lon_registro, df_espacial_sin_vacios.lat_registro))
    gdf['dentro'] = gdf.apply(lambda row: row.geometry.within(area_especifica), axis=1)
    registros_fuera = gdf[~gdf['dentro']]
    ##Creacion dataframes para comparar con controles
    ##Motivo intervencion
    df_mot_interv_archivo = df[['motivo_intervencion']]
    df_localidad_archivo = df[['componente_localidad']]
    df_causa_prob_archivo = df[['causa_probable']]
    df_tipo_registro_archivo = df[['tipo_registro', 'componente_biologico']]
    df_comportamiento_archivo = df[['comportamiento', 'componente_biologico']]
    
    ##Dataframe de especies
    df_filtrado_ornito = df[df['componente_biologico']=='Ornitofauna']
    df_filtrado_ornito = df_filtrado_ornito[['id_esp','nombre_comun','globalid','componente_biologico']]
    df_filtrado_herpeto = df[df['componente_biologico']=='Herpetofauna']
    df_filtrado_herpeto = df_filtrado_herpeto[['id_esp','nombre_comun','globalid','componente_biologico']]
    df_filtrado_masto = df[df['componente_biologico']=='Mastofauna']
    df_filtrado_masto = df_filtrado_masto[['id_esp','nombre_comun','globalid','componente_biologico']]
    df_filtrado_ictio = df[df['componente_biologico']=='Ictiofauna']
    df_filtrado_ictio = df_filtrado_ictio[['id_esp','nombre_comun','globalid','componente_biologico']]
    df_especies_archivo = df[['id_esp','nombre_comun','globalid']]
    df_especies_archivo.columns = ['id_esp', 'especie','globalid']
    df_especies_archivo = df_especies_archivo.dropna()
    #
    #df_1 = df[df.metodologia == 'Busqueda por Encuentros Visuales (VES)']
    #df_ves = df_1[['metodologia', 'este_registro', 'norte_registro']]
    #   
    conteo_campos_mastofauna = len(df_inicial.columns)    
    
    ###Dataframe de abundancia de Sexo
    df_abundancia_sexo = df[['n_macho','n_hembra_prenada_gravida','n_hembra_no_prenada_gravida','n_indeterminado_sexo']]
    df_abundancia_sexo_funcion = df[['globalid','n_macho','n_hembra_prenada_gravida','n_hembra_no_prenada_gravida','n_indeterminado_sexo','abundancia']]
    df_abundancia_sexo['suma_abundancia_sexo'] = df_abundancia_sexo.sum(axis=1)
    ########################################
    #Variable suma abundancia_sexo
    total_abundancia_sexo = df_abundancia_sexo['suma_abundancia_sexo'].sum()

    ##Creacion dataframe abundancia edad
    df_abundancia_edad = df[['n_adulto','n_juvenil','n_cria','n_huevo','n_indeterminado_edad','n_subadulto']]
    df_abundancia_edad_funcion = df[['globalid','n_adulto','n_juvenil','n_cria','n_huevo','n_indeterminado_edad','n_subadulto','abundancia']]
    df_abundancia_edad['suma_abundancia_edad'] = df_abundancia_edad.sum(axis=1)   
    
    #Variable suma abundancia edad
    total_abundancia_edad = df_abundancia_edad['suma_abundancia_edad'].sum()

    #Suma abundancia campo abundancia
    suma_abundancias = df['abundancia'].sum()

    tab1 , tab2, tab3 = st.tabs([':clipboard: Integridad Estructural', ':chart: Campos Especificos', ':bar_chart: Parte Espacial'])
    with tab1:
        # Primera fila
        st.markdown('### Metricas de los Datos')
        col1, col2, col3= st.columns(3)
        #col1.metric("Componente Biologico",(st.dataframe(especialidad_unica)))     
        with col1:
            st.markdown(' N° Componentes')
            st.dataframe(conteo_df,
                 column_order=("componente_biologico", "conteo"),
                 hide_index=True,
                 width=None,
                 column_config={
                    "componente_biologico": st.column_config.TextColumn(
                        "Comp. Biologico",
                    ),
                    "conteo": st.column_config.ProgressColumn(
                        "N° registros",
                        format="%f",
                        min_value=0,
                        max_value=max(conteo_df.conteo),
                     )},use_container_width=True
                 )
        
        
        with col2:
            st.metric("N° Registros", len(df))
            if (int(df.duplicated().sum()) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
        with col3:
            st.metric("N° Campos Plantilla Fauna", conteo_campos_mastofauna, 
            help='El valor debe ser cero')
            if (conteo_campos_mastofauna == numero_campos_masto):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
            
        
        

        st.markdown('### Campos de Integridad ID en Plantilla Fauna: Vacíos y Duplicados')
        conteo_datos_vacios_globalid = df['globalid'].isnull().sum()
        col1, col2, col3 = st.columns(3)
        with col1: 
            st.metric("GlobalID Vacios", df['globalid'].isnull().sum())
            if (int(df['globalid'].isnull().sum()) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
        with col2:
            st.metric("GlobalID1 Vacios", df['globalid'].isnull().sum())
            if (int(df['globalid'].isnull().sum()) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
        with col3:
            st.metric("GlobalID 1 Duplicados",df['globalid'].duplicated().sum())
            if (int(df['globalid'].duplicated().sum()) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
        #with col4:
        #    st.metric("GlobalID Duplicados",df['globalid'].duplicated().sum())
        #    if (int(df['globalid'].duplicated().sum()) == 0):
        #        st.success('Parametro CORRECTO',icon='✅')
        #    else:
        #        st.error('Parametro INCORRECTO',icon='🚨')
        
        st.markdown('## Graficas generales')
        col1, col2 = st.columns([2,1])
        with col1:
            groupby_column = st.selectbox(
            'Que le gustaria graficar?',
            ('condicion_animal', 'tipo_registro', 'motivo_intervencion', 'componente_localidad'),
            )
            output_columns = ['globalid']
            df_grouped = df.groupby(by=[groupby_column], as_index=False)[output_columns].count()
            
            fig = px.bar(df_grouped,
                        x= groupby_column,
                        y= df_grouped.globalid,                         
                        color=groupby_column)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown('Tabla de registros')
            st.dataframe(df_grouped,
                 column_order=[groupby_column]+output_columns,
                 hide_index=True,
                 width=None,
                 column_config={
                    groupby_column: st.column_config.TextColumn(
                        groupby_column,
                    ),},use_container_width=True
                 )
        
        
        df_copia = df.copy()            
        df_copia['fecha_evaluacion'] = pd.to_datetime(df_copia['fecha_evaluacion']).dt.date
        chart = alt.Chart(df_copia).mark_bar().encode(
                x=alt.X('fecha_evaluacion:T', title='Fecha de Evaluación'),
                y=alt.Y('count()', title='Número de Registros'),
                color=alt.Color('componente_biologico:N', title='Componente Biológico',),
                tooltip=[alt.Tooltip('fecha_evaluacion:T', title='Fecha'), alt.Tooltip('count()', title='Número de Registros'), 'componente_biologico:N']
            ).properties(
                width=800,
                height=400,
                title='Distribución de Registros por Fecha y Componente Biológico'
            )
        st.altair_chart(chart, use_container_width=True)

            

    with tab2:
        # Primera fila
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown('#### Suma Abundancia-Sexo')
            st.metric(
                label=" ***Comparativa ABUNDANCIA-SEXO*** ",
                help='El indicador debe mostrar siempre el valor 0 para ser correcto',
                value=round(total_abundancia_sexo, ndigits=None),
                delta=int(suma_abundancias) - int(total_abundancia_sexo)
                )
            if (int(suma_abundancias) - int(total_abundancia_sexo) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(encontrar_diferencias_sexo(df_abundancia_sexo_funcion))        
        with col2:
            st.markdown('#### Suma Abundancia-Edad')
            st.metric(label=" ***Comparativa ABUNDANCIA-EDAD*** ",
                help='El indicador debe mostrar siempre el valor 0 para ser correcto',
                value=round(total_abundancia_edad, ndigits=None),
                delta=int(suma_abundancias) - int(total_abundancia_edad)
                )
            if (int(suma_abundancias) - int(total_abundancia_edad) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(encontrar_diferencias_edad(df_abundancia_edad_funcion))
        with col3:
            st.markdown('#### Componente-Localidad')
            observaciones = ['Coincide' if coincide_con_control(fila, df_localidad) else 'No coincide' for _, fila in df_localidad_archivo.iterrows()]
            df_localidad_archivo['Observaciones'] = observaciones
            df_localidad_filtrada = df_localidad_archivo[df_localidad_archivo['Observaciones'] == 'No coincide']

            st.metric("Diferencias encontradas", len(df_localidad_filtrada))
            if (len(df_localidad_filtrada) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_localidad_filtrada.drop_duplicates())
        with col4:
            st.markdown('#### Motivo Intervencion')
            observaciones = ['Coincide' if coincide_con_control(fila, df_mot_interv) else 'No coincide' for _, fila in df_mot_interv_archivo.iterrows()]
            df_mot_interv_archivo['Observaciones'] = observaciones
            df_mot_interv_archivo_filtrada = df_mot_interv_archivo[df_mot_interv_archivo['Observaciones'] == 'No coincide']

            st.metric("Diferencias encontradas", len(df_mot_interv_archivo_filtrada))
            if (len(df_mot_interv_archivo_filtrada) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_mot_interv_archivo_filtrada.drop_duplicates())
        #with col5:
        #    st.metric("Variables Numéricas",df.select_dtypes(exclude='object').shape[1])
        
        ##Iniciando segunda fila
        col2_1, col2_2, col2_3, col2_4 = st.columns(4)
        with col2_1:
            st.markdown('#### Especies Herpetofauna')
            df_especies_no_registradas_herpeto = encontrar_especies_no_registradas2(df_herpetofauna, df_filtrado_herpeto)
            st.metric("Especies no corresponden", len(df_especies_no_registradas_herpeto))
            if (len(df_especies_no_registradas_herpeto) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_especies_no_registradas_herpeto.drop_duplicates())

        with col2_2:
            st.markdown('#### Especies Ornitofauna')
            df_especies_no_registradas_ornito = encontrar_especies_no_registradas2(df_ornitofauna, df_filtrado_ornito)
            st.metric("Especies no corresponden", len(df_especies_no_registradas_ornito))
            if (len(df_especies_no_registradas_ornito) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_especies_no_registradas_ornito.drop_duplicates())
            
        with col2_3:
            st.markdown('#### Especies Mastofauna')
            df_especies_no_registradas_masto = encontrar_especies_no_registradas2(df_mastofauna, df_filtrado_masto)
            st.metric("Especies no corresponden", len(df_especies_no_registradas_masto))
            if (len(df_especies_no_registradas_masto) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_especies_no_registradas_masto.drop_duplicates())
            
        with col2_4:
            st.markdown('#### Especies Ictiofauna')
            df_especies_no_registradas_ictio = encontrar_especies_no_registradas2(df_ictiofauna, df_filtrado_ictio)
            st.metric("Especies no corresponden", len(df_especies_no_registradas_ictio))
            if (len(df_especies_no_registradas_ictio) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_especies_no_registradas_ictio.drop_duplicates())
        col_grupo_2_1, col_grupo_2_2, col_grupo_2_3 = st.columns(3)
        with col_grupo_2_1:
            st.markdown('#### Comportamiento')
            observaciones = ['Coincide' if coincide_con_control(fila, df_comportamiento) else 'No coincide' for _, fila in df_comportamiento_archivo.iterrows()]
            df_comportamiento_archivo['Observaciones'] = observaciones
            df_comportamiento_archivo_filtrada = df_comportamiento_archivo[df_comportamiento_archivo['Observaciones'] == 'No coincide']
            
            st.metric("Diferencias encontradas", len(df_comportamiento_archivo_filtrada))
            if (len(df_comportamiento_archivo_filtrada) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_comportamiento_archivo_filtrada.drop_duplicates())
        with col_grupo_2_2:
            st.markdown('#### Tipo Registro')
            observaciones = ['Coincide' if coincide_con_control(fila, df_tipo_registro) else 'No coincide' for _, fila in df_tipo_registro_archivo.iterrows()]
            df_tipo_registro_archivo['Observaciones'] = observaciones
            df_tipo_registro_archivo_filtrada = df_tipo_registro_archivo[df_tipo_registro_archivo['Observaciones'] == 'No coincide']
            
            st.metric("Diferencias encontradas", len(df_tipo_registro_archivo_filtrada))
            if (len(df_tipo_registro_archivo_filtrada) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_tipo_registro_archivo_filtrada.drop_duplicates())
        with col_grupo_2_3:
            
            st.markdown('#### Causa Probable')
            observaciones = ['Coincide' if coincide_con_control(fila, df_causa_prob) else 'No coincide' for _, fila in df_causa_prob_archivo.iterrows()]
            df_causa_prob_archivo['Observaciones'] = observaciones
            df_causa_prob_archivo_filtrada = df_causa_prob_archivo[df_causa_prob_archivo['Observaciones'] == 'No coincide']

            st.metric("Diferencias encontradas", len(df_causa_prob_archivo_filtrada))
            if (len(df_causa_prob_archivo_filtrada) == 0):
                st.success('Parametro CORRECTO',icon='✅')
            else:
                st.error('Parametro INCORRECTO',icon='🚨')
                with st.expander('Tabla de datos'):
                    st.dataframe(df_causa_prob_archivo_filtrada.drop_duplicates())
            
            
            
            
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('#### Parte Espacial')
            col1_espacial, col2_espacial = st.columns(2)
            with col1_espacial:
                st.metric("Registros sin coordenadas", filas_con_valores_vacios.shape[0])
                if (df_espacial_sin_vacios.shape[0] == df_sin_registro.shape[0]):
                    st.success('Parametro CORRECTO',icon='✅')
                else:
                    st.error('Parametro INCORRECTO',icon='🚨')
            with col2_espacial:
                st.metric("Registros fuera de area", registros_fuera.shape[0])
                if (registros_fuera.shape[0] == 0):
                    st.success('Parametro CORRECTO',icon='✅')
                else:
                    st.error('Parametro INCORRECTO',icon='🚨')
            st.markdown('#### Registros sin coordenadas')
            st.dataframe(filas_con_valores_vacios, use_container_width=True)
            st.markdown('#### Registros fuera de area')
            st.dataframe(registros_fuera.drop(columns=['geometry','dentro']), use_container_width=True)            
        with col2:
            # Crear el mapa
            st.markdown('#### Mapa Ubicación')
            mapa = create_map()
            # Mostrar el mapa en Streamlit
            folium_static(mapa, width=700, height=700 )
    

